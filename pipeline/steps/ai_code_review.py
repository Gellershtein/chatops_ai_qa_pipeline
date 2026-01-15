"""
This module implements the AI Code Review step of the QA pipeline.
It takes auto-generated test code, sends it to an LLM for review based on a specific prompt,
and processes the LLM's response to extract and save structured code review reports.
"""
import os
import json
import re
from dotenv import load_dotenv
from llm.llm_client import call_llm
from llm.prompts.code_review import PROMPT

load_dotenv()

def _extract_json_from_llm_response(text: str) -> str:
    """
    Extracts a JSON string from an LLM's raw text response by removing markdown code block delimiters.
    This function is crucial when LLMs enclose JSON output within markdown blocks (e.g., ```json ... ```).

    Args:
        text (str): The raw text response received from the LLM.

    Returns:
        str: A clean JSON string, suitable for parsing with `json.loads()`.
    """
    # Remove leading ```json or ``` and any whitespace
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    # Remove trailing ``` and any whitespace
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text


def run(ctx: dict) -> None:
    """
    Executes the AI Code Review step. This function iterates through autotest files,
    sends their content to an LLM for code review, and saves the LLM's structured
    review responses as JSON files. It also handles cases where autotest files
    are not explicitly provided in the context.

    Args:
        ctx (dict): The pipeline context dictionary, which must contain:
                    - 'run_id' (str): The unique identifier for the current pipeline run.
                    - 'autotest_files' (list, optional): A list of paths to autotest files to review.
                                                        If not provided, it will look for 'autotests_dir'.
                    - 'autotests_dir' (str, optional): The directory containing autotest .py files.
                                                       Used if 'autotest_files' is not provided.
    """
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # === Determine files for review ===
    autotest_files = ctx.get("autotest_files", [])

    # If specific files are not provided, search for .py files in the autotests directory
    if not autotest_files:
        autotests_dir = ctx.get("autotests_dir")
        if autotests_dir and os.path.isdir(autotests_dir):
            autotest_files = [
                os.path.join(autotests_dir, f)
                for f in os.listdir(autotests_dir)
                if f.endswith(".py")
            ]
        else:
            print("❌ Neither 'autotest_files' nor 'autotests_dir' found in context. Skipping AI review.")
            ctx["ai_code_reviews"] = []
            return

    if not autotest_files:
        print("⚠️ No .py files found for AI review.")
        ctx["ai_code_reviews"] = []
        return

    # === LLM Configuration ===
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    # Determine model name based on provider
    model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro") if llm_provider == "cloud" else os.getenv(
        "LOCAL_MODEL_NAME", "llama2")
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))

    reviews = [] # List to store paths of generated review files
    for file_path in autotest_files:
        if not os.path.isfile(file_path):
            continue

        # Read the content of the autotest file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            print(f"Failed to read {file_path}: {e}")
            continue

        # Extract test_id from the filename
        test_id = os.path.splitext(os.path.basename(file_path))[0]
        if test_id.startswith("test_"): # Remove 'test_' prefix if present
            test_id = test_id[5:]

        # === Prompt Generation ===
        try:
            prompt_text = PROMPT.format(code=code, test_id=test_id)
        except KeyError as e:
            # Fallback if prompt formatting fails (e.g., missing a key)
            print(f"Prompt formatting failed (missing key {e}) for {file_path}. Using fallback.")
            prompt_text = PROMPT.replace("{test_id}", test_id).format(code=code) # Attempt to format without specific key
        except Exception as e:
            print(f"Unexpected prompt error for {file_path}: {e}")
            continue

        # === LLM Call ===
        try:
            raw_response = call_llm(
                model_name=model_name,
                temperature=temperature,
                prompt=prompt_text
            )
        except Exception as e:
            print(f"LLM call failed for {test_id}: {e}")
            continue

        # === Response Processing ===
        try:
            # Extract clean JSON from LLM's raw response
            clean_json_str = _extract_json_from_llm_response(raw_response)
            review_data = json.loads(clean_json_str)

            # Save the structured review data to a JSON file
            review_file = os.path.join(report_dir, f"ai_code_review_{test_id}.json")
            with open(review_file, "w", encoding="utf-8") as f:
                json.dump(review_data, f, indent=2, ensure_ascii=False)
            reviews.append(review_file)

        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, save the raw LLM response for debugging
            print(f"JSON parse failed for {test_id}: {e}. Saving raw response.")
            debug_file = os.path.join(report_dir, f"ai_code_review_{test_id}_raw.txt")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(raw_response)
            reviews.append(debug_file)  # Add raw response file to artifacts to be sent to Telegram

    ctx["ai_code_reviews"] = reviews
    print(f"✅ AI Code Review completed. Generated {len(reviews)} report(s).")