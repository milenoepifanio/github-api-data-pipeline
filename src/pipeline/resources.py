import json
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
    """

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
    # CHECKPOINT MANAGEMENT
    # ==================================================

    def _checkpoint_path(self, entity: str) -> Path:
        return self.checkpoint_directory / (
            f"{entity}_{self.owner}_{self.repository}.json"
        )

    def _load_checkpoint(self, entity: str) -> dict[str, Any]:

        path = self._checkpoint_path(entity)

        if not path.exists():
            return {
                "last_processed_at": None,
                "recent_records": {}
            }

        with path.open("r", encoding="utf-8") as file:
            checkpoint = json.load(file)

        return {
            "last_processed_at": checkpoint.get("last_processed_at"),
            "recent_records": checkpoint.get("recent_records") or {}
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

        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(
                checkpoint,
                file,
                ensure_ascii=False,
                indent=2
            )

        temporary_path.replace(path)

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(timezone.utc)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
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

        watermark = self._parse_datetime(last_processed_at)
        new_records = []

        for record in records:

            updated_at = record.get("updated_at")
            record_id = record.get("id")

            if not updated_at or record_id is None:
                continue

            record_date = self._parse_datetime(updated_at)
            previous_date = recent_records.get(str(record_id))

            if record_date > watermark:
                new_records.append(record)

            elif (
                record_date >= watermark - timedelta(seconds=60)
                and previous_date != updated_at
            ):
                new_records.append(record)

        return new_records

    # ==================================================
    # CHECKPOINT UPDATE
    # ==================================================

    def _update_checkpoint(
        self,
        entity: str,
        records: list[dict[str, Any]],
        previous_checkpoint: dict[str, Any]
    ) -> None:

        previous_watermark = previous_checkpoint["last_processed_at"]

        latest_record_date = max(
            self._parse_datetime(record["updated_at"])
            for record in records
        )

        if previous_watermark:
            latest_record_date = max(
                latest_record_date,
                self._parse_datetime(previous_watermark)
            )

        overlap_start = latest_record_date - timedelta(seconds=60)

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
    # PERSISTENCE
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
            "repositories": self.storage.save_repositories_parquet,
            "issues": self.storage.save_issues_parquet,
            "pull_requests": self.storage.save_pull_requests_parquet
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
    # REPOSITORIES
    # ==================================================

    def run_repositories(self) -> None:

        print("\n=== REPOSITORIES ===")

        repositories = self.repositories_ingestion.get_repositories(
            params={
                "affiliation": "owner",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100
            }
        )

        print(f"Repositories retrieved: {len(repositories)}")

        self._persist(
            entity="repositories",
            records=repositories
        )

    # ==================================================
    # ISSUES AND PULL REQUESTS
    # ==================================================

    def _run_incremental(
        self,
        entity: str,
        ingestion_method
    ) -> None:

        print(f"\n=== {entity.upper()} ===")

        checkpoint = self._load_checkpoint(entity)
        last_processed_at = checkpoint["last_processed_at"]

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
            params["since"] = self._format_datetime(overlap_start)

        if last_processed_at:
            print(f"Checkpoint: {last_processed_at}")
        else:
            print("No checkpoint found. Running full load.")

        records = ingestion_method(
            owner=self.owner,
            repository=self.repository,
            params=params
        )

        print(f"Records retrieved from API: {len(records)}")

        new_records = self._filter_incremental(
            records=records,
            checkpoint=checkpoint
        )

        print(f"New or updated records: {len(new_records)}")

        if not new_records:
            print("No new records found.")
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

        print("Checkpoint updated successfully.")

    def run_issues(self) -> None:

        self._run_incremental(
            entity="issues",
            ingestion_method=self.issues_ingestion.get_issues
        )

    def run_pull_requests(self) -> None:

        self._run_incremental(
            entity="pull_requests",
            ingestion_method=self.pull_requests_ingestion.get_pull_requests
        )

    # ==================================================
    # MAIN EXECUTION
    # ==================================================

    def run(self) -> None:

        print("\n=== GITHUB RESOURCES PIPELINE ===")

        self.run_repositories()
        self.run_issues()
        self.run_pull_requests()

        print("\nResources pipeline completed successfully.")