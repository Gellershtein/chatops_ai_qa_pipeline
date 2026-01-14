import os
import json
import re
from dotenv import load_dotenv
from llm.llm_client import call_llm
from llm.prompts.code_review import PROMPT

load_dotenv()


def _extract_json_from_llm_response(text: str) -> str:
    """Удаляет markdown-блоки и оставляет только JSON."""
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text


def run(ctx):
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # === НАДЕЖНОЕ ОПРЕДЕЛЕНИЕ ФАЙЛОВ ДЛЯ РЕВЬЮ ===
    autotest_files = ctx.get("autotest_files", [])

    # Если список файлов не передан — ищем .py файлы в autotests_dir
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

    # === НАСТРОЙКИ LLM ===
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro") if llm_provider == "cloud" else os.getenv(
        "LOCAL_MODEL_NAME", "llama2")
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))

    reviews = []
    for file_path in autotest_files:
        if not os.path.isfile(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            print(f"Failed to read {file_path}: {e}")
            continue

        test_id = os.path.splitext(os.path.basename(file_path))[0]
        if test_id.startswith("test_"):
            test_id = test_id[5:]

        # === ГЕНЕРАЦИЯ ПРОМПТА ===
        try:
            prompt_text = PROMPT.format(code=code, test_id=test_id)
        except KeyError as e:
            print(f"Prompt formatting failed (missing key {e}) for {file_path}. Using fallback.")
            # Fallback: убираем {test_id} из промпта, если он не поддерживается
            prompt_text = PROMPT.replace("{test_id}", test_id).format(code=code)
        except Exception as e:
            print(f"Unexpected prompt error for {file_path}: {e}")
            continue

        # === ВЫЗОВ LLM ===
        try:
            raw_response = call_llm(
                model_name=model_name,
                temperature=temperature,
                prompt=prompt_text
            )
        except Exception as e:
            print(f"LLM call failed for {test_id}: {e}")
            continue

        # === ОБРАБОТКА ОТВЕТА ===
        try:
            clean_json_str = _extract_json_from_llm_response(raw_response)
            review_data = json.loads(clean_json_str)

            review_file = os.path.join(report_dir, f"ai_code_review_{test_id}.json")
            with open(review_file, "w", encoding="utf-8") as f:
                json.dump(review_data, f, indent=2, ensure_ascii=False)
            reviews.append(review_file)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parse failed for {test_id}: {e}")
            # Сохраняем сырой ответ — и добавляем в артефакты!
            debug_file = os.path.join(report_dir, f"ai_code_review_{test_id}_raw.txt")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(raw_response)
            reviews.append(debug_file)  # ← КЛЮЧЕВОЕ: теперь файл отправится в Telegram!

    ctx["ai_code_reviews"] = reviews
    print(f"✅ AI Code Review completed. Generated {len(reviews)} report(s).")