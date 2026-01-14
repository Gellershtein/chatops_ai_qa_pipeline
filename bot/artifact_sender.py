import os
import tempfile
import shutil
import json
from telegram.ext import ContextTypes
from telegram import Update
from storage.minio_client import upload
from logs.logger import log_error

async def send_folder_as_zip(context: ContextTypes.DEFAULT_TYPE, chat_id: int, folder_path: str, zip_filename: str):
    """
    Zips a folder, uploads it to MinIO, and sends it to the user.

    Args:
        context: The Telegram context.
        chat_id: The ID of the chat to send the file to.
        folder_path: The path to the folder to zip.
        zip_filename: The name of the zip file.
    """
    if not os.path.isdir(folder_path):
        log_error(f"Folder not found for zipping: {folder_path}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Folder not found: {folder_path}")
        return

    tmp_zip_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_zip_path = tmp.name

        shutil.make_archive(tmp_zip_path.replace(".zip", ""), 'zip', folder_path)

        try:
            run_id = folder_path.split(os.sep)[-2]
        except IndexError:
            run_id = "unknown"

        final_zip_name = f"{run_id}_{zip_filename}"

        with open(tmp_zip_path, 'rb') as f:
            zip_content = f.read()
        minio_path = f"{run_id}/{zip_filename}"
        upload(os.getenv("MINIO_BUCKET"), minio_path, zip_content)

        temp_dir = tempfile.mkdtemp()
        final_zip_path = os.path.join(temp_dir, final_zip_name)

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
            text=f"⚠️ Failed to create or send the archive: {zip_filename}"
        )
    finally:
        if tmp_zip_path and os.path.exists(tmp_zip_path):
            os.unlink(tmp_zip_path)
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def send_step_artifacts_if_available(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str):
    """
    Sends the artifacts for a given step to the user.

    Args:
        update: The Telegram update.
        context: The Telegram context.
        ctx: The pipeline context.
        step_name: The name of the step.
    """
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]

    sent_count = 0

    if step_name == "Generating Scenarios":
        if ctx.get("scenarios"):
            await send_content_as_file_from_minio(context, chat_id, run_id, "scenarios.txt", "🧠 Generated Scenarios", ctx["scenarios"])
            sent_count += 1

    elif step_name == "PII Masking":
        if ctx.get("masked_scenarios"):
            await send_content_as_file_from_minio(context, chat_id, run_id, "masked_scenarios.txt", "🔒 PII Masked Scenarios", ctx["masked_scenarios"])
            sent_count += 1

    elif step_name == "Generating Test Cases":
        if ctx.get("testcases_json"):
            testcases_str = json.dumps(ctx["testcases_json"], indent=2, ensure_ascii=False)
            await send_content_as_file_from_minio(context, chat_id, run_id, "testcases.json", "📋 Generated Test Cases (JSON)", testcases_str)
            sent_count += 1

    elif step_name == "Generating Autotests":
        if ctx.get("autotests_dir"):
            await send_folder_as_zip(context, chat_id, ctx["autotests_dir"], "autotests.zip")
            sent_count += 1

    elif step_name == "Checking Code Quality":
        report_path = ctx.get("code_quality_report")
        if report_path and os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
            await send_content_as_file_from_minio(
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
                await send_content_as_file_from_minio(
                    context, chat_id, run_id,
                    filename,
                    f"🤖 AI Code Review: {filename}",
                    content
                )
                sent_count += 1


    elif step_name == "Running Autotests":
        sent = 0
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

        if ctx.get("test_report_html"):
            with open(ctx["test_report_html"], "rb") as f:
                temp_dir = tempfile.mkdtemp()
                final_name = f"{run_id}_test_report.html"
                final_path = os.path.join(temp_dir, final_name)

                with open(final_path, 'wb') as dst:
                    dst.write(f.read())

                with open(final_path, 'rb') as f_to_send:
                    await context.bot.send_document(chat_id, f_to_send, caption=f"📊 HTML Test Report ({final_name})")

                shutil.rmtree(temp_dir)
            sent += 1

        else:
            await context.bot.send_message(chat_id, text="⚠️ HTML report not generated (missing pytest-html)")

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
                temp_dir = tempfile.mkdtemp()
                final_name = f"{run_id}_test_run.log"
                final_path = os.path.join(temp_dir, final_name)

                with open(final_path, 'w', encoding='utf-8') as dst:
                    dst.write(log_content)

                with open(final_path, 'rb') as f_to_send:
                    await context.bot.send_document(chat_id, f_to_send, caption=f"📋 Full Test Log ({final_name})")

                shutil.rmtree(temp_dir)
            sent += 1

        if sent > 0:
            sent_count += sent

    elif step_name == "Generating QA Summary":
        if ctx.get("qa_summary_report"):
            with open(ctx["qa_summary_report"], "r", encoding="utf-8") as f:
                content = f.read()
            await send_content_as_file_from_minio(
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
            await send_content_as_file_from_minio(context, chat_id, run_id, filename, f"🐞 Bug Report: {filename}",
                                                   content)
            sent_count += 1

    if sent_count > 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📤 Finished sending {sent_count} artifact(s) for *{step_name}*.",
            parse_mode='Markdown'
        )

async def send_content_as_file_from_minio(context: ContextTypes.DEFAULT_TYPE, chat_id: int, run_id: str, filename: str,
                                           caption: str, content: str):
    """
    Sends string content as a file to the user, uploading it to MinIO first.

    Args:
        context: The Telegram context.
        chat_id: The ID of the chat to send the file to.
        run_id: The ID of the pipeline run.
        filename: The name of the file.
        caption: The caption for the file.
        content: The content of the file.
    """
    minio_path = f"{run_id}/{filename}"
    temp_dir = None
    try:
        upload(os.getenv("MINIO_BUCKET"), minio_path, content.encode('utf-8'))

        temp_dir = tempfile.mkdtemp()
        prefixed_filename = f"{run_id}_{filename}"
        temp_file_path = os.path.join(temp_dir, prefixed_filename)

        with open(temp_file_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        with open(temp_file_path, 'rb') as f:
            await context.bot.send_document(chat_id=chat_id, document=f, caption=caption)

    except Exception as e:
        log_error(f"Failed to send and/or upload content artifact {filename} for run_id {run_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Could not send artifact: {filename}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
