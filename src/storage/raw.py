import json
from datetime import datetime
from pathlib import Path
from typing import Any


class RawStorage:
    """
    Handles persistence of GitHub API responses
    in the Raw data layer.
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
        Saves API data as JSON in the Raw layer.

        Args:
            entity: API resource being persisted.
            data: Original data returned by the API.
            owner: GitHub repository owner.
            repository: GitHub repository name.

        Returns:
            Path: Path of the generated JSON file.
        """
        ingestion_datetime = datetime.now()

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