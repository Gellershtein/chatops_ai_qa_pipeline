import logging
import os

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=os.path.join(log_dir, "errors.log"),
    filemode="a"
)

def log_error(message):
    logging.error(message)
