from typing import Any

from src.api.pagination import GitHubPaginator


class IssuesIngestion:
    """
    Handles issue data ingestion from the GitHub REST API.
    """

    def __init__(
        self,
        paginator: GitHubPaginator
    ) -> None:
        self.paginator = paginator

    def get_issues(
        self,
        owner: str,
        repository: str,
        params: dict[str, Any] = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves issues from a specific GitHub repository.

        Pull requests returned by the GitHub Issues endpoint
        are excluded from the result.

        Args:
            owner: Repository owner.
            repository: Repository name.
            params: Optional query parameters.

        Returns:
            list[dict[str, Any]]: Issues returned by GitHub.
        """
        endpoint = f"/repos/{owner}/{repository}/issues"

        issues = []

        pages = self.paginator.paginate(
            endpoint=endpoint,
            params=params
        )

        for page in pages:
            for issue in page:
                if "pull_request" not in issue:
                    issues.append(issue)

        return issues