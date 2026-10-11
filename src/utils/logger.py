
import logging

from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

LOG_FILE = LOG_DIR / "github_api.log"

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "%(name)s | "
    "%(message)s"
)


def get_logger(
    name: str,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Creates and configures an application logger.

    Features:
        - Console logging
        - File logging
        - Log rotation
        - Configurable logging level
        - Duplicate handler prevention

    Args:
        name: Logger name.
        level: Logging level.

    Returns:
        logging.Logger: Configured logger instance.
    """

    logger = logging.getLogger(name)

    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        LOG_FORMAT
    )

    # Console handler
    console_handler = logging.StreamHandler()

    console_handler.setLevel(level)

    console_handler.setFormatter(
        formatter
    )

    # Rotating file handler
    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )

    file_handler.setLevel(level)

    file_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        console_handler
    )

    logger.addHandler(
        file_handler
    )

    # Prevent duplicate logs through root logger.
    logger.propagate = False

    return logger
