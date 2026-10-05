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
        - Selected commit data persistence as Parquet
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

        Args:
            entity: API resource being persisted.
            data: Original data returned by the API.
            owner: GitHub repository owner.
            repository: GitHub repository name.

        Returns:
            Path: Path of the generated JSON file.
        """
        ingestion_datetime = datetime.now(timezone.utc)

        ingestion_date = ingestion_datetime.strftime(
            "%Y-%m-%d"
        )

        timestamp = ingestion_datetime.strftime(
            "%Y%m%dT%H%M%S"
        )

        output_directory = (
            self.base_path
            / entity
            / f"ingestion_date={ingestion_date}"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = (
            f"{owner}_{repository}_{timestamp}.json"
        )

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

    def save_commits_parquet(
        self,
        data: list[dict[str, Any]],
        owner: str,
        repository: str
    ) -> Path:
        """
        Selects relevant commit fields and persists
        them as a Parquet file.

        Args:
            data: Commit data returned by the GitHub API.
            owner: GitHub repository owner.
            repository: GitHub repository name.

        Returns:
            Path: Path of the generated Parquet file.
        """
        ingestion_datetime = datetime.now(timezone.utc)

        ingestion_date = ingestion_datetime.strftime(
            "%Y-%m-%d"
        )

        timestamp = ingestion_datetime.strftime(
            "%Y%m%dT%H%M%S"
        )

        records = []

        for commit in data:
            commit_info = commit.get(
                "commit",
                {}
            )

            author_info = commit_info.get(
                "author",
                {}
            )

            github_author = (
                commit.get("author") or {}
            )

            records.append(
                {
                    "sha": commit.get("sha"),
                    "message": commit_info.get("message"),
                    "author_login": github_author.get("login"),
                    "commit_date": author_info.get("date"),
                    "html_url": commit.get("html_url"),
                    "ingestion_timestamp": ingestion_datetime,
                }
            )

        dataframe = pd.DataFrame(records)

        if not dataframe.empty:
            dataframe["commit_date"] = pd.to_datetime(
                dataframe["commit_date"],
                utc=True
            )

        output_directory = (
            self.base_path
            / "commits"
            / f"ingestion_date={ingestion_date}"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = (
            f"{owner}_{repository}_{timestamp}.parquet"
        )

        output_path = output_directory / filename

        dataframe.to_parquet(
            output_path,
            engine="pyarrow",
            index=False
        )

        return output_path