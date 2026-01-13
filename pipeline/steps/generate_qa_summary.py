import os
from dotenv import load_dotenv  # ← добавь импорт
from llm.gemini_client import call_llm
from llm.prompts.qa_summary import PROMPT
from logs.logger import log_error

load_dotenv()  # ← загрузи переменные


def run(ctx):
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    test_log_path = ctx.get("test_run_log")
    test_xml_path = ctx.get("test_results_xml")

    test_log = ""
    if test_log_path and os.path.exists(test_log_path):
        with open(test_log_path, 'r', encoding='utf-8') as f:
            test_log = f.read()

    test_xml = ""
    if test_xml_path and os.path.exists(test_xml_path):
        with open(test_xml_path, 'r', encoding='utf-8') as f:
            test_xml = f.read()

    if not test_log and not test_xml:
        print("No test results found to generate a QA summary.")
        ctx["qa_summary_text"] = None
        return

    try:
        # === Настройки LLM (как в других шагах) ===
        llm_provider = os.getenv("LLM_PROVIDER", "cloud")
        if llm_provider == "cloud":
            model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
        else:
            model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))

        prompt = PROMPT.format(test_log=test_log, test_xml=test_xml)

        # === Правильный вызов ===
        summary_text = call_llm(
            model_name=model_name,
            temperature=temperature,
            prompt=prompt
        )

        if not summary_text or not summary_text.strip():
            summary_text = "⚠️ Warning: LLM returned an empty response for QA summary."

        summary_file_path = os.path.join(report_dir, "qa_summary.txt")
        with open(summary_file_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        ctx["qa_summary_report"] = summary_file_path
        ctx["qa_summary_text"] = summary_text
        print(f"✅ QA Summary saved to {summary_file_path}")

    except Exception as e:
        error_message = f"Failed to generate QA summary: {e}"
        print(f"❌ {error_message}")
        log_error(error_message)
        ctx["qa_summary_text"] = None