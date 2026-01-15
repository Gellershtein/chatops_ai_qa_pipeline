"""
This module implements the Generate Bug Report step of the QA pipeline.
It aggregates various artifacts from previous steps (test cases, autotests, code reviews,
test results, QA summary) and uses an LLM to generate a structured bug report
if discrepancies or issues are identified.
"""
import os
import json
import re
from llm.llm_client import call_llm
from llm.prompts.bug_report import PROMPT
from logs.logger import log_error
from typing import Dict, Any

def _extract_json_from_llm_response(text: str) -> str:
    """
    Extracts a JSON string from an LLM's raw text response by removing markdown code block delimiters.
    This function is a duplicate of one found in `ai_code_review.py` and could be moved to a shared utility module.

    Args:
        text (str): The raw text response received from the LLM.

    Returns:
        str: A clean JSON string, suitable for parsing with `json.loads()`.
    """
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text

def run(ctx: Dict[str, Any]) -> None:
    """
    Executes the Generate Bug Report step. This function gathers all relevant artifacts
    from the pipeline context, constructs a comprehensive prompt for the LLM,
    and uses the LLM to generate a structured bug report based on the provided data.
    The generated report (or a raw error log if parsing fails) is saved.

    Args:
        ctx (Dict[str, Any]): The pipeline context dictionary, expected to contain:
                              - 'run_id' (str): Unique identifier for the run.
                              - 'masked_scenarios' (str): PII-masked scenarios (checklist).
                              - 'testcases_json' (list): List of generated test cases.
                              - 'autotest_files' (list): List of paths to generated autotest files.
                              - 'ai_code_reviews' (list): List of paths to AI code review reports.
                              - 'test_results_xml' (str): Path to the test results XML file.
                              - 'qa_summary_text' (str): Text of the QA summary.
    """
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # === Collect Input Artifacts ===
    # PII-masked checklist content
    checklist = ctx.get("masked_scenarios", "")

    # Test cases (already a Python object, needs to be dumped to string for prompt)
    testcases = ctx.get("testcases_json", [])
    testcases_str = json.dumps(testcases, indent=2, ensure_ascii=False)

    # Concatenate content of all generated autotest files
    autotests = ""
    autotest_files = ctx.get("autotest_files", [])
    for file_path in autotest_files:
        if file_path.endswith(".py") and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                autotests += f"--- {os.path.basename(file_path)} ---\n{f.read()}\n\n"

    # Concatenate content of all AI code review reports
    reviews = ""
    ai_reviews = ctx.get("ai_code_reviews", [])
    for review_path in ai_reviews:
        if os.path.exists(review_path):
            with open(review_path, "r", encoding="utf-8") as f:
                reviews += f"--- {os.path.basename(review_path)} ---\n{f.read()}\n\n"

    # Read the test results XML content
    test_results = ""
    test_xml_path = ctx.get("test_results_xml")
    if test_xml_path and os.path.exists(test_xml_path):
        with open(test_xml_path, "r", encoding="utf-8") as f:
            test_results = f.read()

    # Get the QA summary text
    qa_summary = ctx.get("qa_summary_text", "Not available")

    # === Generate LLM Prompt ===
    try:
        # Format the prompt using all collected artifacts
        prompt = PROMPT.format(
            checklist=checklist,
            testcases=testcases_str,
            tests=autotests,
            review=reviews,
            qa_summary=qa_summary,
            test_results=test_results
        )
    except KeyError as e:
        print(f"Prompt formatting failed: missing key {e}. Bug report generation skipped.")
        ctx["bug_report"] = None
        return

    # === Call LLM to Generate Bug Report ===
    try:
        # Configure LLM settings from environment variables (consistent with other steps)
        # dotenv is loaded at module level, so no need to call load_dotenv() here again
        llm_provider = os.getenv("LLM_PROVIDER", "cloud")
        if llm_provider == "cloud":
            model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
        else:
            model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))

        raw_response = call_llm(
            model_name=model_name,
            temperature=temperature,
            prompt=prompt
        )

        # Extract and parse the JSON bug report from the LLM's response
        clean_json_str = _extract_json_from_llm_response(raw_response)
        bug_report = json.loads(clean_json_str)

        # Save the structured bug report to a JSON file
        report_file = os.path.join(report_dir, "bug_report.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(bug_report, f, indent=2, ensure_ascii=False)
        ctx["bug_report"] = report_file
        print(f"✅ Bug report generated and saved to {report_file}")

    except (json.JSONDecodeError, ValueError) as e:
        # If JSON parsing fails, save the raw LLM response for debugging purposes
        print(f"Failed to parse bug report JSON: {e}. Raw response saved.")
        error_file = os.path.join(report_dir, "bug_report_raw.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(raw_response)
        ctx["bug_report"] = error_file
    except Exception as e:
        # Catch any other LLM call or processing errors
        error_message = f"LLM call failed in bug report generation: {e}"
        print(f"❌ {error_message}")
        log_error(error_message)
        ctx["bug_report"] = None