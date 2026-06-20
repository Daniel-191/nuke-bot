import logging
from datetime import datetime
from pathlib import Path


def setup_logging():
    """Set up logging to file and console."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_filename = log_dir / f'bot_{datetime.now().strftime("%Y-%m-%d")}.log'

    logger = logging.getLogger("NukeBot")
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return logger
