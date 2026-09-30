from typing import Any

from src.api.client import GitHubClient


class RepositoriesIngestion:
    """
    Handles repository data ingestion from the GitHub REST API.
    """

    def __init__(
        self,
        client: GitHubClient
    ) -> None:
        self.client = client

    def get_repository(
        self,
        owner: str,
        repository: str
    ) -> dict[str, Any]:
        """
        Retrieves metadata for a specific GitHub repository.

        Args:
            owner: Repository owner.
            repository: Repository name.

        Returns:
            dict[str, Any]: Repository metadata returned by GitHub.
        """
        endpoint = f"/repos/{owner}/{repository}"

        response = self.client.get(
            endpoint=endpoint
        )

        data = response.json()

        return data