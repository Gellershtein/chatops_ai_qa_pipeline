from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
import tempfile
import json # Import json for serialization
from pipeline.runner import initialize_pipeline, PIPELINE_STEPS
from storage.minio_client import upload, upload_json, download_json # Import new functions
from logs.logger import log_error

# Map chat_id to run_id for ongoing pipelines
pipeline_runs = {}

MINIO_CONTEXT_BUCKET = os.getenv("MINIO_BUCKET", "qa-pipeline")
MINIO_CONTEXT_PREFIX = "contexts" # Prefix for storing context files in MinIO

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
        from models.requirement import Requirement # Import Requirement model dynamically
        loaded_ctx["requirements"] = [Requirement(**req_dict) for req_dict in loaded_ctx["requirements"]]
    
    return loaded_ctx

def _delete_context_from_minio(run_id: str):
    """Deletes the pipeline context from MinIO."""
    try:
        # Note: MinIO client does not have a direct delete_object method in this client version.
        # This would require more advanced MinIO client operations or setting up object lifecycle rules.
        # For simplicity, we'll just remove the entry from pipeline_runs for now.
        # In a real-world scenario, you'd use client.remove_object(bucket_name, object_name)
        pass # Leaving this for future implementation with proper MinIO object deletion
    except Exception as e:
        log_error(f"Failed to delete context for run_id {run_id} from MinIO: {e}")


def get_main_keyboard(ctx):
    """Creates the main inline keyboard with the current step status."""
    step_index = ctx.get("step_index", 0)
    run_id = ctx.get("run_id")
    buttons = []

    if step_index < len(PIPELINE_STEPS):
        step_name, _ = PIPELINE_STEPS[step_index]
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

    # Removed "Download Artifacts" button as per user's request for automated sending.
    return InlineKeyboardMarkup(buttons)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles file upload and initializes the pipeline."""
    chat_id = update.effective_chat.id
    
    if chat_id in pipeline_runs:
        await context.bot.send_message(
            chat_id=chat_id, text="A pipeline is already in progress. Please wait for it to finish or cancel it."
        )
        return

    doc = update.message.document
    if not doc.file_name.endswith((".txt", ".json")):
        await context.bot.send_message(
            chat_id=chat_id, text="Please upload a .txt or .json file."
        )
        return

    try:
        file = await doc.get_file()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, doc.file_name)
            await file.download_to_drive(file_path)
            
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
            
        # Upload to MinIO using configurable bucket name
        upload(MINIO_CONTEXT_BUCKET, doc.file_name, content_bytes)

        # Initialize pipeline
        ctx = initialize_pipeline(doc.file_name)
        pipeline_runs[chat_id] = ctx["run_id"] # Store only run_id

        _save_context_to_minio(ctx) # Persist context to MinIO

        keyboard = get_main_keyboard(ctx)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Pipeline initialized for `{doc.file_name}` with Run ID: `{ctx['run_id']}`.\nReady to start the first step.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        log_error(f"Error in handle_file for chat {chat_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"An error occurred during initialization: `{e}`", parse_mode='Markdown')

async def run_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs the next step in the pipeline."""
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    # Extract run_id from callback_data
    run_id = query.data.split('_')[-1]

    # Load context from MinIO
    try:
        ctx = _load_context_from_minio(run_id)
        pipeline_runs[chat_id] = run_id # Ensure pipeline_runs is updated
    except Exception as e:
        log_error(f"Failed to load context for run_id {run_id}: {e}")
        await query.edit_message_text(text="Pipeline state not found or corrupted. Please upload a file again.")
        if chat_id in pipeline_runs:
            del pipeline_runs[chat_id]
        return

    step_index = ctx.get("step_index", 0)

    if step_index >= len(PIPELINE_STEPS):
        await query.edit_message_text(text="Pipeline already completed.")
        del pipeline_runs[chat_id] # Clean up state
        _delete_context_from_minio(run_id)
        return

    try:
        step_name, step_function = PIPELINE_STEPS[step_index]
        await context.bot.send_message(chat_id=chat_id, text=f"Running step: *{step_name}*...", parse_mode='Markdown')
        
        step_function(ctx) # This is a synchronous call
        
        ctx["step_index"] += 1
        _save_context_to_minio(ctx) # Persist updated context

        # Automated file sending after each step (if applicable)
        await _send_step_artifacts_if_available(update, context, ctx, step_name)

        next_keyboard = get_main_keyboard(ctx)
        
        if ctx["step_index"] < len(PIPELINE_STEPS):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Step *{step_name}* completed.\nReady for the next step.",
                reply_markup=next_keyboard,
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(chat_id=chat_id, text="🎉 Pipeline finished successfully!", reply_markup=next_keyboard)

    except Exception as e:
        log_error(f"An error occurred during step {step_name} for chat {chat_id}, run_id {run_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"An error occurred during step *{step_name}*:\n`{e}`", parse_mode='Markdown')
        del pipeline_runs[chat_id] # Clean up state on error
        _delete_context_from_minio(run_id)


async def _send_step_artifacts_if_available(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: dict, step_name: str):
    """Automatically sends relevant artifacts after a step completes."""
    chat_id = update.effective_chat.id
    run_id = ctx["run_id"]

    sent_count = 0
    # Define which artifacts are expected from which step
    if step_name == "Generating Scenarios":
        if ctx.get("scenarios"):
            await _send_content_as_file_from_minio(context, chat_id, run_id, "scenarios.txt", "Generated Scenarios", ctx["scenarios"])
            sent_count += 1
    elif step_name == "PII Masking":
        if ctx.get("masked_scenarios"):
            await _send_content_as_file_from_minio(context, chat_id, run_id, "masked_scenarios.txt", "PII Masked Scenarios", ctx["masked_scenarios"])
            sent_count += 1
    elif step_name == "Generating Test Cases":
        if ctx.get("testcases_json"):
            await _send_content_as_file_from_minio(context, chat_id, run_id, "testcases.json", "Generated Test Cases (JSON)", ctx["testcases_json"])
            sent_count += 1
    # Add other steps and their associated artifacts here

    if sent_count > 0:
        await context.bot.send_message(chat_id=chat_id, text=f"Finished sending {sent_count} artifact(s) for *{step_name}*.", parse_mode='Markdown')

async def _send_content_as_file_from_minio(context: ContextTypes.DEFAULT_TYPE, chat_id: int, run_id: str, filename: str, caption: str, content: str):
    """Helper to send string content as a file to the user from MinIO artifacts."""
    minio_path = f"{run_id}/{filename}"
    tmp_file_path = ""
    try:
        # Assuming content is already available in ctx for now, but in future this might download from MinIO artifact path
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=f"_{filename}") as tmp:
            tmp.write(content.encode('utf-8'))
            tmp_file_path = tmp.name
        
        with open(tmp_file_path, 'rb') as f:
            await context.bot.send_document(chat_id=chat_id, document=f, caption=caption)
        
        # Also upload to MinIO for history (if not already done by upload_artifacts.run)
        upload(MINIO_CONTEXT_BUCKET, minio_path, content.encode('utf-8'))
    except Exception as e:
        log_error(f"Failed to send and/or upload content artifact {filename} for run_id {run_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Could not send artifact: {filename}")
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


