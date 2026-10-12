import logging
from logging.handlers import RotatingFileHandler

import pytest

import src.utils.logger as logger_module
from src.utils.exceptions import (
    AuthenticationError,
    BadRequestError,
    GitHubAPIError,
    GitHubConnectionError,
    RateLimitError,
    RequestTimeoutError,
    ResourceNotFoundError,
    ServerError,
)


@pytest.mark.parametrize(
    "exception_type",
    [
        BadRequestError,
        AuthenticationError,
        ResourceNotFoundError,
        RateLimitError,
        ServerError,
        RequestTimeoutError,
        GitHubConnectionError,
    ],
)
def test_api_exceptions_share_domain_base(exception_type: type[Exception]) -> None:
    assert issubclass(exception_type, GitHubAPIError)
    assert issubclass(exception_type, Exception)


def test_get_logger_configures_handlers_without_duplicates(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_name = "tests.unique.logger"
    logger = logging.getLogger(logger_name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    monkeypatch.setattr(logger_module, "LOG_FILE", tmp_path / "application.log")

    configured_logger = logger_module.get_logger(logger_name, logging.DEBUG)
    same_logger = logger_module.get_logger(logger_name, logging.WARNING)

    assert configured_logger is same_logger
    assert len(configured_logger.handlers) == 2
    assert configured_logger.level == logging.WARNING
    assert configured_logger.propagate is False
    assert any(
        isinstance(handler, RotatingFileHandler)
        for handler in configured_logger.handlers
    )

    configured_logger.warning("test log entry")
    assert (tmp_path / "application.log").exists()

    for handler in list(configured_logger.handlers):
        configured_logger.removeHandler(handler)
        handler.close()