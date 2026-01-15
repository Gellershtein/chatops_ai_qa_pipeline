"""
This module implements the Generate QA Summary step of the QA pipeline.
It processes test execution logs and XML reports to create a concise, high-level
QA summary using an LLM, making it accessible for non-technical stakeholders.
"""
import os
from llm.llm_client import call_llm
from llm.prompts.qa_summary import PROMPT
from logs.logger import log_error
from typing import Dict, Any

def run(ctx: Dict[str, Any]) -> None:
    """
    Executes the Generate QA Summary step. This function gathers test log and
    XML report data from the pipeline context, uses it to format a prompt for the LLM,
    and then calls the LLM to generate a QA summary. The summary is saved as a text file
    and also stored in the context for potential further use.

    Args:
        ctx (Dict[str, Any]): The pipeline context dictionary, expected to contain:
                              - 'run_id' (str): The unique identifier for the current pipeline run.
                              - 'test_run_log' (str, optional): Path to the full test execution log file.
                              - 'test_results_xml' (str, optional): Path to the test results XML report file.
    """
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # === Collect Input Artifacts ===
    test_log_path = ctx.get("test_run_log")
    test_xml_path = ctx.get("test_results_xml")

    # Read content of test log file
    test_log = ""
    if test_log_path and os.path.exists(test_log_path):
        with open(test_log_path, 'r', encoding='utf-8') as f:
            test_log = f.read()

    # Read content of test XML report file
    test_xml = ""
    if test_xml_path and os.path.exists(test_xml_path):
        with open(test_xml_path, 'r', encoding='utf-8') as f:
            test_xml = f.read()

    # If no test data is available, skip summary generation
    if not test_log and not test_xml:
        print("⚠️ No test results found to generate a QA summary. Skipping.")
        ctx["qa_summary_text"] = None
        ctx["qa_summary_report"] = None
        return

    # === Call LLM to Generate QA Summary ===
    try:
        # Configure LLM settings from environment variables (consistent with other steps)
        llm_provider = os.getenv("LLM_PROVIDER", "cloud")
        if llm_provider == "cloud":
            model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
        else:
            model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))

        # Format the prompt using collected test data
        prompt = PROMPT.format(test_log=test_log, test_xml=test_xml)

        # Call the LLM to get the summary
        summary_text = call_llm(
            model_name=model_name,
            temperature=temperature,
            prompt=prompt
        )

        # Handle empty LLM response
        if not summary_text or not summary_text.strip():
            summary_text = "⚠️ Warning: LLM returned an empty response for QA summary."
            print(summary_text)

        # Save the generated summary to a text file
        summary_file_path = os.path.join(report_dir, "qa_summary.txt")
        with open(summary_file_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        # Store the path and content of the summary in the context
        ctx["qa_summary_report"] = summary_file_path
        ctx["qa_summary_text"] = summary_text
        print(f"✅ QA Summary generated and saved to {summary_file_path}")

    except Exception as e:
        # Log and store error if LLM call or processing fails
        error_message = f"Failed to generate QA summary: {e}"
        print(f"❌ {error_message}")
        log_error(error_message)
        ctx["qa_summary_text"] = None
        ctx["qa_summary_report"] = None