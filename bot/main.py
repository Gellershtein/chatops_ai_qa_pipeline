from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
import tempfile
import json  # Import json for serialization
import time  # Import time for sleep in retry logic
import shutil  # <-- НОВЫЙ ИМПОРТ для архивации
from pipeline.runner import initialize_pipeline, PIPELINE_STEPS
from storage.minio_client import upload, upload_json, download_json  # Import new functions
from logs.logger import log_error
from collections import defaultdict  # For retry counts

# Map chat_id to run_id for ongoing pipelines
pipeline_runs = {}
# Store retry attempts for each step
step_retry_counts = defaultdict(lambda: defaultdict(int))

MINIO_CONTEXT_BUCKET = os.getenv("MINIO_BUCKET", "qa-pipeline")
MINIO_CONTEXT_PREFIX = "contexts"  # Prefix for storing context files in MinIO


def _get_context_minio_path(run_id: str) -> str:
    return f"{MINIO_CONTEXT_PREFIX}/{run_id}/context.json"


def _save_context_to_minio(ctx: dict):
    """Saves the pipeline context to MinIO as a JSON file."""
    run_id = ctx["run_id"]

    # Handle non-serializable objects (e.g., Requirement objects)
    serializable_ctx = ctx.copy()
    if "requirements" in serializable_ctx and isinstance(serializable_ctx["requirements"], list):
        serializable_ctx["requirements"] = [req.__dict__ for req in serializable_ctx["requirements"]]

    upload_json(MINIO_CONTEXT_BUCKET, _get_context_minio_path(run_id), serializable_ctx)


def _load_context_from_minio(run_id: str) -> dict:
    """Loads the pipeline context from MinIO."""
    loaded_ctx = download_json(MINIO_CONTEXT_BUCKET, _get_context_minio_path(run_id))

    # Convert serializable objects back (e.g., Requirement objects)
    if "requirements" in loaded_ctx and isinstance(loaded_ctx["requirements"], list):
        from models.requirement import Requirement  # Import Requirement model dynamically
        loaded_ctx["requirements"] = [Requirement(**req_dict) for req_dict in loaded_ctx["requirements"]]

    return loaded_ctx


def _delete_context_from_minio(run_id: str):
    """Deletes the pipeline context from MinIO."""
    try:
        pass
    except Exception as e:
        log_error(f"Failed to delete context for run_id {run_id} from MinIO: {e}")


