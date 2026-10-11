
import time

from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator
from src.ingestion.commits import CommitsIngestion
from src.storage.raw import RawStorage
from src.utils.checkpoint import CheckpointManager
from src.utils.logger import get_logger


logger = get_logger(__name__)


class CommitsPipeline:
    """
    Orchestrates incremental ingestion and persistence
    of GitHub repository commits.

    Features:
        - Full and incremental ingestion
        - Checkpoint-based processing
        - Raw JSON and Parquet persistence
        - Structured execution logging
        - Execution duration tracking
        - Exception logging
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

        start_time = time.perf_counter()

        logger.info(
            "Commits ingestion started | "
            "Repository=%s/%s",
            self.owner,
            self.repository
        )

        try:

            # ==========================================
            # STEP 1 - LOAD CHECKPOINT
            # ==========================================

            checkpoint = (
                self.checkpoint_manager.load(
                    entity="commits"
                )
            )

            params = {}

            if checkpoint:

                params["since"] = checkpoint

                logger.info(
                    "Incremental load | Since=%s",
                    checkpoint
                )

            else:

                logger.info(
                    "No checkpoint found | "
                    "Running full load"
                )

            # ==========================================
            # STEP 2 - FETCH COMMITS
            # ==========================================

            commits = self.ingestion.get_commits(
                owner=self.owner,
                repository=self.repository,
                params=params
            )

            retrieved_count = len(commits)

            logger.info(
                "Commits retrieved from API | "
                "Count=%d",
                retrieved_count
            )

            # ==========================================
            # STEP 3 - INCREMENTAL FILTER
            # ==========================================

            if checkpoint:

                commits = [
                    commit
                    for commit in commits
                    if (
                        commit["commit"]["committer"]["date"]
                        > checkpoint
                    )
                ]

            new_commits_count = len(commits)

            logger.info(
                "New commits to process | "
                "Count=%d",
                new_commits_count
            )

            # ==========================================
            # STEP 4 - NO NEW RECORDS
            # ==========================================

            if not commits:

                duration = (
                    time.perf_counter() - start_time
                )

                logger.info(
                    "Commits ingestion completed | "
                    "Status=SUCCESS | "
                    "NewRecords=0 | "
                    "Duration=%.2fs",
                    duration
                )

                return

            # ==========================================
            # STEP 5 - RAW PERSISTENCE
            # ==========================================

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

            logger.info(
                "Commits Raw JSON persisted | "
                "Path=%s",
                json_path
            )

            logger.info(
                "Commits Raw Parquet persisted | "
                "Path=%s",
                parquet_path
            )

            # ==========================================
            # STEP 6 - UPDATE CHECKPOINT
            # ==========================================

            last_commit_date = max(
                commit["commit"]["committer"]["date"]
                for commit in commits
            )

            self.checkpoint_manager.save(
                entity="commits",
                last_processed_at=last_commit_date
            )

            logger.info(
                "Commits checkpoint updated | "
                "LastProcessedAt=%s",
                last_commit_date
            )

            # ==========================================
            # STEP 7 - EXECUTION SUMMARY
            # ==========================================

            duration = (
                time.perf_counter() - start_time
            )

            logger.info(
                "Commits ingestion completed | "
                "Status=SUCCESS | "
                "Retrieved=%d | "
                "Persisted=%d | "
                "Duration=%.2fs",
                retrieved_count,
                new_commits_count,
                duration
            )

        except Exception:

            duration = (
                time.perf_counter() - start_time
            )

            logger.exception(
                "Commits ingestion failed | "
                "Status=FAILED | "
                "Repository=%s/%s | "
                "Duration=%.2fs",
                self.owner,
                self.repository,
                duration
            )

            raise
