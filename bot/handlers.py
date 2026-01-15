"""
This module contains the Telegram bot's handler functions for various commands and messages.
It manages the interaction with users, file uploads, pipeline execution, and state management.
"""
import os
from telegram import Update, InputFile
from telegram.ext import ContextTypes
import tempfile
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /start command. Sends a welcome message, a brief description of the bot,
    and an example checklist file with instructions.

    Args:
        update (Update): The Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 Welcome to the AI QA Pipeline Bot!\n\n"
             "This bot automates the process of generating scenarios, test cases, and autotests for *SauceDemo login page*.\n\n"
             "📤 Please upload a .txt file with your checklist for the "
             "**SauceDemo login page** (https://www.saucedemo.com/) to begin or use the example below"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⚠️ Here is an example checklist you can use to start: just forward it back to me in this chat to proceed.",
        parse_mode='Markdown'
    )
    # Send the example file directly from its path
    with open("examples/checklist_login.txt", 'rb') as f:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=InputFile(f, filename="checklist_login.txt"),
            caption="📤 checklist_login.txt"
        )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles uploaded files, particularly expecting .txt files for checklist processing.
    It prevents concurrent pipeline runs, validates file type, downloads and uploads the file
    to Minio, initializes a new pipeline run, and sends feedback to the user with control buttons.

    Args:
        update (Update): The Telegram update object containing the message with the document.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.

    Raises:
        StorageError: If there's an issue with Minio storage operations.
        PipelineError: If there's an issue during pipeline initialization.
    """
    chat_id = update.effective_chat.id
    if chat_id in pipeline_runs:
        await context.bot.send_message(
            chat_id=chat_id, text="🔄 A pipeline is already in progress. Please wait or cancel it."
        )
        return

    doc = update.message.document
    if not doc.file_name.endswith((".txt")):
        await context.bot.send_message(
            chat_id=chat_id, text="📄 Please upload a .txt file (e.g., your checklist)."
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


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all incoming callback queries (button clicks) from the user.
    It parses the callback data to determine the action to take (e.g., run a step,
    cancel, or close the pipeline) and delegates to the appropriate handler function.

    Args:
        update (Update): The Telegram update object containing the callback query.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
    """
    query = update.callback_query
    data = query.data
    # Extract the run_id from the callback data, which is appended at the end
    run_id = data.split('_')[-1]

    if data.startswith("run_step_") or data.startswith("retry_step_"):
        # Determine if it's a retry attempt based on the callback data prefix
        await run_next_step(update, context, run_id, is_retry=(data.startswith("retry_step_")))
    elif data.startswith("cancel_pipeline_"):
        await cancel_pipeline(update, context, run_id)
    elif data.startswith("close_pipeline_"):
        await close_pipeline(update, context, run_id)
    else:
        # Answer the callback query to dismiss the loading animation on the client side
        await query.answer("Unknown command.")

