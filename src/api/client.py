import os
from typing import Any, Optional

import requests

from dotenv import load_dotenv
from src.api.auth import get_auth_headers

load_dotenv()


class GitHubClient:
    """
    HTTP client for interacting with the GitHub REST API.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30
    ) -> None:

        self.base_url = (
            base_url
            or os.getenv(
                "GITHUB_BASE_URL",
                "https://api.github.com"
            )
        ).rstrip("/")

        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(get_auth_headers())

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None
    ) -> requests.Response:
        """
        Executes a GET request against the GitHub REST API.
        """
        url = self._build_url(endpoint)

        response = self.session.get(
            url=url,
            params=params,
            timeout=self.timeout
        )

        response.raise_for_status()

        return response

    def get_url(
        self,
        url: str
    ) -> requests.Response:
        """
        Executes a GET request using a complete URL.
        """
        response = self.session.get(
            url=url,
            timeout=self.timeout
        )

        response.raise_for_status()

        return response

    def _build_url(
        self,
        endpoint: str
    ) -> str:
        """
        Builds the complete GitHub API URL.
        """
        endpoint = endpoint.lstrip("/")

        return f"{self.base_url}/{endpoint}"