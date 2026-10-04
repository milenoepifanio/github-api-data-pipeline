from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator

from src.ingestion.commits import CommitsIngestion
from src.storage.raw import RawStorage


client = GitHubClient()

paginator = GitHubPaginator(
    client=client
)

commits_ingestion = CommitsIngestion(
    paginator=paginator
)

raw_storage = RawStorage()


owner = "milenoepifanio"
repository = "github-api-data-pipeline"


commits = commits_ingestion.get_commits(
    owner=owner,
    repository=repository
)


output_path = raw_storage.save(
    entity="commits",
    data=commits,
    owner=owner,
    repository=repository
)


print("Raw file created:")
print(output_path)
print(f"Records: {len(commits)}")