async def run_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE, run_id: str, is_retry: bool) -> None:
    """
    Manages the execution of the next step in the pipeline or retries the current step.
    It loads the pipeline's state, checks if the pipeline is completed, and then
    calls either `_execute_step` or `_retry_step` based on the `is_retry` flag.

    Args:
        update (Update): The Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
        run_id (str): The unique identifier for the current pipeline run.
        is_retry (bool): A flag indicating if the current call is a retry attempt for a step.
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
            # Clean up the entry if state is not found
            del pipeline_runs[chat_id]
        return

    step_index = ctx.get("step_index", 0)
    if step_index >= len(PIPELINE_STEPS):
        await context.bot.send_message(chat_id=chat_id, text="✅ Pipeline already completed.")
        # Clean up pipeline run and context as it's completed
        del pipeline_runs[chat_id]
        delete_context_from_minio(run_id)
        return

    step_name, step_function = PIPELINE_STEPS[step_index]

    if is_retry:
        await _retry_step(update, context, ctx, step_name, step_function)
    else:
        await _execute_step(update, context, ctx, step_name, step_function)

async def _execute_step(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str, step_function) -> None:
    """
    Executes a single, non-retried step of the pipeline. It sends a "running" message,
    calls the step's function, updates the pipeline context, saves it, sends artifacts,
    and then sends a "completed" message with the next set of control buttons.
    Handles various exceptions that may occur during step execution.

    Args:
        update (Update): The Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
        ctx (dict): The current pipeline context dictionary.
        step_name (str): The name of the step being executed.
        step_function (Callable): The function implementing the logic for the current step.
    """
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]

    await context.bot.send_message(
        chat_id=chat_id, text=f"🚀 Running step: *{step_name}*...", parse_mode='Markdown'
    )
    try:
        step_function(ctx)

        # Advance to the next step
        ctx["step_index"] += 1
        save_context_to_minio(ctx)
        # Reset retry count for this step upon successful completion
        if chat_id in step_retry_counts and step_name in step_retry_counts[chat_id]:
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
        # If an error occurs, the pipeline is considered failed and cleaned up
        if chat_id in pipeline_runs:
            del pipeline_runs[chat_id]
        delete_context_from_minio(run_id)
        if chat_id in step_retry_counts and step_name in step_retry_counts[chat_id]:
            del step_retry_counts[chat_id][step_name]

async def _retry_step(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str, step_function) -> None:
    """
    Attempts to retry a failed pipeline step with an exponential backoff mechanism.
    It tracks retry counts, applies delays between retries, and provides feedback
    to the user about the retry attempts.

    Args:
        update (Update): The Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
        ctx (dict): The current pipeline context dictionary.
        step_name (str): The name of the step being retried.
        step_function (Callable): The function implementing the logic for the step being retried.
    """
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]
    max_retries = 3 # Define maximum number of retries
    
    # Initialize or get current retry count for this chat and step
    if chat_id not in step_retry_counts:
        step_retry_counts[chat_id] = {}
    if step_name not in step_retry_counts[chat_id]:
        step_retry_counts[chat_id][step_name] = 0
    
    current_retry = step_retry_counts[chat_id][step_name]
    
    # Calculate exponential backoff delay (1, 2, 4 seconds)
    delay = 1 * (2 ** current_retry) 

    if current_retry < max_retries:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔁 Retrying *{step_name}* (Attempt {current_retry + 1}/{max_retries})...",
            parse_mode='Markdown'
        )
        try:
            step_function(ctx)

            # If successful, advance to the next step and reset retry count
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
            # Increment retry count on failure
            step_retry_counts[chat_id][step_name] += 1
            log_error(
                f"LLM call failed for run_id {run_id}, step {step_name}. " \
                f"Retrying in {delay} seconds. " \
                f"Attempt {step_retry_counts[chat_id][step_name]}/{max_retries}"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ LLM service temporarily unavailable for *{step_name}*. " \
                     f"Retrying in {delay} seconds...",
                parse_mode='Markdown'
            )
            # Use a blocking sleep for simplicity in this example, but asyncio.sleep()
            # would be preferred in a truly non-blocking async application.
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
        # If max retries reached, inform user and clean up pipeline
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Failed to complete *{step_name}* after {max_retries} retries.",
            parse_mode='Markdown'
        )
        # Clear pipeline state and context
        del pipeline_runs[chat_id]
        delete_context_from_minio(run_id)
        if chat_id in step_retry_counts and step_name in step_retry_counts[chat_id]:
            del step_retry_counts[chat_id][step_name]

async def cancel_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE, run_id: str) -> None:
    """
    Cancels an active pipeline run. It removes the pipeline from active runs,
    clears any associated retry counts, deletes the context from Minio, and
    sends a cancellation confirmation message to the user.

    Args:
        update (Update): The Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
        run_id (str): The unique identifier of the pipeline run to cancel.
    """
    chat_id = update.effective_chat.id
    # Check if the pipeline is active for this chat and matches the run_id
    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        if chat_id in step_retry_counts:
            del step_retry_counts[chat_id]
        delete_context_from_minio(run_id)
        await context.bot.send_message(chat_id=chat_id, text="❌ Pipeline cancelled.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="No active pipeline to cancel or incorrect run_id.")

async def close_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE, run_id: str) -> None:
    """
    Closes a completed or cancelled pipeline, clearing its state and allowing the user
    to start a new one. It removes the pipeline from active runs, clears retry counts,
    deletes the context from Minio, and sends a closure confirmation message.

    Args:
        update (Update): The Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): The context object for the current update.
        run_id (str): The unique identifier of the pipeline run to close.
    """
    chat_id = update.effective_chat.id
    # Check if the pipeline is active for this chat and matches the run_id
    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        if chat_id in step_retry_counts:
            del step_retry_counts[chat_id]
        delete_context_from_minio(run_id)
    await context.bot.send_message(
        chat_id=chat_id, text="✅ Pipeline closed. You can now start a new one by uploading a file."
    )