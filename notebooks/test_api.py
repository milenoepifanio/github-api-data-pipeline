from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator
from src.ingestion.issues import IssuesIngestion


client = GitHubClient()

paginator = GitHubPaginator(
    client=client,
    per_page=5
)

issues_ingestion = IssuesIngestion(
    paginator=paginator
)

issues = issues_ingestion.get_issues(
    owner="milenoepifanio",
    repository="github-api-data-pipeline",
    params={
        "state": "all"
    }
)

print("=== ISSUES ===")
print(f"Total: {len(issues)}")

for issue in issues[:5]:
    print(
        f"#{issue['number']} - "
        f"{issue['state']} - "
        f"{issue['title']}"
    )