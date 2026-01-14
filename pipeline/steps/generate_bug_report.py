import os
import json
import re
from llm.llm_client import call_llm
from llm.prompts.bug_report import PROMPT
from logs.logger import log_error

def _extract_json_from_llm_response(text: str) -> str:
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text

def run(ctx):
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # === Исходный чеклист ===
    checklist = ctx.get("masked_scenarios", "")  # ← правильный ключ

    # === Тест-кейсы (уже объект, а не строка) ===
    testcases = ctx.get("testcases_json", [])
    testcases_str = json.dumps(testcases, indent=2, ensure_ascii=False)

    # === Сгенерированные автотесты ===
    autotests = ""
    autotest_files = ctx.get("autotest_files", [])
    for file_path in autotest_files:
        if file_path.endswith(".py") and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                autotests += f"--- {os.path.basename(file_path)} ---\n{f.read()}\n\n"

    # === AI Code Reviews ===
    reviews = ""
    ai_reviews = ctx.get("ai_code_reviews", [])
    for review_path in ai_reviews:
        if os.path.exists(review_path):
            with open(review_path, "r", encoding="utf-8") as f:
                reviews += f"--- {os.path.basename(review_path)} ---\n{f.read()}\n\n"

    # === Результаты тестов ===
    test_results = ""
    test_xml_path = ctx.get("test_results_xml")
    if test_xml_path and os.path.exists(test_xml_path):
        with open(test_xml_path, "r", encoding="utf-8") as f:
            test_results = f.read()

    # === QA Summary ===
    qa_summary = ctx.get("qa_summary_text", "Not available")

    # === Генерация промпта ===
    try:
        prompt = PROMPT.format(
            checklist=checklist,
            testcases=testcases_str,
            tests=autotests,
            review=reviews,
            qa_summary=qa_summary,
            test_results=test_results
        )
    except KeyError as e:
        print(f"Prompt formatting failed: missing key {e}")
        ctx["bug_report"] = None
        return

    # === Вызов LLM ===
    try:
        # Настройки модели (как в других шагах)
        from dotenv import load_dotenv
        load_dotenv()
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

        clean_json_str = _extract_json_from_llm_response(raw_response)
        bug_report = json.loads(clean_json_str)

        report_file = os.path.join(report_dir, "bug_report.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(bug_report, f, indent=2, ensure_ascii=False)
        ctx["bug_report"] = report_file

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to parse bug report JSON: {e}")
        error_file = os.path.join(report_dir, "bug_report_raw.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(raw_response)
        ctx["bug_report"] = error_file
    except Exception as e:
        error_message = f"LLM call failed in bug report generation: {e}"
        print(f"❌ {error_message}")
        log_error(error_message)
        ctx["bug_report"] = None