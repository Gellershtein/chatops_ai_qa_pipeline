"""
This module is responsible for generating Telegram inline keyboards used to control the AI QA pipeline.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pipeline.runner import PIPELINE_STEPS

def get_main_keyboard(ctx: dict, is_retry_available: bool = False) -> InlineKeyboardMarkup:
    """
    Creates and returns the main inline keyboard for the Telegram bot,
    displaying buttons relevant to the current state of the pipeline (e.g., Run next step, Retry, Cancel, Close).

    Args:
        ctx (dict): The current pipeline context dictionary, containing 'step_index' and 'run_id'.
        is_retry_available (bool): A flag indicating whether a "Retry" button should be shown
                                   for the current step. Defaults to False.

    Returns:
        InlineKeyboardMarkup: An InlineKeyboardMarkup object representing the main control keyboard.
    """
    step_index = ctx.get("step_index", 0)
    run_id = ctx.get("run_id")
    buttons = []

    # If there are more steps to run
    if step_index < len(PIPELINE_STEPS):
        step_name, _ = PIPELINE_STEPS[step_index]
        if is_retry_available:
            # Add a retry button if retry is available
            buttons.append(
                [InlineKeyboardButton(f"🔁 Retry: {step_name}", callback_data=f"retry_step_{run_id}")]
            )
        else:
            # Add a run button for the current step
            buttons.append(
                [InlineKeyboardButton(f"▶️ Run: {step_name}", callback_data=f"run_step_{run_id}")]
            )
        # Always allow cancellation of an ongoing pipeline
        buttons.append(
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_pipeline_{run_id}")]
        )
    else:
        # If all steps are completed, show a close button
        buttons.append(
            [InlineKeyboardButton("🎉 Close Pipeline", callback_data=f"close_pipeline_{run_id}")]
        )

    return InlineKeyboardMarkup(buttons)