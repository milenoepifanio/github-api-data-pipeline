import logging
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

import src.utils.logger as logger_module


_TEST_LOG_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="github-api-tests-")
)
logger_module.LOG_FILE = _TEST_LOG_DIRECTORY / "github_api.log"


def pytest_unconfigure(config) -> None:
    for logger in logging.Logger.manager.loggerDict.values():
        if not isinstance(logger, logging.Logger):
            continue

        for handler in list(logger.handlers):
            if (
                isinstance(handler, RotatingFileHandler)
                and Path(handler.baseFilename).parent == _TEST_LOG_DIRECTORY
            ):
                logger.removeHandler(handler)
                handler.close()

    for log_file in _TEST_LOG_DIRECTORY.iterdir():
        log_file.unlink(missing_ok=True)

    _TEST_LOG_DIRECTORY.rmdir()