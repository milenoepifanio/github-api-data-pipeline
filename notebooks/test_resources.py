from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator
from src.storage.raw import RawStorage

from src.ingestion.repositories import RepositoriesIngestion
from src.ingestion.issues import IssuesIngestion
from src.ingestion.pull_requests import PullRequestsIngestion


def main() -> None:

    owner = "milenoepifanio"
    repository = "github-api-data-pipeline"

    client = GitHubClient()
    paginator = GitHubPaginator(client=client)
    storage = RawStorage()

    repositories_ingestion = RepositoriesIngestion(
        client=client,
        paginator=paginator
    )

    issues_ingestion = IssuesIngestion(
        paginator=paginator
    )

    pull_requests_ingestion = PullRequestsIngestion(
        paginator=paginator
    )

    # ==================================================
    # REPOSITORIES
    # ==================================================

    repositories = repositories_ingestion.get_repositories(
        params={
            "affiliation": "owner",
            "per_page": 100
        }
    )

    print("\n=== REPOSITORIES ===")
    print(f"Records retrieved: {len(repositories)}")

    for repo in repositories[:5]:
        print(f"- {repo.get('full_name')}")

    # ==================================================
    # ISSUES
    # ==================================================

    issues = issues_ingestion.get_issues(
        owner=owner,
        repository=repository,
        params={
            "state": "all",
            "per_page": 100
        }
    )

    print("\n=== ISSUES ===")
    print(f"Records retrieved: {len(issues)}")

    for issue in issues[:5]:
        print(
            f"- #{issue.get('number')}: "
            f"{issue.get('title')}"
        )

    # ==================================================
    # PULL REQUESTS
    # ==================================================

    pull_requests = pull_requests_ingestion.get_pull_requests(
        owner=owner,
        repository=repository,
        params={
            "state": "all",
            "per_page": 100
        }
    )

    print("\n=== PULL REQUESTS ===")
    print(f"Records retrieved: {len(pull_requests)}")

    for pr in pull_requests[:5]:
        print(
            f"- #{pr.get('number')}: "
            f"{pr.get('title')}"
        )

    # ==================================================
    # RAW PERSISTENCE
    # ==================================================

    print("\n=== RAW PERSISTENCE ===")

    # --------------------------------------------------
    # REPOSITORIES
    # --------------------------------------------------

    if repositories:

        repositories_json = storage.save(
            entity="repositories",
            data=repositories,
            owner=owner,
            repository="all_repositories"
        )

        repositories_parquet = storage.save_repositories_parquet(
            data=repositories,
            owner=owner,
            repository="all_repositories"
        )

        print("\nRepositories persistence completed.")
        print(f"JSON: {repositories_json}")
        print(f"Parquet: {repositories_parquet}")
        print(f"Records persisted: {len(repositories)}")

    else:
        print("\nRepositories: no records to persist.")

    # --------------------------------------------------
    # ISSUES
    # --------------------------------------------------

    if issues:

        issues_json = storage.save(
            entity="issues",
            data=issues,
            owner=owner,
            repository=repository
        )

        issues_parquet = storage.save_issues_parquet(
            data=issues,
            owner=owner,
            repository=repository
        )

        print("\nIssues persistence completed.")
        print(f"JSON: {issues_json}")
        print(f"Parquet: {issues_parquet}")
        print(f"Records persisted: {len(issues)}")

    else:
        print("\nIssues: no records to persist.")

    # --------------------------------------------------
    # PULL REQUESTS
    # --------------------------------------------------

    if pull_requests:

        pull_requests_json = storage.save(
            entity="pull_requests",
            data=pull_requests,
            owner=owner,
            repository=repository
        )

        pull_requests_parquet = storage.save_pull_requests_parquet(
            data=pull_requests,
            owner=owner,
            repository=repository
        )

        print("\nPull Requests persistence completed.")
        print(f"JSON: {pull_requests_json}")
        print(f"Parquet: {pull_requests_parquet}")
        print(f"Records persisted: {len(pull_requests)}")

    else:
        print("\nPull Requests: no records to persist.")

    print("\n=== RESOURCE INGESTION COMPLETED ===")


if __name__ == "__main__":
    main()