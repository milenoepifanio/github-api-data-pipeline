
import os
import time

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv

from src.api.auth import get_auth_headers
from src.utils.logger import get_logger
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


load_dotenv()

logger = get_logger(__name__)


class GitHubClient:
    """
    HTTP client for interacting with the GitHub REST API.

    Features:
        - Token-based authentication
        - Query parameters
        - Request timeout
        - HTTP error handling
        - Retry for temporary server errors
        - Retry for timeout and connection errors
        - Primary and secondary rate limit detection
        - Retry-After support
        - X-RateLimit-Reset support
        - Exponential backoff
        - Maximum retry wait
        - Pagination URL validation
        - Structured logging
    """

    RETRYABLE_STATUS_CODES = {
        500,
        502,
        503,
        504,
    }

    RATE_LIMIT_MESSAGES = (
        "secondary rate limit",
        "primary rate limit",
        "rate limit exceeded",
        "api rate limit exceeded",
        "abuse detection",
        "too many requests",
    )

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        max_retry_wait: float = 60.0,
    ) -> None:

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries cannot be negative."
            )

        if backoff_factor <= 0:
            raise ValueError(
                "backoff_factor must be greater than zero."
            )

        if max_retry_wait <= 0:
            raise ValueError(
                "max_retry_wait must be greater than zero."
            )

        configured_base_url = (
            base_url
            or os.getenv(
                "GITHUB_BASE_URL",
                "https://api.github.com"
            )
        )

        self.base_url = configured_base_url.rstrip("/")

        parsed_base_url = urlparse(self.base_url)

        if (
            parsed_base_url.scheme != "https"
            or not parsed_base_url.hostname
            or parsed_base_url.username is not None
            or parsed_base_url.password is not None
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise ValueError(
                "GitHub API base URL must be a valid "
                "HTTPS URL without credentials or query."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_retry_wait = max_retry_wait

        self.session = requests.Session()

        self.session.headers.update(
            get_auth_headers()
        )

        # Disable automatic redirects to avoid sending
        # authenticated requests to unexpected hosts.
        self.allow_redirects = False

    # ==================================================
    # PUBLIC HTTP METHODS
    # ==================================================

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None
    ) -> requests.Response:
        """
        Executes a GET request against the GitHub API.
        """

        url = self._build_url(endpoint)

        return self._request(
            url=url,
            params=params
        )

    def get_url(
        self,
        url: str
    ) -> requests.Response:
        """
        Executes a GET request using a complete URL.

        Used mainly for pagination links.
        """

        self._validate_url(url)

        return self._request(
            url=url
        )

    # ==================================================
    # REQUEST EXECUTION
    # ==================================================

    def _request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None
    ) -> requests.Response:
        """
        Executes HTTP GET with retry and backoff.

        max_retries represents additional attempts
        after the initial request.
        """

        self._validate_url(url)

        attempt = 0

        while True:

            try:

                response = self.session.get(
                    url=url,
                    params=params,
                    timeout=self.timeout,
                    allow_redirects=self.allow_redirects
                )

            # ------------------------------------------
            # TIMEOUT
            # ------------------------------------------
            except requests.exceptions.Timeout as error:

                if attempt >= self.max_retries:

                    logger.error(
                        "GitHub API timeout exhausted | "
                        "Attempts=%d",
                        attempt + 1
                    )

                    raise RequestTimeoutError(
                        "GitHub API request timed out "
                        f"after {attempt + 1} attempts."
                    ) from error

                wait_time = self._exponential_backoff(
                    attempt
                )

                logger.warning(
                    "GitHub API request timeout | "
                    "Retry=%d/%d | Wait=%.2fs",
                    attempt + 1,
                    self.max_retries,
                    wait_time
                )

                time.sleep(wait_time)

                attempt += 1

                continue

            # ------------------------------------------
            # CONNECTION ERROR
            # ------------------------------------------
            except requests.exceptions.ConnectionError as error:

                if attempt >= self.max_retries:

                    logger.error(
                        "GitHub API connection retries exhausted | "
                        "Attempts=%d",
                        attempt + 1
                    )

                    raise GitHubConnectionError(
                        "Could not connect to GitHub API "
                        f"after {attempt + 1} attempts."
                    ) from error

                wait_time = self._exponential_backoff(
                    attempt
                )

                logger.warning(
                    "GitHub API connection error | "
                    "Retry=%d/%d | Wait=%.2fs",
                    attempt + 1,
                    self.max_retries,
                    wait_time
                )

                time.sleep(wait_time)

                attempt += 1

                continue

            # ------------------------------------------
            # RATE LIMIT
            # ------------------------------------------
            if self._is_rate_limit_response(response):

                if attempt >= self.max_retries:

                    logger.error(
                        "GitHub API rate limit retries exhausted | "
                        "HTTP=%d | Attempts=%d",
                        response.status_code,
                        attempt + 1
                    )

                    self._handle_response(response)

                wait_time = self._get_rate_limit_wait_time(
                    response=response,
                    attempt=attempt
                )

                if wait_time > self.max_retry_wait:

                    logger.error(
                        "GitHub API rate limit wait exceeds limit | "
                        "Required=%.2fs | Maximum=%.2fs",
                        wait_time,
                        self.max_retry_wait
                    )

                    raise RateLimitError(
                        "GitHub API rate limit requires "
                        f"waiting {wait_time:.2f}s, exceeding "
                        f"the configured maximum of "
                        f"{self.max_retry_wait:.2f}s."
                    )

                logger.warning(
                    "GitHub API rate limit reached | "
                    "HTTP=%d | Retry=%d/%d | Wait=%.2fs",
                    response.status_code,
                    attempt + 1,
                    self.max_retries,
                    wait_time
                )

                time.sleep(wait_time)

                attempt += 1

                continue

            # ------------------------------------------
            # SUCCESS
            # ------------------------------------------
            if 200 <= response.status_code < 300:

                if attempt > 0:

                    logger.info(
                        "GitHub API request recovered | "
                        "HTTP=%d | Retries=%d",
                        response.status_code,
                        attempt
                    )

                return response

            # ------------------------------------------
            # NON-RETRYABLE HTTP ERRORS
            # ------------------------------------------
            if (
                response.status_code
                not in self.RETRYABLE_STATUS_CODES
            ):

                self._handle_response(response)

                return response

            # ------------------------------------------
            # RETRYABLE SERVER ERRORS
            # ------------------------------------------
            if attempt >= self.max_retries:

                logger.error(
                    "GitHub API server retries exhausted | "
                    "HTTP=%d | Attempts=%d",
                    response.status_code,
                    attempt + 1
                )

                self._handle_response(response)

            wait_time = self._exponential_backoff(
                attempt
            )

            logger.warning(
                "GitHub API temporary server error | "
                "HTTP=%d | Retry=%d/%d | Wait=%.2fs",
                response.status_code,
                attempt + 1,
                self.max_retries,
                wait_time
            )

            time.sleep(wait_time)

            attempt += 1

    # ==================================================
    # RETRY AND BACKOFF
    # ==================================================

    def _exponential_backoff(
        self,
        attempt: int
    ) -> float:
        """
        Calculates exponential backoff.

        The result is limited by max_retry_wait.
        """

        wait_time = (
            self.backoff_factor
            * (2 ** attempt)
        )

        return min(
            wait_time,
            self.max_retry_wait
        )

    def _wait_before_retry(
        self,
        attempt: int
    ) -> None:
        """
        Maintained for compatibility with existing code.
        """

        time.sleep(
            self._exponential_backoff(attempt)
        )

    # ==================================================
    # RATE LIMIT WAIT TIME
    # ==================================================

    def _get_rate_limit_wait_time(
        self,
        response: requests.Response,
        attempt: int
    ) -> float:
        """
        Determines retry wait time.

        Priority:
            1. Retry-After
            2. X-RateLimit-Reset
            3. Exponential backoff
        """

        retry_after = response.headers.get(
            "Retry-After"
        )

        if retry_after is not None:

            try:

                return max(
                    float(retry_after),
                    0.0
                )

            except (ValueError, OverflowError):

                try:

                    retry_datetime = (
                        parsedate_to_datetime(retry_after)
                    )

                    if retry_datetime.tzinfo is None:

                        retry_datetime = (
                            retry_datetime.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    return max(
                        retry_datetime.timestamp()
                        - time.time(),
                        0.0
                    )

                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                ):

                    logger.warning(
                        "Invalid Retry-After header ignored"
                    )

        rate_limit_reset = response.headers.get(
            "X-RateLimit-Reset"
        )

        if rate_limit_reset is not None:

            try:

                reset_timestamp = float(
                    rate_limit_reset
                )

                return max(
                    reset_timestamp - time.time(),
                    0.0
                )

            except (ValueError, OverflowError):

                logger.warning(
                    "Invalid X-RateLimit-Reset header ignored"
                )

        return self._exponential_backoff(
            attempt
        )

    # ==================================================
    # HTTP RESPONSE HANDLING
    # ==================================================

    def _handle_response(
        self,
        response: requests.Response
    ) -> None:
        """
        Raises custom exceptions based on HTTP status.
        """

        status_code = response.status_code

        if 200 <= status_code < 300:
            return

        if status_code == 400:

            raise BadRequestError(
                f"GitHub API error [{status_code}]: "
                "Invalid request."
            )

        if status_code == 401:

            raise AuthenticationError(
                f"GitHub API error [{status_code}]: "
                "Authentication failed."
            )

        if status_code == 403:

            if self._is_rate_limit_response(response):

                raise RateLimitError(
                    f"GitHub API error [{status_code}]: "
                    "Rate limit exceeded."
                )

            raise AuthenticationError(
                f"GitHub API error [{status_code}]: "
                "Access forbidden."
            )

        if status_code == 404:

            raise ResourceNotFoundError(
                f"GitHub API error [{status_code}]: "
                "Resource not found."
            )

        if status_code == 429:

            raise RateLimitError(
                f"GitHub API error [{status_code}]: "
                "Rate limit exceeded."
            )

        if 500 <= status_code < 600:

            raise ServerError(
                f"GitHub API error [{status_code}]: "
                "Server error."
            )

        raise GitHubAPIError(
            f"GitHub API error [{status_code}]: "
            "Unexpected response."
        )

    # ==================================================
    # RATE LIMIT IDENTIFICATION
    # ==================================================

    @classmethod
    def _is_rate_limit_response(
        cls,
        response: requests.Response
    ) -> bool:
        """
        Detects primary and secondary GitHub rate limits.
        """

        if response.status_code == 429:
            return True

        if response.status_code != 403:
            return False

        remaining = response.headers.get(
            "X-RateLimit-Remaining"
        )

        if remaining == "0":
            return True

        if response.headers.get("Retry-After"):
            return True

        try:

            payload = response.json()

            message = str(
                payload.get("message", "")
            ).lower()

        except (ValueError, AttributeError):

            message = ""

        return any(
            expression in message
            for expression in cls.RATE_LIMIT_MESSAGES
        )

    # ==================================================
    # URL VALIDATION
    # ==================================================

    def _validate_url(
        self,
        url: str
    ) -> None:
        """
        Ensures authenticated requests stay on
        the configured GitHub API origin and path.
        """

        parsed_url = urlparse(url)
        parsed_base = urlparse(self.base_url)

        if (
            parsed_url.scheme != "https"
            or parsed_url.netloc != parsed_base.netloc
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.fragment
        ):

            raise GitHubAPIError(
                "Unsafe GitHub API URL blocked."
            )

        base_path = parsed_base.path.rstrip("/")

        if base_path and not (
            parsed_url.path == base_path
            or parsed_url.path.startswith(base_path + "/")
        ):

            raise GitHubAPIError(
                "GitHub API URL is outside "
                "the configured API base path."
            )

    def _build_url(
        self,
        endpoint: str
    ) -> str:
        """
        Builds a URL relative to the GitHub API base URL.
        """

        endpoint = endpoint.lstrip("/")

        if (
            "://" in endpoint
            or endpoint.startswith("//")
        ):

            raise GitHubAPIError(
                "Endpoint must be a relative API path."
            )

        url = f"{self.base_url}/{endpoint}"

        self._validate_url(url)

        return url
