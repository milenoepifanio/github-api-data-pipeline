from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator


client = GitHubClient()

paginator = GitHubPaginator(
    client=client,
    per_page=5
)

pages = paginator.paginate(
    endpoint="/repos/microsoft/vscode/issues",
    params={
        "state": "open"
    }
)

for page_number, page in enumerate(
    pages,
    start=1
):
    print(
        f"Page {page_number}: "
        f"{len(page)} records"
    )

    if page_number == 3:
        break