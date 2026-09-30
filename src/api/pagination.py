from collections.abc import Iterator
from typing import Any, Optional

import requests

from src.api.client import GitHubClient


class GitHubPaginator:
    """
    Handles pagination for the GitHub REST API
    using the Link response header.
    """

    def __init__(
        self,
        client: GitHubClient,
        per_page: int = 100
    ) -> None:

        if not 1 <= per_page <= 100:
            raise ValueError(
                "per_page must be between 1 and 100."
            )

        self.client = client
        self.per_page = per_page

    def paginate(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None
    ) -> Iterator[list[dict[str, Any]]]:
        """
        Retrieves all pages from a paginated GitHub endpoint.

        Args:
            endpoint: GitHub API endpoint.
            params: Optional query parameters.

        Yields:
            list[dict[str, Any]]: Records from each page.
        """
        request_params = dict(params or {})
        request_params["per_page"] = self.per_page

        response = self.client.get(
            endpoint=endpoint,
            params=request_params
        )

        while True:

            data = response.json()

            if not isinstance(data, list):
                raise ValueError(
                    "Expected a list response from paginated endpoint."
                )

            if not data:
                break

            yield data

            next_url = self._get_next_url(response)

            if next_url is None:
                break

            response = self.client.get_url(next_url)

    @staticmethod
    def _get_next_url(
        response: requests.Response
    ) -> Optional[str]:
        """
        Retrieves the next page URL from GitHub's Link header.

        Args:
            response: GitHub HTTP response.

        Returns:
            Optional[str]: Next page URL or None when
            pagination is complete.
        """
        return response.links.get(
            "next",
            {}
        ).get("url")