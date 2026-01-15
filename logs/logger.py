"""
This module sets up a basic logging configuration for the application,
specifically for error messages. It ensures that error logs are written to a file.
"""
import logging
import os

# Define the directory where log files will be stored
log_dir = "logs"
# Create the log directory if it doesn't already exist
os.makedirs(log_dir, exist_ok=True)

# Configure the basic logging settings
# - level: Only messages of ERROR severity and above will be processed.
# - format: Defines the layout of log records.
# - filename: Specifies the file to which log messages will be written.
# - filemode: 'a' means append mode, so new log messages are added to the end of the file.
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=os.path.join(log_dir, "errors.log"),
    filemode="a"
)

def log_error(message: str) -> None:
    """
    Logs an error message to the configured error log file.

    Args:
        message (str): The error message string to be logged.
    """
    logging.error(message)
