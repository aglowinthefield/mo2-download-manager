﻿import logging
import os
from pathlib import Path

logger: logging.Logger = logging.getLogger("DownloadManager")

def create_logger() -> None:
    """
    Creates a logger with a file handler and sets it to the DEBUG level.
    Removes all existing handlers from the logger.
    """
    # Remove all existing handlers from the logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    script_dir: str = os.path.dirname(os.path.abspath(__file__))
    logs_dir: str = os.path.abspath(os.path.join(script_dir, "..", "..", "logs"))
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    log_path: str = os.path.abspath(os.path.join(logs_dir, "DownloadManager.log"))
    with open(log_path, "w") as _:
        pass

    # Create a file handler that logs messages to "logs\PageFileManager.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="w")

    # Set the format of the log messages
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s")
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)

    # Set the logger to the DEBUG level
    logger.setLevel(logging.DEBUG)