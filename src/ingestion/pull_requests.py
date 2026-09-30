from typing import Any

from src.api.pagination import GitHubPaginator


class PullRequestsIngestion:
    """
    Handles pull request data ingestion from the GitHub REST API.
    """

    def __init__(
        self,
        paginator: GitHubPaginator
    ) -> None:
        self.paginator = paginator

    def get_pull_requests(
        self,
        owner: str,
        repository: str,
        params: dict[str, Any] = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves pull requests from a specific GitHub repository.

        Args:
            owner: Repository owner.
            repository: Repository name.
            params: Optional query parameters.

        Returns:
            list[dict[str, Any]]: Pull requests returned by GitHub.
        """
        endpoint = f"/repos/{owner}/{repository}/pulls"

        pull_requests = []

        pages = self.paginator.paginate(
            endpoint=endpoint,
            params=params
        )

        for page in pages:
            pull_requests.extend(page)

        return pull_requests