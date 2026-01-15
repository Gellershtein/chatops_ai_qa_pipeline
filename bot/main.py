"""
This module serves as the entry point for the Telegram bot application.
It initializes the bot, registers all command and message handlers, and starts the polling process.
"""
import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from bot.handlers import (
    start,
    handle_file,
    button_handler
)

def main() -> None:
    """
    Starts the Telegram bot.
    Initializes the ApplicationBuilder with the bot token, registers handlers for
    the /start command, file uploads, and inline keyboard button clicks,
    then begins polling for updates.
    """
    # Create artifacts directory if it doesn't exist
    os.makedirs("artifacts", exist_ok=True)

    # Build the Application using the bot token from environment variables
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Register handlers for different types of updates
    app.add_handler(CommandHandler("start", start)) # Handles the /start command
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file)) # Handles all document uploads
    app.add_handler(CallbackQueryHandler(button_handler)) # Handles inline keyboard button presses

    # Start the bot's polling mechanism to listen for updates
    app.run_polling()

if __name__ == "__main__":
    # Ensures that main() is called only when the script is executed directly
    main()