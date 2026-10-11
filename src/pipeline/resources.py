
import hashlib
import json
import os
import time

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator

from src.ingestion.repositories import RepositoriesIngestion
from src.ingestion.issues import IssuesIngestion
from src.ingestion.pull_requests import PullRequestsIngestion

from src.storage.raw import RawStorage
from src.utils.logger import get_logger


logger = get_logger(__name__)


class ResourcesPipeline:
    """
    Orchestrates ingestion, persistence and incremental
    processing of GitHub repositories, issues and pull requests.

    Repositories:
        - Full Raw snapshots in JSON and Parquet
        - Historical change detection
        - CREATED, UPDATED, MISSING and RESTORED events
        - Persistent repository state
        - Atomic event and checkpoint persistence
        - Idempotent event batches

    Issues and Pull Requests:
        - Incremental ingestion
        - Timestamp-based checkpoints
        - Overlap window for recent records

    Observability:
        - Structured application logging
        - Execution duration tracking
        - Ingestion and persistence metrics
        - Exception tracking
    """

    REPOSITORY_FIELDS = (
        "name",
        "full_name",
        "description",
        "private",
        "fork",
        "archived",
        "default_branch",
        "language",
        "stargazers_count",
        "forks_count",
        "open_issues_count",
        "created_at",
        "updated_at",
        "pushed_at",
        "html_url"
    )

    def __init__(
        self,
        owner: str,
        repository: str,
        checkpoint_path: str = "data/checkpoints"
    ) -> None:

        self.owner = owner
        self.repository = repository

        client = GitHubClient()
        paginator = GitHubPaginator(client=client)

        self.repositories_ingestion = RepositoriesIngestion(
            client=client,
            paginator=paginator
        )

        self.issues_ingestion = IssuesIngestion(
            paginator=paginator
        )

        self.pull_requests_ingestion = PullRequestsIngestion(
            paginator=paginator
        )

        self.storage = RawStorage()

        self.checkpoint_directory = Path(checkpoint_path)

        self.checkpoint_directory.mkdir(
            parents=True,
            exist_ok=True
        )

    # ==================================================
    # CHECKPOINT MANAGEMENT - ISSUES AND PULL REQUESTS
    # ==================================================

    def _checkpoint_path(
        self,
        entity: str
    ) -> Path:

        return self.checkpoint_directory / (
            f"{entity}_{self.owner}_{self.repository}.json"
        )

    def _load_checkpoint(
        self,
        entity: str
    ) -> dict[str, Any]:

        path = self._checkpoint_path(entity)

        if not path.exists():
            return {
                "last_processed_at": None,
                "recent_records": {}
            }

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:
            checkpoint = json.load(file)

        return {
            "last_processed_at": checkpoint.get(
                "last_processed_at"
            ),
            "recent_records": (
                checkpoint.get("recent_records") or {}
            )
        }

    def _save_checkpoint(
        self,
        entity: str,
        last_processed_at: str,
        recent_records: dict[str, str]
    ) -> None:

        path = self._checkpoint_path(entity)

        temporary_path = path.with_suffix(".tmp")

        checkpoint = {
            "entity": entity,
            "owner": self.owner,
            "repository": self.repository,
            "last_processed_at": last_processed_at,
            "recent_records": recent_records
        }

        with temporary_path.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                checkpoint,
                file,
                ensure_ascii=False,
                indent=2
            )

        temporary_path.replace(path)

    @staticmethod
    def _parse_datetime(
        value: str
    ) -> datetime:

        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(timezone.utc)

    @staticmethod
    def _format_datetime(
        value: datetime
    ) -> str:

        return value.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    # ==================================================
    # INCREMENTAL FILTERING
    # ==================================================

    def _filter_incremental(
        self,
        records: list[dict[str, Any]],
        checkpoint: dict[str, Any]
    ) -> list[dict[str, Any]]:

        last_processed_at = checkpoint["last_processed_at"]
        recent_records = checkpoint["recent_records"]

        if not last_processed_at:
            return records

        watermark = self._parse_datetime(
            last_processed_at
        )

        new_records = []

        for record in records:

            updated_at = record.get("updated_at")
            record_id = record.get("id")

            if not updated_at or record_id is None:
                continue

            record_date = self._parse_datetime(
                updated_at
            )

            previous_date = recent_records.get(
                str(record_id)
            )

            if record_date > watermark:
                new_records.append(record)

            elif (
                record_date >= watermark - timedelta(seconds=60)
                and previous_date != updated_at
            ):
                new_records.append(record)

        return new_records

    # ==================================================
    # INCREMENTAL CHECKPOINT UPDATE
    # ==================================================

    def _update_checkpoint(
        self,
        entity: str,
        records: list[dict[str, Any]],
        previous_checkpoint: dict[str, Any]
    ) -> None:

        previous_watermark = (
            previous_checkpoint["last_processed_at"]
        )

        latest_record_date = max(
            self._parse_datetime(record["updated_at"])
            for record in records
        )

        if previous_watermark:

            latest_record_date = max(
                latest_record_date,
                self._parse_datetime(previous_watermark)
            )

        overlap_start = (
            latest_record_date - timedelta(seconds=60)
        )

        recent_records = {
            record_id: updated_at
            for record_id, updated_at
            in previous_checkpoint["recent_records"].items()
            if self._parse_datetime(updated_at) >= overlap_start
        }

        for record in records:

            updated_at = record.get("updated_at")
            record_id = record.get("id")

            if (
                updated_at
                and record_id is not None
                and self._parse_datetime(updated_at) >= overlap_start
            ):
                recent_records[str(record_id)] = updated_at

        self._save_checkpoint(
            entity=entity,
            last_processed_at=self._format_datetime(
                latest_record_date
            ),
            recent_records=recent_records
        )

    # ==================================================
    # RAW PERSISTENCE
    # ==================================================

    def _persist(
        self,
        entity: str,
        records: list[dict[str, Any]]
    ) -> None:

        if not records:

            logger.info(
                "No records to persist | Entity=%s",
                entity
            )

            return

        repository_name = (
            "all_repositories"
            if entity == "repositories"
            else self.repository
        )

        json_path = self.storage.save(
            entity=entity,
            data=records,
            owner=self.owner,
            repository=repository_name
        )

        parquet_methods = {
            "repositories": (
                self.storage.save_repositories_parquet
            ),
            "issues": (
                self.storage.save_issues_parquet
            ),
            "pull_requests": (
                self.storage.save_pull_requests_parquet
            )
        }

        parquet_path = parquet_methods[entity](
            data=records,
            owner=self.owner,
            repository=repository_name
        )

        logger.info(
            "Raw persistence completed | "
            "Entity=%s | Records=%d",
            entity,
            len(records)
        )

        logger.info(
            "Raw JSON persisted | "
            "Entity=%s | Path=%s",
            entity,
            json_path
        )

        logger.info(
            "Raw Parquet persisted | "
            "Entity=%s | Path=%s",
            entity,
            parquet_path
        )

    # ==================================================
    # ATOMIC JSON PERSISTENCE
    # ==================================================

    @staticmethod
    def _atomic_json_write(
        path: Path,
        payload: Any
    ) -> None:
        """
        Writes JSON to a temporary file before replacing
        the destination.

        This avoids exposing partially written checkpoint
        or event files if serialization or writing fails.
        """

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        temporary_path = path.with_name(
            path.name + ".tmp"
        )

        try:

            with temporary_path.open(
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    indent=2
                )

                file.flush()
                os.fsync(file.fileno())

            os.replace(
                temporary_path,
                path
            )

        finally:

            temporary_path.unlink(
                missing_ok=True
            )

    # ==================================================
    # REPOSITORIES - STATE MANAGEMENT
    # ==================================================

    def _repositories_state_path(
        self
    ) -> Path:

        return (
            self.checkpoint_directory
            / f"repositories_{self.owner}.json"
        )

    @classmethod
    def _repository_signature(
        cls,
        repository: dict[str, Any]
    ) -> str:
        """
        Generates a stable SHA-256 signature from
        selected repository metadata.
        """

        payload = {
            field: repository.get(field)
            for field in cls.REPOSITORY_FIELDS
        }

        serialized = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            default=str
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def _build_repository_state(
        self,
        repositories: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Builds a repository state indexed by GitHub ID.

        Duplicate IDs are rejected to avoid comparing
        an inconsistent API response.
        """

        state = {}

        for repository in repositories:

            repository_id = repository.get("id")

            if repository_id is None:
                raise ValueError(
                    "Repository without ID returned by API."
                )

            repository_key = str(repository_id)

            if repository_key in state:
                raise ValueError(
                    "Duplicate repository ID returned by API: "
                    f"{repository_key}"
                )

            state[repository_key] = {
                "name": repository.get("name"),
                "full_name": repository.get("full_name"),
                "signature": self._repository_signature(
                    repository
                ),
                "is_present": True
            }

        return state

    def _load_previous_repositories_state(
        self
    ) -> dict[str, dict[str, Any]]:
        """
        Loads the previous repository checkpoint.

        When no checkpoint exists, initializes the state
        from the latest available Raw JSON snapshot.
        """

        state_path = self._repositories_state_path()

        if state_path.exists():

            with state_path.open(
                "r",
                encoding="utf-8"
            ) as file:
                checkpoint = json.load(file)

            repositories = checkpoint.get(
                "repositories"
            )

            if not isinstance(repositories, dict):
                raise ValueError(
                    "Invalid repositories checkpoint."
                )

            return repositories

        snapshots_directory = (
            Path(self.storage.base_path)
            / "repositories"
        )

        if snapshots_directory.exists():

            snapshots = list(
                snapshots_directory.rglob("*.json")
            )

        else:
            snapshots = []

        if not snapshots:

            logger.info(
                "No previous repository snapshot found | "
                "Starting with empty state"
            )

            return {}

        latest_snapshot = max(
            snapshots,
            key=lambda item: item.stat().st_mtime
        )

        with latest_snapshot.open(
            "r",
            encoding="utf-8"
        ) as file:
            previous_repositories = json.load(file)

        if not isinstance(previous_repositories, list):
            raise ValueError(
                "Previous repositories snapshot is invalid."
            )

        logger.info(
            "Repository state bootstrapped | Snapshot=%s",
            latest_snapshot
        )

        return self._build_repository_state(
            previous_repositories
        )

    # ==================================================
    # REPOSITORIES - CHANGE DETECTION
    # ==================================================

    def _detect_repository_changes(
        self,
        previous_state: dict[str, dict[str, Any]],
        current_state: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Detects changes by repository ID.

        CREATED:
            Repository was not previously known.

        UPDATED:
            Repository is present and its signature changed.

        MISSING:
            Repository was present but is absent now.

        RESTORED:
            Previously missing repository is present again.
        """

        changes = []

        all_ids = (
            set(previous_state)
            | set(current_state)
        )

        for repository_id in sorted(
            all_ids,
            key=int
        ):

            previous = previous_state.get(
                repository_id
            )

            current = current_state.get(
                repository_id
            )

            change_type = None

            if previous is None and current is not None:

                change_type = "CREATED"

            elif previous is not None and current is None:

                if previous.get("is_present", True):
                    change_type = "MISSING"

            elif previous is not None and current is not None:

                if not previous.get("is_present", True):
                    change_type = "RESTORED"

                elif (
                    previous.get("signature")
                    != current.get("signature")
                ):
                    change_type = "UPDATED"

            if change_type:

                reference = current or previous

                changes.append({
                    "repository_id": repository_id,
                    "repository_name": reference.get(
                        "full_name"
                    ),
                    "change_type": change_type,
                    "previous_signature": (
                        previous.get("signature")
                        if previous else None
                    ),
                    "current_signature": (
                        current.get("signature")
                        if current else None
                    )
                })

        return changes

    # ==================================================
    # REPOSITORIES - STATE MERGE
    # ==================================================

    def _merge_repository_states(
        self,
        previous_state: dict[str, dict[str, Any]],
        current_state: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Preserves all previously known repositories.

        Repositories absent from the current API response
        remain in the checkpoint with is_present=False.
        """

        merged_state = {
            repository_id: {
                **repository,
                "is_present": False
            }
            for repository_id, repository
            in previous_state.items()
        }

        merged_state.update(
            current_state
        )

        return merged_state

    # ==================================================
    # REPOSITORIES - CHECKPOINT PERSISTENCE
    # ==================================================

    def _save_repositories_state(
        self,
        state: dict[str, dict[str, Any]],
        execution_datetime: datetime
    ) -> None:
        """
        Saves the latest known repository state atomically.
        """

        checkpoint = {
            "entity": "repositories",
            "owner": self.owner,
            "last_checked_at": (
                execution_datetime.isoformat()
            ),
            "repositories": state
        }

        checkpoint_path = (
            self._repositories_state_path()
        )

        self._atomic_json_write(
            path=checkpoint_path,
            payload=checkpoint
        )

    # ==================================================
    # REPOSITORIES - EVENT BATCH IDENTIFICATION
    # ==================================================

    def _repository_batch_id(
        self,
        previous_state: dict[str, dict[str, Any]],
        changes: list[dict[str, Any]]
    ) -> str:
        """
        Generates a deterministic batch identifier.

        Execution time is excluded so retries against
        the same previous state and changes generate
        the same batch ID.
        """

        identity = {
            "owner": self.owner,
            "previous_state": previous_state,
            "changes": changes
        }

        serialized = json.dumps(
            identity,
            sort_keys=True,
            ensure_ascii=False
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    # ==================================================
    # REPOSITORIES - EVENT PERSISTENCE
    # ==================================================

    def _save_repository_changes(
        self,
        changes: list[dict[str, Any]],
        execution_datetime: datetime,
        previous_state: dict[str, dict[str, Any]]
    ) -> None:
        """
        Persists historical repository events.

        Event files use deterministic batch IDs and
        are stored in a non-date-partitioned directory
        to support retries across different days.
        """

        if not changes:

            logger.info(
                "Repository changes detected | Count=0"
            )

            return

        batch_id = self._repository_batch_id(
            previous_state=previous_state,
            changes=changes
        )

        output_directory = Path(
            "data/changes/repositories/batches"
        )

        output_path = (
            output_directory
            / f"{self.owner}_{batch_id}.json"
        )

        if output_path.exists():

            with output_path.open(
                "r",
                encoding="utf-8"
            ) as file:
                existing_events = json.load(file)

            if (
                not isinstance(existing_events, list)
                or len(existing_events) != len(changes)
                or any(
                    event.get("batch_id") != batch_id
                    for event in existing_events
                )
            ):
                raise ValueError(
                    "Existing repository batch is invalid: "
                    f"{output_path}"
                )

            logger.info(
                "Repository event batch already exists | Path=%s",
                output_path
            )

            return

        events = [
            {
                **change,
                "batch_id": batch_id,
                "detected_at": (
                    execution_datetime.isoformat()
                )
            }
            for change in changes
        ]

        self._atomic_json_write(
            path=output_path,
            payload=events
        )

        logger.info(
            "Repository changes persisted | "
            "Count=%d | Path=%s",
            len(changes),
            output_path
        )

    # ==================================================
    # REPOSITORIES - PIPELINE
    # ==================================================

    def run_repositories(self) -> None:
        """
        Executes full repository ingestion and
        historical change tracking.

        The checkpoint advances only after the Raw
        snapshot and change events are persisted.
        """

        start_time = time.perf_counter()

        logger.info(
            "Repositories ingestion started | Owner=%s",
            self.owner
        )

        try:

            execution_datetime = datetime.now(
                timezone.utc
            )

            # 1. Load previous state.
            previous_state = (
                self._load_previous_repositories_state()
            )

            # 2. Save initial baseline before first snapshot.
            if not self._repositories_state_path().exists():

                self._save_repositories_state(
                    state=previous_state,
                    execution_datetime=execution_datetime
                )

                logger.info(
                    "Initial repository baseline checkpoint saved"
                )

            # 3. Retrieve repositories from GitHub.
            repositories = (
                self.repositories_ingestion.get_repositories(
                    params={
                        "affiliation": "owner",
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": 100
                    }
                )
            )

            if not isinstance(repositories, list):
                raise ValueError(
                    "Repository ingestion must return a list."
                )

            retrieved_count = len(repositories)

            logger.info(
                "Repositories retrieved from API | Count=%d",
                retrieved_count
            )

            # Empty response is treated as suspicious.
            if not repositories:
                raise ValueError(
                    "Repository API returned an empty collection. "
                    "Comparison aborted."
                )

            # 4. Build current repository state.
            current_state = self._build_repository_state(
                repositories
            )

            # 5. Detect changes.
            changes = self._detect_repository_changes(
                previous_state=previous_state,
                current_state=current_state
            )

            # 6. Persist complete Raw snapshot.
            self._persist(
                entity="repositories",
                records=repositories
            )

            # 7. Persist historical change events.
            self._save_repository_changes(
                changes=changes,
                execution_datetime=execution_datetime,
                previous_state=previous_state
            )

            # 8. Preserve missing repositories.
            merged_state = self._merge_repository_states(
                previous_state=previous_state,
                current_state=current_state
            )

            # 9. Advance checkpoint after persistence.
            self._save_repositories_state(
                state=merged_state,
                execution_datetime=execution_datetime
            )

            logger.info(
                "Repository state checkpoint updated | "
                "Repositories=%d",
                len(merged_state)
            )

            # 10. Summarize detected changes.
            change_counts = {
                change_type: sum(
                    1
                    for change in changes
                    if change["change_type"] == change_type
                )
                for change_type in (
                    "CREATED",
                    "UPDATED",
                    "MISSING",
                    "RESTORED"
                )
            }

            duration = (
                time.perf_counter() - start_time
            )

            logger.info(
                "Repositories ingestion completed | "
                "Status=SUCCESS | "
                "Retrieved=%d | "
                "Created=%d | "
                "Updated=%d | "
                "Missing=%d | "
                "Restored=%d | "
                "Duration=%.2fs",
                retrieved_count,
                change_counts["CREATED"],
                change_counts["UPDATED"],
                change_counts["MISSING"],
                change_counts["RESTORED"],
                duration
            )

        except Exception:

            duration = (
                time.perf_counter() - start_time
            )

            logger.exception(
                "Repositories ingestion failed | "
                "Status=FAILED | "
                "Owner=%s | Duration=%.2fs",
                self.owner,
                duration
            )

            raise

    # ==================================================
    # ISSUES AND PULL REQUESTS
    # ==================================================

    def _run_incremental(
        self,
        entity: str,
        ingestion_method
    ) -> None:
        """
        Executes incremental ingestion for Issues
        and Pull Requests.
        """

        start_time = time.perf_counter()

        logger.info(
            "Incremental ingestion started | Entity=%s",
            entity
        )

        try:

            # 1. Load checkpoint.
            checkpoint = self._load_checkpoint(
                entity
            )

            last_processed_at = (
                checkpoint["last_processed_at"]
            )

            params = {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100
            }

            # 2. Configure overlap for Issues.
            if last_processed_at and entity == "issues":

                overlap_start = (
                    self._parse_datetime(last_processed_at)
                    - timedelta(seconds=60)
                )

                params["since"] = self._format_datetime(
                    overlap_start
                )

            if last_processed_at:

                logger.info(
                    "Incremental checkpoint loaded | "
                    "Entity=%s | Since=%s",
                    entity,
                    last_processed_at
                )

            else:

                logger.info(
                    "No checkpoint found | "
                    "Entity=%s | Running full load",
                    entity
                )

            # 3. Retrieve records.
            records = ingestion_method(
                owner=self.owner,
                repository=self.repository,
                params=params
            )

            retrieved_count = len(records)

            logger.info(
                "Records retrieved from API | "
                "Entity=%s | Count=%d",
                entity,
                retrieved_count
            )

            # 4. Apply incremental filtering.
            new_records = self._filter_incremental(
                records=records,
                checkpoint=checkpoint
            )

            new_records_count = len(new_records)

            logger.info(
                "Incremental records identified | "
                "Entity=%s | Count=%d",
                entity,
                new_records_count
            )

            # 5. Skip persistence if no changes.
            if not new_records:

                duration = (
                    time.perf_counter() - start_time
                )

                logger.info(
                    "Incremental ingestion completed | "
                    "Entity=%s | Status=SUCCESS | "
                    "Persisted=0 | Duration=%.2fs",
                    entity,
                    duration
                )

                return

            # 6. Persist Raw records.
            self._persist(
                entity=entity,
                records=new_records
            )

            # 7. Update checkpoint.
            self._update_checkpoint(
                entity=entity,
                records=new_records,
                previous_checkpoint=checkpoint
            )

            logger.info(
                "Incremental checkpoint updated | Entity=%s",
                entity
            )

            duration = (
                time.perf_counter() - start_time
            )

            logger.info(
                "Incremental ingestion completed | "
                "Entity=%s | Status=SUCCESS | "
                "Retrieved=%d | Persisted=%d | "
                "Duration=%.2fs",
                entity,
                retrieved_count,
                new_records_count,
                duration
            )

        except Exception:

            duration = (
                time.perf_counter() - start_time
            )

            logger.exception(
                "Incremental ingestion failed | "
                "Entity=%s | Status=FAILED | "
                "Duration=%.2fs",
                entity,
                duration
            )

            raise

    def run_issues(self) -> None:

        self._run_incremental(
            entity="issues",
            ingestion_method=(
                self.issues_ingestion.get_issues
            )
        )

    def run_pull_requests(self) -> None:

        self._run_incremental(
            entity="pull_requests",
            ingestion_method=(
                self.pull_requests_ingestion.get_pull_requests
            )
        )

    # ==================================================
    # MAIN EXECUTION
    # ==================================================

    def run(self) -> None:
        """
        Executes all GitHub resource pipelines.
        """

        start_time = time.perf_counter()

        logger.info(
            "GitHub Resources Pipeline started | "
            "Owner=%s | Repository=%s",
            self.owner,
            self.repository
        )

        try:

            self.run_repositories()

            self.run_issues()

            self.run_pull_requests()

            duration = (
                time.perf_counter() - start_time
            )

            logger.info(
                "GitHub Resources Pipeline completed | "
                "Status=SUCCESS | Duration=%.2fs",
                duration
            )

        except Exception:

            duration = (
                time.perf_counter() - start_time
            )

            logger.error(
                "GitHub Resources Pipeline failed | "
                "Status=FAILED | Duration=%.2fs",
                duration
            )

            raise
