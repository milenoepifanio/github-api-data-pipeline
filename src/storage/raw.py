import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class RawStorage:
    """
    Handles persistence of GitHub API responses
    in the Raw data layer.

    Supports:
        - Complete API payload persistence as JSON
        - Structured persistence as Parquet
        - Commits, repositories, issues and pull requests
    """

    def __init__(
        self,
        base_path: str = "data/raw"
    ) -> None:
        self.base_path = Path(base_path)

    def save(
        self,
        entity: str,
        data: Any,
        owner: str,
        repository: str
    ) -> Path:
        """
        Saves the complete API response as JSON.
        """
        ingestion_datetime = datetime.now(timezone.utc)

        ingestion_date = ingestion_datetime.strftime("%Y-%m-%d")
        timestamp = ingestion_datetime.strftime("%Y%m%dT%H%M%S%f")

        output_directory = (
            self.base_path
            / entity
            / f"ingestion_date={ingestion_date}"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = f"{owner}_{repository}_{timestamp}.json"
        output_path = output_directory / filename

        with output_path.open(
            mode="w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        return output_path

    def _save_parquet(
        self,
        entity: str,
        records: list[dict[str, Any]],
        owner: str,
        repository: str,
        ingestion_datetime: datetime
    ) -> Path:
        """
        Persists structured records as Parquet.

        Centralizes directory creation, file naming
        and Parquet serialization.
        """
        if not records:
            raise ValueError(
                f"No records available for {entity} Parquet persistence."
            )

        dataframe = pd.DataFrame(records)

        for column in (
            "commit_date",
            "created_at",
            "updated_at",
            "closed_at",
            "merged_at",
            "pushed_at",
            "ingestion_timestamp"
        ):
            if column in dataframe.columns:
                dataframe[column] = pd.to_datetime(
                    dataframe[column],
                    utc=True,
                    errors="coerce"
                )

        ingestion_date = ingestion_datetime.strftime("%Y-%m-%d")
        timestamp = ingestion_datetime.strftime("%Y%m%dT%H%M%S%f")

        output_directory = (
            self.base_path
            / entity
            / f"ingestion_date={ingestion_date}"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = f"{owner}_{repository}_{timestamp}.parquet"
        output_path = output_directory / filename

        dataframe.to_parquet(
            output_path,
            engine="pyarrow",
            index=False
        )

        return output_path

    def save_commits_parquet(
        self,
        data: list[dict[str, Any]],
        owner: str,
        repository: str
    ) -> Path:
        """
        Selects relevant commit fields and persists
        them as Parquet.
        """
        ingestion_datetime = datetime.now(timezone.utc)
        records = []

        for commit in data:
            commit_info = commit.get("commit") or {}
            author_info = commit_info.get("author") or {}
            committer_info = commit_info.get("committer") or {}
            github_author = commit.get("author") or {}

            records.append({
                "sha": commit.get("sha"),
                "message": commit_info.get("message"),
                "author_login": github_author.get("login"),
                "commit_date": author_info.get("date"),
                "committer_date": committer_info.get("date"),
                "html_url": commit.get("html_url"),
                "ingestion_timestamp": ingestion_datetime,
            })

        return self._save_parquet(
            entity="commits",
            records=records,
            owner=owner,
            repository=repository,
            ingestion_datetime=ingestion_datetime
        )

    def save_repositories_parquet(
        self,
        data: list[dict[str, Any]],
        owner: str,
        repository: str
    ) -> Path:
        """
        Selects repository metadata and persists
        it as Parquet.
        """
        ingestion_datetime = datetime.now(timezone.utc)
        records = []

        for repo in data:
            repo_owner = repo.get("owner") or {}

            records.append({
                "id": repo.get("id"),
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "owner_login": repo_owner.get("login"),
                "description": repo.get("description"),
                "private": repo.get("private"),
                "fork": repo.get("fork"),
                "archived": repo.get("archived"),
                "default_branch": repo.get("default_branch"),
                "language": repo.get("language"),
                "stargazers_count": repo.get("stargazers_count"),
                "forks_count": repo.get("forks_count"),
                "open_issues_count": repo.get("open_issues_count"),
                "created_at": repo.get("created_at"),
                "updated_at": repo.get("updated_at"),
                "pushed_at": repo.get("pushed_at"),
                "html_url": repo.get("html_url"),
                "ingestion_timestamp": ingestion_datetime,
            })

        return self._save_parquet(
            entity="repositories",
            records=records,
            owner=owner,
            repository=repository,
            ingestion_datetime=ingestion_datetime
        )

    def save_issues_parquet(
        self,
        data: list[dict[str, Any]],
        owner: str,
        repository: str
    ) -> Path:
        """
        Selects issue fields and persists
        them as Parquet.
        """
        ingestion_datetime = datetime.now(timezone.utc)
        records = []

        for issue in data:
            github_user = issue.get("user") or {}
            labels = issue.get("labels") or []

            records.append({
                "id": issue.get("id"),
                "number": issue.get("number"),
                "title": issue.get("title"),
                "state": issue.get("state"),
                "state_reason": issue.get("state_reason"),
                "author_login": github_user.get("login"),
                "body": issue.get("body"),
                "comments": issue.get("comments"),
                "labels": [
                    label.get("name")
                    for label in labels
                    if isinstance(label, dict)
                ],
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "closed_at": issue.get("closed_at"),
                "html_url": issue.get("html_url"),
                "ingestion_timestamp": ingestion_datetime,
            })

        return self._save_parquet(
            entity="issues",
            records=records,
            owner=owner,
            repository=repository,
            ingestion_datetime=ingestion_datetime
        )

    def save_pull_requests_parquet(
        self,
        data: list[dict[str, Any]],
        owner: str,
        repository: str
    ) -> Path:
        """
        Selects pull request fields and persists
        them as Parquet.
        """
        ingestion_datetime = datetime.now(timezone.utc)
        records = []

        for pr in data:
            github_user = pr.get("user") or {}
            base_info = pr.get("base") or {}
            head_info = pr.get("head") or {}

            records.append({
                "id": pr.get("id"),
                "number": pr.get("number"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "draft": pr.get("draft"),
                "author_login": github_user.get("login"),
                "body": pr.get("body"),
                "base_branch": base_info.get("ref"),
                "head_branch": head_info.get("ref"),
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
                "closed_at": pr.get("closed_at"),
                "merged_at": pr.get("merged_at"),
                "html_url": pr.get("html_url"),
                "ingestion_timestamp": ingestion_datetime,
            })

        return self._save_parquet(
            entity="pull_requests",
            records=records,
            owner=owner,
            repository=repository,
            ingestion_datetime=ingestion_datetime
        )