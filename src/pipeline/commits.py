from datetime import datetime, timezone

from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator
from src.ingestion.commits import CommitsIngestion
from src.storage.raw import RawStorage
from src.utils.checkpoint import CheckpointManager


class CommitsPipeline:
    """
    Orchestrates incremental ingestion and persistence
    of GitHub repository commits.
    """

    def __init__(
        self,
        owner: str,
        repository: str
    ) -> None:
        self.owner = owner
        self.repository = repository

        client = GitHubClient()

        paginator = GitHubPaginator(
            client=client
        )

        self.ingestion = CommitsIngestion(
            paginator=paginator
        )

        self.storage = RawStorage()

        self.checkpoint_manager = CheckpointManager()

    def run(self) -> None:
        """
        Executes the commits ingestion pipeline,
        supporting full and incremental loads.
        """

        checkpoint = self.checkpoint_manager.load(
            entity="commits"
        )

        params = {}

        if checkpoint:
            params["since"] = checkpoint

            print(
                f"Incremental load since: {checkpoint}"
            )
        else:
            print(
                "No checkpoint found. Running full load."
            )

        commits = self.ingestion.get_commits(
            owner=self.owner,
            repository=self.repository,
            params=params
        )

        print(
            f"Commits retrieved from API: {len(commits)}"
        )

        # Remove commits already processed.
        if checkpoint:
            commits = [
                commit
                for commit in commits
                if commit["commit"]["committer"]["date"] > checkpoint
            ]

        print(
            f"New commits to process: {len(commits)}"
        )

        if not commits:
            print(
                "No new commits found."
            )
            return

        json_path = self.storage.save(
            entity="commits",
            data=commits,
            owner=self.owner,
            repository=self.repository
        )

        parquet_path = (
            self.storage.save_commits_parquet(
                data=commits,
                owner=self.owner,
                repository=self.repository
            )
        )

        # Uses the committer date as the incremental watermark.
        last_commit_date = max(
            commit["commit"]["committer"]["date"]
            for commit in commits
        )

        self.checkpoint_manager.save(
            entity="commits",
            last_processed_at=last_commit_date
        )

        print(f"JSON: {json_path}")
        print(f"Parquet: {parquet_path}")
        print(
            f"Checkpoint updated: {last_commit_date}"
        )