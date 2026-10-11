from typing import Any

from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator


class RepositoriesIngestion:
    """
    Handles repository data ingestion from the GitHub REST API.
    """

    def __init__(
        self,
        client: GitHubClient,
        paginator: GitHubPaginator
    ) -> None:
        self.client = client
        self.paginator = paginator

    def get_repository(
        self,
        owner: str,
        repository: str
    ) -> dict[str, Any]:
        """
        Retrieves metadata for a specific GitHub repository.
        """
        endpoint = f"/repos/{owner}/{repository}"

        response = self.client.get(
            endpoint=endpoint
        )

        return response.json()

    def get_repositories(
        self,
        params: dict[str, Any] = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves repositories accessible to the
        authenticated GitHub user using pagination.
        """
        endpoint = "/user/repos"

        repositories = []

        pages = self.paginator.paginate(
            endpoint=endpoint,
            params=params
        )

        for page in pages:
            repositories.extend(page)

        return repositories