def get_main_keyboard(ctx, is_retry_available=False):
    """Creates the main inline keyboard with the current step status."""
    step_index = ctx.get("step_index", 0)
    run_id = ctx.get("run_id")
    buttons = []

    if step_index < len(PIPELINE_STEPS):
        step_name, _ = PIPELINE_STEPS[step_index]
        if is_retry_available:
            buttons.append(
                [InlineKeyboardButton(f"🔁 Retry: {step_name}", callback_data=f"retry_step_{run_id}")]
            )
        else:
            buttons.append(
                [InlineKeyboardButton(f"▶️ Run: {step_name}", callback_data=f"run_step_{run_id}")]
            )
        buttons.append(
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_pipeline_{run_id}")]
        )
    else:
        buttons.append(
            [InlineKeyboardButton("🎉 Close Pipeline", callback_data=f"close_pipeline_{run_id}")]
        )

    return InlineKeyboardMarkup(buttons)


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles file upload and initializes the pipeline."""
    chat_id = update.effective_chat.id

    if chat_id in pipeline_runs:
        await context.bot.send_message(
            chat_id=chat_id, text="🔄 A pipeline is already in progress. Please wait or cancel it."
        )
        return

    doc = update.message.document
    if not doc.file_name.endswith((".txt", ".json")):
        await context.bot.send_message(
            chat_id=chat_id, text="📄 Please upload a .txt or .json file."
        )
        return

    try:
        file = await doc.get_file()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, doc.file_name)
            await file.download_to_drive(file_path)

            with open(file_path, 'rb') as f:
                content_bytes = f.read()

        upload(MINIO_CONTEXT_BUCKET, doc.file_name, content_bytes)

        ctx = initialize_pipeline(doc.file_name)
        pipeline_runs[chat_id] = ctx["run_id"]

        _save_context_to_minio(ctx)

        keyboard = get_main_keyboard(ctx)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📥 Pipeline initialized for `{doc.file_name}`\nRun ID: `{ctx['run_id']}`\nReady to start!",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        log_error(f"Error in handle_file for chat {chat_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error during initialization: `{e}`",
                                       parse_mode='Markdown')


async def run_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    run_id = query.data.split('_')[-1]

    try:
        ctx = _load_context_from_minio(run_id)
        pipeline_runs[chat_id] = run_id
    except Exception as e:
        log_error(f"Failed to load context for run_id {run_id}: {e}")
        await context.bot.send_message(chat_id=chat_id,
                                       text="❌ Pipeline state not found. Please upload a file again.")
        if chat_id in pipeline_runs:
            del pipeline_runs[chat_id]
        return

    step_index = ctx.get("step_index", 0)

    if step_index >= len(PIPELINE_STEPS):
        await context.bot.send_message(chat_id=chat_id, text="✅ Pipeline already completed.")
        del pipeline_runs[chat_id]
        _delete_context_from_minio(run_id)
        return

    step_name, step_function = PIPELINE_STEPS[step_index]

    retries = 3
    current_retry = step_retry_counts[chat_id][step_name]
    delay = 1 * (2 ** current_retry)

    if query.data.startswith("retry_step_"):
        await context.bot.send_message(chat_id=chat_id,
                                       text=f"🔁 Retrying *{step_name}* (Attempt {current_retry + 1}/{retries})...",
                                       parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 Running step: *{step_name}*...", parse_mode='Markdown')

    try:
        step_function(ctx)

        ctx["step_index"] += 1
        _save_context_to_minio(ctx)
        step_retry_counts[chat_id][step_name] = 0

        await _send_step_artifacts_if_available(update, context, ctx, step_name)

        next_keyboard = get_main_keyboard(ctx)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Step *{step_name}* completed.",
            reply_markup=next_keyboard,
            parse_mode='Markdown'
        )

    except Exception as e:
        error_message = str(e)
        if "503 UNAVAILABLE" in error_message and current_retry < retries - 1:
            step_retry_counts[chat_id][step_name] += 1
            log_error(
                f"LLM call failed (503 UNAVAILABLE) for run_id {run_id}, step {step_name}. Retrying in {delay} seconds. Attempt {step_retry_counts[chat_id][step_name]}/{retries}")
            await context.bot.send_message(chat_id=chat_id,
                                           text=f"⚠️ LLM service temporarily unavailable for *{step_name}*. Retrying in {delay} seconds...",
                                           parse_mode='Markdown')
            time.sleep(delay)
            retry_keyboard = get_main_keyboard(ctx, is_retry_available=True)
            await context.bot.send_message(chat_id=chat_id,
                                           text=f"❌ Failed to complete *{step_name}* after internal retries. Please try again.",
                                           reply_markup=retry_keyboard, parse_mode='Markdown')
        else:
            log_error(f"An error occurred during step {step_name} for chat {chat_id}, run_id {run_id}: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Error in step *{step_name}*:\n`{e}`",
                                           parse_mode='Markdown')
            del pipeline_runs[chat_id]
            _delete_context_from_minio(run_id)
            if chat_id in step_retry_counts and step_name in step_retry_counts[chat_id]:
                del step_retry_counts[chat_id][step_name]


async def _send_folder_as_zip(context: ContextTypes.DEFAULT_TYPE, chat_id: int, folder_path: str, zip_filename: str):
    """
    Архивирует папку в ZIP, загружает в MinIO и отправляет пользователю с именем {run_id}_autotests.zip.
    """
    if not os.path.isdir(folder_path):
        log_error(f"Folder not found for zipping: {folder_path}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Папка для архивации не найдена: {folder_path}")
        return

    tmp_zip_path = ""
    try:
        # Создаём временный ZIP-файл (без имени)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_zip_path = tmp.name

        # Архивируем папку
        shutil.make_archive(tmp_zip_path.replace(".zip", ""), 'zip', folder_path)

        # Определяем run_id из пути
        try:
            run_id = folder_path.split(os.sep)[-2]
        except IndexError:
            run_id = "unknown"

        # Имя файла с run_id
        final_zip_name = f"{run_id}_{zip_filename}"

        # === ЗАГРУЖАЕМ В MINIO ===
        with open(tmp_zip_path, 'rb') as f:
            zip_content = f.read()
        minio_path = f"{run_id}/{zip_filename}"
        upload(MINIO_CONTEXT_BUCKET, minio_path, zip_content)

        # === ОТПРАВЛЯЕМ В TELEGRAM ===
        # Создаём временный файл с нужным именем
        temp_dir = tempfile.mkdtemp()
        final_zip_path = os.path.join(temp_dir, final_zip_name)

        # Копируем содержимое
        with open(final_zip_path, 'wb') as dst:
            with open(tmp_zip_path, 'rb') as src:
                dst.write(src.read())

        with open(final_zip_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                caption=f"📦 Autotests Archive: `{final_zip_name}`",
                parse_mode='Markdown'
            )

    except Exception as e:
        log_error(f"Failed to create/send/upload ZIP from {folder_path}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Не удалось создать или отправить архив: {zip_filename}"
        )
    finally:
        # Удаляем временные файлы
        if tmp_zip_path and os.path.exists(tmp_zip_path):
            os.unlink(tmp_zip_path)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def _send_step_artifacts_if_available(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str):
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]

    sent_count = 0

    if step_name == "Generating Scenarios":
        if ctx.get("scenarios"):
            await _send_content_as_file_from_minio(context, chat_id, run_id, "scenarios.txt", "🧠 Generated Scenarios", ctx["scenarios"])
            sent_count += 1

    elif step_name == "PII Masking":
        if ctx.get("masked_scenarios"):
            await _send_content_as_file_from_minio(context, chat_id, run_id, "masked_scenarios.txt", "🔒 PII Masked Scenarios", ctx["masked_scenarios"])
            sent_count += 1

    elif step_name == "Generating Test Cases":
        if ctx.get("testcases_json"):
            testcases_str = json.dumps(ctx["testcases_json"], indent=2, ensure_ascii=False)
            await _send_content_as_file_from_minio(context, chat_id, run_id, "testcases.json", "📋 Generated Test Cases (JSON)", testcases_str)
            sent_count += 1

    elif step_name == "Generating Autotests":
        if ctx.get("autotests_dir"):
            await _send_folder_as_zip(context, chat_id, ctx["autotests_dir"], "autotests.zip")
            sent_count += 1

    elif step_name == "Checking Code Quality":
        report_path = ctx.get("code_quality_report")
        if report_path and os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
            await _send_content_as_file_from_minio(
                context, chat_id, run_id,
                "code_quality_report.txt",
                "🧹 Code Quality Report",
                content
            )
            sent_count += 1

    elif step_name == "Performing AI Code Review":
        review_files = ctx.get("ai_code_reviews", [])
        for review_path in review_files:
            if os.path.exists(review_path):
                with open(review_path, "r", encoding="utf-8") as f:
                    content = f.read()
                filename = os.path.basename(review_path)
                await _send_content_as_file_from_minio(
                    context, chat_id, run_id,
                    filename,
                    f"🤖 AI Code Review: {filename}",
                    content
                )
                sent_count += 1


    elif step_name == "Running Autotests":
        sent = 0
        # Сводка
        summary = ctx.get("test_summary", {})
        if summary and "error" not in summary:
            total = summary["total"]
            passed = summary["passed"]
            failed = summary["failed"]
            errors = summary["errors"]
            skipped = summary["skipped"]
            status_emoji = "✅" if (failed == 0 and errors == 0) else "⚠️"
            summary_text = (
                f"{status_emoji} *🧪 Test Run Summary*\n"
                f"Run ID: `{run_id}`\n"
                f"Total: {total}\n"
                f"Passed: ✅ {passed}\n"
                f"Failed: ❌ {failed}\n"
                f"Errors: 🚨 {errors}\n"
                f"Skipped: ➖ {skipped}"
            )
            await context.bot.send_message(chat_id=chat_id, text=summary_text, parse_mode="Markdown")
            sent += 1

        # HTML-отчёт (с Run ID в имени)
        if ctx.get("test_report_html"):
            with open(ctx["test_report_html"], "rb") as f:

                # Создаём временный файл с Run ID в имени
                temp_dir = tempfile.mkdtemp()
                final_name = f"{run_id}_test_report.html"
                final_path = os.path.join(temp_dir, final_name)

                with open(final_path, 'wb') as dst:
                    dst.write(f.read())

                # Отправляем
                with open(final_path, 'rb') as f:
                    await context.bot.send_document(chat_id, f, caption=f"📊 HTML Test Report ({final_name})")

                shutil.rmtree(temp_dir)
            sent += 1

        else:
            await context.bot.send_message(chat_id, text="⚠️ HTML report not generated (missing pytest-html)")

        # Лог (с Run ID в имени)

        if ctx.get("test_run_log"):

            with open(ctx["test_run_log"], "r", encoding="utf-8") as f:

                log_content = f.read()

            if len(log_content) < 3500:

                await context.bot.send_message(

                    chat_id,

                    text=f"📋 *Test Log*\n```\n{log_content}\n```",

                    parse_mode="Markdown"

                )

            else:

                # Создаём временный файл с Run ID в имени

                temp_dir = tempfile.mkdtemp()

                final_name = f"{run_id}_test_run.log"

                final_path = os.path.join(temp_dir, final_name)

                with open(final_path, 'w', encoding='utf-8') as dst:

                    dst.write(log_content)

                with open(final_path, 'rb') as f:

                    await context.bot.send_document(chat_id, f, caption=f"📋 Full Test Log ({final_name})")

                shutil.rmtree(temp_dir)

            sent += 1

        if sent > 0:
            sent_count += sent

    elif step_name == "Generating QA Summary":
        if ctx.get("qa_summary_report"):
            with open(ctx["qa_summary_report"], "r", encoding="utf-8") as f:
                content = f.read()
            await _send_content_as_file_from_minio(
                context, chat_id, run_id,
                "qa_summary.txt",
                "📊 QA Summary Report",
                content
            )
            sent_count += 1

    elif step_name == "Generating Bug Report":
        if ctx.get("bug_report"):
            with open(ctx["bug_report"], "r", encoding="utf-8") as f:
                content = f.read()
            filename = os.path.basename(ctx["bug_report"])
            await _send_content_as_file_from_minio(context, chat_id, run_id, filename, f"🐞 Bug Report: {filename}",
                                                   content)
            sent_count += 1

    if sent_count > 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📤 Finished sending {sent_count} artifact(s) for *{step_name}*.",
            parse_mode='Markdown'
        )

async def _send_content_as_file_from_minio(context: ContextTypes.DEFAULT_TYPE, chat_id: int, run_id: str, filename: str,
                                           caption: str, content: str):
    """Helper to send string content as a file to the user from MinIO artifacts."""
    minio_path = f"{run_id}/{filename}"
    temp_dir = None
    try:
        # Upload to MinIO
        upload(MINIO_CONTEXT_BUCKET, minio_path, content.encode('utf-8'))

        # Create a temporary directory and file with run_id prefix
        temp_dir = tempfile.mkdtemp()
        prefixed_filename = f"{run_id}_{filename}"
        temp_file_path = os.path.join(temp_dir, prefixed_filename)

        with open(temp_file_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        # Send the file with the correct name
        with open(temp_file_path, 'rb') as f:
            await context.bot.send_document(chat_id=chat_id, document=f, caption=caption)

    except Exception as e:
        log_error(f"Failed to send and/or upload content artifact {filename} for run_id {run_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Could not send artifact: {filename}")
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


async def cancel_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    run_id = query.data.split('_')[-1]

    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        if chat_id in step_retry_counts:
            del step_retry_counts[chat_id]
        _delete_context_from_minio(run_id)
        await query.edit_message_text(text="❌ Pipeline cancelled.")
    else:
        await query.edit_message_text(text="No active pipeline to cancel or incorrect run_id.")


async def close_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    run_id = query.data.split('_')[-1]

    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        if chat_id in step_retry_counts:
            del step_retry_counts[chat_id]
        _delete_context_from_minio(run_id)
    await query.edit_message_text(text="✅ Pipeline closed. You can now start a new one by uploading a file.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 Welcome to the AI QA Pipeline Bot!\n\n📤 Please upload a .txt file with your checklist for the **SauceDemo login page** (https://www.saucedemo.com/) to begin."
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("run_step_") or data.startswith("retry_step_"):
        await run_next_step(update, context)
    elif data.startswith("download_artifacts_"):
        await send_artifacts(update, context)
    elif data.startswith("cancel_pipeline_"):
        await cancel_pipeline(update, context)
    elif data.startswith("close_pipeline_"):
        await close_pipeline(update, context)


if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()