async def send_artifacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends all generated artifacts to the user (can be triggered by a final 'Download All' button if needed)."""
    # This function is now largely redundant with automated sending, but kept for completeness or future use.
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    # Extract run_id from callback_data (if this function were to be called by a button)
    # run_id = query.data.split('_')[-1] if '_' in query.data else None
    # Assuming run_id is in pipeline_runs for now if this is manually triggered
    run_id = pipeline_runs.get(chat_id)

    if not run_id:
        await context.bot.send_message(chat_id=chat_id, text="Pipeline state not found. Please upload a file again.")
        return
    
    try:
        ctx = _load_context_from_minio(run_id)
    except Exception as e:
        log_error(f"Failed to load context for run_id {run_id} in send_artifacts: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Error loading pipeline state. Please upload a file again.")
        return

    # Call the existing upload_artifacts.run (which saves to MinIO)
    # and then send from MinIO, or directly send from ctx.
    # For now, we assume _send_step_artifacts_if_available handles sending.
    # This method could be used to gather ALL artifacts at once.
    await context.bot.send_message(chat_id=chat_id, text="All artifacts are sent automatically after each relevant step now.")

    # Re-evaluate if this function is still needed, or how it should work with automated sending.
    # For now, it will just inform the user.


async def cancel_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the current pipeline run."""
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    run_id = query.data.split('_')[-1] # Extract run_id from callback_data

    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        _delete_context_from_minio(run_id)
        await query.edit_message_text(text="Pipeline cancelled.")
    else:
        await query.edit_message_text(text="No active pipeline to cancel or incorrect run_id.")


async def close_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Closes a finished pipeline view."""
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()
    
    run_id = query.data.split('_')[-1] # Extract run_id from callback_data

    if chat_id in pipeline_runs and pipeline_runs[chat_id] == run_id:
        del pipeline_runs[chat_id]
        _delete_context_from_minio(run_id)
    await query.edit_message_text(text="Pipeline closed. You can now start a new one by uploading a file.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Welcome to the AI QA Pipeline Bot!\n\nPlease upload a .txt or .json file with your requirements to begin."
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses."""
    query = update.callback_query
    data = query.data
    
    if data.startswith("run_step_"):
        await run_next_step(update, context)
    elif data.startswith("download_artifacts_"): # This case is largely deprecated now
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