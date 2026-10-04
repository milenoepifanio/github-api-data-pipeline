import os
import time
from typing import Any, Optional

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

    Handles:
        - Authentication headers
        - Query parameters
        - Request timeout
        - HTTP status codes
        - Retry for temporary server errors
        - Retry for timeout errors
        - Retry for connection errors
        - Retry for rate limit responses
        - Retry-After
        - X-RateLimit-Reset
        - Exponential backoff
    """

    RETRYABLE_STATUS_CODES = {
        500,
        502,
        503,
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0
    ) -> None:

        self.base_url = (
            base_url
            or os.getenv(
                "GITHUB_BASE_URL",
                "https://api.github.com"
            )
        ).rstrip("/")

        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.session = requests.Session()
        self.session.headers.update(
            get_auth_headers()
        )

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None
    ) -> requests.Response:
        """
        Executes a GET request against the GitHub REST API.

        Args:
            endpoint: GitHub API endpoint.
            params: Optional query parameters.

        Returns:
            requests.Response: GitHub API response.
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

        Used mainly for GitHub pagination URLs.

        Args:
            url: Complete GitHub API URL.

        Returns:
            requests.Response: GitHub API response.
        """
        return self._request(
            url=url
        )

    def _request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None
    ) -> requests.Response:
        """
        Executes an HTTP GET request with retry
        and exponential backoff.

        Retries are performed for:
            - HTTP 500, 502, 503, 403, 429
            - Request timeout
            - Connection errors

        Args:
            url: Complete request URL.
            params: Optional query parameters.

        Returns:
            requests.Response: GitHub API response.

        Raises:
            RequestTimeoutError:
                If all timeout retries fail.

            GitHubConnectionError:
                If all connection retries fail.

            RateLimitError:
                If the rate limit remains exceeded
                after all retry attempts.

            ServerError:
                If all server error retries fail.

            GitHubAPIError:
                For non-retryable API errors.
        """
        attempt = 0

        while True:

            try:
                response = self.session.get(
                    url=url,
                    params=params,
                    timeout=self.timeout
                )

            # ---------------------------------------------------------
            # TIMEOUT
            # ---------------------------------------------------------
            except requests.exceptions.Timeout as error:

                if attempt >= self.max_retries:
                    raise RequestTimeoutError(
                        "GitHub API request timed out "
                        f"after {attempt + 1} attempts."
                    ) from error

                wait_time = (
                    self.backoff_factor
                    * (2 ** attempt)
                )

                logger.warning(
                    "GitHub API request timeout. "
                    "Retry %s/%s in %.2f seconds.",
                    attempt + 1,
                    self.max_retries,
                    wait_time
                )

                self._wait_before_retry(attempt)

                attempt += 1

                continue

            # ---------------------------------------------------------
            # CONNECTION ERROR
            # ---------------------------------------------------------
            except requests.exceptions.ConnectionError as error:

                if attempt >= self.max_retries:
                    raise GitHubConnectionError(
                        "Could not connect to the GitHub API "
                        f"after {attempt + 1} attempts."
                    ) from error

                wait_time = (
                    self.backoff_factor
                    * (2 ** attempt)
                )

                logger.warning(
                    "GitHub API connection error. "
                    "Retry %s/%s in %.2f seconds.",
                    attempt + 1,
                    self.max_retries,
                    wait_time
                )

                self._wait_before_retry(attempt)

                attempt += 1

                continue

            # ---------------------------------------------------------
            # RATE LIMIT
            # ---------------------------------------------------------
            if self._is_rate_limit_response(response):

                if attempt >= self.max_retries:
                    self._handle_response(response)

                wait_time = self._get_rate_limit_wait_time(
                    response=response,
                    attempt=attempt
                )

                logger.warning(
                    "GitHub API rate limit reached. "
                    "HTTP %s. Retry %s/%s in %.2f seconds.",
                    response.status_code,
                    attempt + 1,
                    self.max_retries,
                    wait_time
                )

                time.sleep(wait_time)

                attempt += 1

                continue

            # ---------------------------------------------------------
            # NON-RETRYABLE RESPONSES
            # ---------------------------------------------------------
            if (
                response.status_code
                not in self.RETRYABLE_STATUS_CODES
            ):
                self._handle_response(response)

                return response

            # ---------------------------------------------------------
            # TEMPORARY SERVER ERRORS
            # ---------------------------------------------------------
            if attempt >= self.max_retries:
                self._handle_response(response)

            wait_time = (
                self.backoff_factor
                * (2 ** attempt)
            )

            logger.warning(
                "GitHub API temporary server error. "
                "HTTP %s. Retry %s/%s in %.2f seconds.",
                response.status_code,
                attempt + 1,
                self.max_retries,
                wait_time
            )

            self._wait_before_retry(attempt)

            attempt += 1

    def _get_rate_limit_wait_time(
        self,
        response: requests.Response,
        attempt: int
    ) -> float:
        """
        Determines how long to wait before retrying
        a rate-limited request.

        Priority:
            1. Retry-After
            2. X-RateLimit-Reset
            3. Exponential backoff

        Args:
            response: GitHub API response.
            attempt: Current retry attempt.

        Returns:
            float: Number of seconds to wait.
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

            except ValueError:
                pass

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

            except ValueError:
                pass

        return (
            self.backoff_factor
            * (2 ** attempt)
        )

    def _wait_before_retry(
        self,
        attempt: int
    ) -> None:
        """
        Waits before retrying a request using
        exponential backoff.

        Args:
            attempt: Current retry attempt.
        """
        wait_time = (
            self.backoff_factor
            * (2 ** attempt)
        )

        time.sleep(wait_time)

    def _handle_response(
        self,
        response: requests.Response
    ) -> None:
        """
        Handles HTTP responses returned by the GitHub API.

        Raises specific exceptions according to
        the HTTP status code.
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

    @staticmethod
    def _is_rate_limit_response(
        response: requests.Response
    ) -> bool:
        """
        Checks whether the response indicates
        that a GitHub API rate limit was reached.

        Args:
            response: GitHub API response.

        Returns:
            bool: True when the response represents
            a rate limit condition.
        """
        if response.status_code == 429:
            return True

        if response.status_code == 403:
            remaining = response.headers.get(
                "X-RateLimit-Remaining"
            )

            return remaining == "0"

        return False

    def _build_url(
        self,
        endpoint: str
    ) -> str:
        """
        Builds the complete GitHub API URL.

        Args:
            endpoint: GitHub API endpoint.

        Returns:
            str: Complete GitHub API URL.
        """
        endpoint = endpoint.lstrip("/")

        return f"{self.base_url}/{endpoint}"