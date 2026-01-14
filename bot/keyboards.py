from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pipeline.runner import PIPELINE_STEPS

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