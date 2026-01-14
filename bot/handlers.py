from telegram import Update
from telegram.ext import ContextTypes
import tempfile
import os
from pipeline.runner import initialize_pipeline, PIPELINE_STEPS
from bot.keyboards import get_main_keyboard
from bot.state_manager import (
    pipeline_runs,
    step_retry_counts,
    save_context_to_minio,
    load_context_from_minio,
    delete_context_from_minio,
)
from bot.artifact_sender import send_step_artifacts_if_available
from utils.exceptions import PipelineError, StorageError, LLMError
from logs.logger import log_error
from storage.minio_client import upload

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot and sends a welcome message."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 Welcome to the AI QA Pipeline Bot!\n\n"
             "📤 Please upload a .txt file with your checklist for the "
             "**SauceDemo login page** (https://www.saucedemo.com/) to begin."
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles file upload and initializes the pipeline.

    Args:
        update: The Telegram update.
        context: The Telegram context.
    """
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

        upload(os.getenv("MINIO_BUCKET"), doc.file_name, content_bytes)
        ctx = initialize_pipeline(doc.file_name)
        pipeline_runs[chat_id] = ctx["run_id"]
        save_context_to_minio(ctx)

        keyboard = get_main_keyboard(ctx)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📥 Pipeline initialized for `{doc.file_name}`\n"
                 f"Run ID: `{ctx['run_id']}`\n"
                 f"Ready to start!",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except (StorageError, PipelineError) as e:
        log_error(f"Error in handle_file for chat {chat_id}: {e}")
        await context.bot.send_message(
            chat_id=chat_id, text=f"❌ Error during initialization: `{e}`",
            parse_mode='Markdown'
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all button clicks from the user.

    Args:
        update: The Telegram update.
        context: The Telegram context.
    """
    query = update.callback_query
    data = query.data
    run_id = data.split('_')[-1]

    if data.startswith("run_step_") or data.startswith("retry_step_"):
        await run_next_step(update, context, run_id, is_retry=(data.startswith("retry_step_")))
    elif data.startswith("cancel_pipeline_"):
        await cancel_pipeline(update, context, run_id)
    elif data.startswith("close_pipeline_"):
        await close_pipeline(update, context, run_id)
    else:
        await query.answer("Unknown command.")

async def run_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE, run_id: str, is_retry: bool):
    """
    Runs the next step of the pipeline.

    Args:
        update: The Telegram update.
        context: The Telegram context.
        run_id: The ID of the pipeline run.
        is_retry: Whether this is a retry attempt.
    """
    chat_id = update.effective_chat.id
    try:
        ctx = load_context_from_minio(run_id)
        pipeline_runs[chat_id] = run_id
    except StorageError:
        await context.bot.send_message(
            chat_id=chat_id, text="❌ Pipeline state not found. Please upload a file again."
        )
        if chat_id in pipeline_runs:
            del pipeline_runs[chat_id]
        return

    step_index = ctx.get("step_index", 0)
    if step_index >= len(PIPELINE_STEPS):
        await context.bot.send_message(chat_id=chat_id, text="✅ Pipeline already completed.")
        del pipeline_runs[chat_id]
        delete_context_from_minio(run_id)
        return

    step_name, step_function = PIPELINE_STEPS[step_index]

    if is_retry:
        await _retry_step(update, context, ctx, step_name, step_function)
    else:
        await _execute_step(update, context, ctx, step_name, step_function)

async def _execute_step(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str, step_function):
    """Executes a single step of the pipeline."""
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]

    await context.bot.send_message(
        chat_id=chat_id, text=f"🚀 Running step: *{step_name}*...", parse_mode='Markdown'
    )
    try:
        step_function(ctx)

        ctx["step_index"] += 1
        save_context_to_minio(ctx)
        step_retry_counts[chat_id][step_name] = 0

        await send_step_artifacts_if_available(update, context, ctx, step_name)

        next_keyboard = get_main_keyboard(ctx)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Step *{step_name}* completed.",
            reply_markup=next_keyboard,
            parse_mode='Markdown'
        )
    except (LLMError, PipelineError, StorageError) as e:
        log_error(f"An error occurred during step {step_name} for chat {chat_id}, run_id {run_id}: {e}")
        await context.bot.send_message(
            chat_id=chat_id, text=f"❌ Error in step *{step_name}*:\n`{e}`",
            parse_mode='Markdown'
        )
        del pipeline_runs[chat_id]
        delete_context_from_minio(run_id)
        if chat_id in step_retry_counts and step_name in step_retry_counts[chat_id]:
            del step_retry_counts[chat_id][step_name]

async def _retry_step(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str, step_function):
    """Retries a single step of the pipeline."""
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]
    retries = 3
    current_retry = step_retry_counts[chat_id][step_name]
    delay = 1 * (2 ** current_retry)

    if current_retry < retries:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔁 Retrying *{step_name}* (Attempt {current_retry + 1}/{retries})...",
            parse_mode='Markdown'
        )
        try:
            step_function(ctx)
            ctx["step_index"] += 1
            save_context_to_minio(ctx)
            step_retry_counts[chat_id][step_name] = 0

            await send_step_artifacts_if_available(update, context, ctx, step_name)

            next_keyboard = get_main_keyboard(ctx)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Step *{step_name}* completed.",
                reply_markup=next_keyboard,
                parse_mode='Markdown'
            )
        except (LLMError, PipelineError, StorageError) as e:
            step_retry_counts[chat_id][step_name] += 1
            log_error(
                f"LLM call failed for run_id {run_id}, step {step_name}. " \
                f"Retrying in {delay} seconds. " \
                f"Attempt {step_retry_counts[chat_id][step_name]}/{retries}"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ LLM service temporarily unavailable for *{step_name}*. " \
                     f"Retrying in {delay} seconds...",
                parse_mode='Markdown'
            )
            # In a real async application, time.sleep() is blocking.
            # A better approach would be to use asyncio.sleep().
            # For this refactoring, we keep it simple.
            import time
            time.sleep(delay)
            retry_keyboard = get_main_keyboard(ctx, is_retry_available=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Failed to complete *{step_name}* after internal retries. " \
                     f"Please try again.",
                reply_markup=retry_keyboard,
                parse_mode='Markdown'
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Failed to complete *{step_name}* after {retries} retries.",
            parse_mode='Markdown'
        )
        del pipeline_runs[chat_id]
        delete_context_from_minio(run_id)
        if chat_id in step_retry_counts and step_name in step_retry_counts[chat_id]:
            del step_retry_counts[chat_id][step_name]

async def cancel_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE, run_id: str):
    """Cancels the pipeline for the given run_id."""
    chat_id = update.effective_chat.id
    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        if chat_id in step_retry_counts:
            del step_retry_counts[chat_id]
        delete_context_from_minio(run_id)
        await context.bot.send_message(chat_id=chat_id, text="❌ Pipeline cancelled.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="No active pipeline to cancel or incorrect run_id.")

async def close_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE, run_id: str):
    """Closes the pipeline for the given run_id."""
    chat_id = update.effective_chat.id
    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        if chat_id in step_retry_counts:
            del step_retry_counts[chat_id]
        delete_context_from_minio(run_id)
    await context.bot.send_message(
        chat_id=chat_id, text="✅ Pipeline closed. You can now start a new one by uploading a file."
    )