import logging
import os
import json
import re
from dotenv import load_dotenv
from llm.gemini_client import call_llm
from logs.logger import log_error  # Оставляем для критических ошибок

load_dotenv()


def _extract_json_obj(text: str) -> str:
    """Извлекает самую внешнюю пару {...} из текста и удаляет однострочные комментарии."""
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No valid JSON object detected in LLM response")
    json_str = text[start:end + 1]
    # Удаляем однострочные комментарии вида // ...
    json_str = re.sub(r"//.*", "", json_str)
    return json_str


def run(ctx):
    # === Настройка модели ===
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    if llm_provider == "cloud":
        model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
    else:  # local
        model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")

    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

    # === Входные данные ===
    if "scenarios" not in ctx:
        available_keys = list(ctx.keys())
        raise ValueError(f"Context missing required key: 'scenarios'. Available keys: {available_keys}")

    scenarios = ctx["scenarios"]
    logging.debug(f"Input scenarios (first 500 chars): {str(scenarios)[:500]}...")

    # === Формирование промпта ===
    # Промпт должен быть в коде или импортирован, но экранирован!
    # Убедись, что в PROMPT все { и } экранированы как {{ и }}
    from llm.prompts.testcases import PROMPT
    try:
        prompt_text = PROMPT.format(scenarios=scenarios)
    except (KeyError, IndexError, ValueError) as e:
        log_error(f"Prompt formatting failed: {e}")
        raise ValueError(f"Failed to format prompt: {e}")

    # === Вызов LLM ===
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    logging.debug(f"Raw LLM response (first 500 chars): {result[:500]}...")

    # === Извлечение и парсинг JSON ===
    try:
        json_str = _extract_json_obj(result)
        parsed = json.loads(json_str)

        if "testcases" not in parsed:
            raise ValueError("LLM response JSON missing 'testcases' key")

        ctx["testcases_json"] = parsed["testcases"]
        logging.info("Successfully parsed test cases from LLM response")

    except (json.JSONDecodeError, ValueError) as e:
        log_error(
            f"Failed to parse LLM response as JSON: {e}\n"
            f"Raw response (first 500 chars): {result[:500]}..."
        )
        raise ValueError(
            f"LLM did not return valid JSON for test cases. Error: {e}\n"
            f"Response snippet: {result[:500]}..."
        )