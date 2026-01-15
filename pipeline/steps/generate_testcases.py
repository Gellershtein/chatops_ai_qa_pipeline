"""
This module implements the Generate Test Cases step of the QA pipeline.
It takes a set of test scenarios and uses a Large Language Model (LLM)
to convert them into a structured JSON array of test cases.
"""
import logging
import os
import json
import re
from llm.llm_client import call_llm
from logs.logger import log_error  # Used for critical errors
from typing import Dict, Any, List

# Load environment variables. This should ideally be done once at application startup.

def _extract_json_obj(text: str) -> str:
    """
    Extracts the outermost JSON object (enclosed by `{...}`) from a given text
    and removes single-line comments (e.g., `// ...`). This is useful for
    cleaning LLM responses that might contain extra text or comments around the JSON.

    Args:
        text (str): The raw text potentially containing a JSON object.

    Returns:
        str: A cleaned JSON string suitable for `json.loads()`.

    Raises:
        ValueError: If no valid outermost JSON object is detected.
    """
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No valid JSON object detected in LLM response")
    json_str = text[start:end + 1]
    # Remove single-line comments (e.g., // some comment)
    json_str = re.sub(r"//.*", "", json_str)
    return json_str


def run(ctx: Dict[str, Any]) -> None:
    """
    Executes the Generate Test Cases step. It retrieves test scenarios from the
    pipeline context, uses an LLM to convert these scenarios into a structured
    JSON array of test cases, and then stores the parsed test cases back into
    the pipeline context. It includes robust error handling for LLM calls and
    JSON parsing.

    Args:
        ctx (Dict[str, Any]): The pipeline context dictionary, which must contain:
                              - 'scenarios' (str): A string containing the generated test scenarios.
    """
    # === LLM Configuration ===
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    if llm_provider == "cloud":
        model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
    else:  # local
        model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")

    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

    # === Input Data Validation ===
    if "scenarios" not in ctx:
        available_keys = list(ctx.keys())
        error_msg = f"Context missing required key: 'scenarios'. Available keys: {available_keys}"
        log_error(error_msg)
        raise ValueError(error_msg)

    scenarios = ctx["scenarios"]
    logging.debug(f"Input scenarios (first 500 chars): {str(scenarios)[:500]}...")

    # === Prompt Formatting ===
    # The PROMPT is imported from llm.prompts.testcases
    from llm.prompts.testcases import PROMPT
    try:
        prompt_text = PROMPT.format(scenarios=scenarios)
    except (KeyError, IndexError, ValueError) as e:
        error_msg = f"Prompt formatting failed: {e}"
        log_error(error_msg)
        raise ValueError(f"Failed to format prompt: {e}")

    # === LLM Call ===
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    logging.debug(f"Raw LLM response (first 500 chars): {result[:500]}...")

    # === Extract and Parse JSON ===
    try:
        json_str = _extract_json_obj(result)
        parsed = json.loads(json_str)

        if "testcases" not in parsed:
            error_msg = "LLM response JSON missing 'testcases' key"
            log_error(f"{error_msg}. Raw response: {json_str}")
            raise ValueError(error_msg)

        ctx["testcases_json"] = parsed["testcases"]
        logging.info("Successfully parsed test cases from LLM response")
        print("✅ Test cases generated successfully.")

    except (json.JSONDecodeError, ValueError) as e:
        error_msg = (
            f"Failed to parse LLM response as JSON: {e}\n"
            f"Raw response (first 500 chars): {result[:500]}..."
        )
        log_error(error_msg)
        raise ValueError(
            f"LLM did not return valid JSON for test cases. Error: {e}\n"
            f"Response snippet: {result[:500]}..."
        )