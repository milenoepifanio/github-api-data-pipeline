
import hashlib
import json
import os

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.api.client import GitHubClient
from src.api.pagination import GitHubPaginator

from src.ingestion.repositories import RepositoriesIngestion
from src.ingestion.issues import IssuesIngestion
from src.ingestion.pull_requests import PullRequestsIngestion

from src.storage.raw import RawStorage


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
            print(f"{entity}: no records to persist.")
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

        print(f"Records persisted: {len(records)}")
        print(f"JSON: {json_path}")
        print(f"Parquet: {parquet_path}")

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

            print(
                "No previous repository snapshot found. "
                "Starting with an empty state."
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

        print(
            "Bootstrapping repository state from: "
            f"{latest_snapshot}"
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

            print(
                "Repository changes detected: 0"
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

            print(
                "Repository change batch already exists: "
                f"{output_path}"
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

        print(
            f"Repository changes detected: {len(changes)}"
        )

        print(
            f"Changes JSON: {output_path}"
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

        print("\n=== REPOSITORIES ===")

        execution_datetime = datetime.now(
            timezone.utc
        )

        # 1. Load previous state.
        previous_state = (
            self._load_previous_repositories_state()
        )

        # 2. Save initial baseline before the first
        #    new snapshot, when no checkpoint exists.
        if not self._repositories_state_path().exists():

            self._save_repositories_state(
                state=previous_state,
                execution_datetime=execution_datetime
            )

            print(
                "Initial repository baseline checkpoint saved."
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

        print(
            f"Repositories retrieved: {len(repositories)}"
        )

        # An empty response is treated as suspicious.
        # This avoids marking every known repository
        # as MISSING because of an empty collection.
        if not repositories:
            raise ValueError(
                "Repository API returned an empty collection. "
                "Comparison aborted."
            )

        # 4. Build the current repository state.
        current_state = self._build_repository_state(
            repositories
        )

        # 5. Detect differences.
        changes = self._detect_repository_changes(
            previous_state=previous_state,
            current_state=current_state
        )

        # 6. Persist complete Raw snapshot.
        #    A failure here stops checkpoint advancement.
        self._persist(
            entity="repositories",
            records=repositories
        )

        # 7. Persist historical change events.
        #    A failure here also stops checkpoint advancement.
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

        # 9. Advance checkpoint only after persistence.
        self._save_repositories_state(
            state=merged_state,
            execution_datetime=execution_datetime
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

        print(
            f"Created: {change_counts['CREATED']}"
        )

        print(
            f"Updated: {change_counts['UPDATED']}"
        )

        print(
            f"Missing: {change_counts['MISSING']}"
        )

        print(
            f"Restored: {change_counts['RESTORED']}"
        )

        print(
            "Repository state checkpoint updated."
        )

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

        print(f"\n=== {entity.upper()} ===")

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

        if last_processed_at and entity == "issues":

            overlap_start = (
                self._parse_datetime(last_processed_at)
                - timedelta(seconds=60)
            )

            params["since"] = self._format_datetime(
                overlap_start
            )

        if last_processed_at:

            print(
                f"Checkpoint: {last_processed_at}"
            )

        else:

            print(
                "No checkpoint found. Running full load."
            )

        records = ingestion_method(
            owner=self.owner,
            repository=self.repository,
            params=params
        )

        print(
            f"Records retrieved from API: {len(records)}"
        )

        new_records = self._filter_incremental(
            records=records,
            checkpoint=checkpoint
        )

        print(
            f"New or updated records: {len(new_records)}"
        )

        if not new_records:

            print(
                "No new records found."
            )

            return

        self._persist(
            entity=entity,
            records=new_records
        )

        self._update_checkpoint(
            entity=entity,
            records=new_records,
            previous_checkpoint=checkpoint
        )

        print(
            "Checkpoint updated successfully."
        )

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

        print(
            "\n=== GITHUB RESOURCES PIPELINE ==="
        )

        self.run_repositories()

        self.run_issues()

        self.run_pull_requests()

        print(
            "\nResources pipeline completed successfully."
        )
