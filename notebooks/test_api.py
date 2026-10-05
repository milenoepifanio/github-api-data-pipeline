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


json_path = raw_storage.save(
    entity="commits",
    data=commits,
    owner=owner,
    repository=repository
)


parquet_path = raw_storage.save_commits_parquet(
    data=commits,
    owner=owner,
    repository=repository
)


print("\n=== RAW PERSISTENCE ===")
print(f"JSON: {json_path}")
print(f"Parquet: {parquet_path}")
print(f"Records: {len(commits)}")