import json
from pathlib import Path
from typing import Optional


class CheckpointManager:
    """
    Manages pipeline checkpoints used for
    incremental data ingestion.
    """

    def __init__(
        self,
        base_path: str = "data/checkpoints"
    ) -> None:
        self.base_path = Path(base_path)

        self.base_path.mkdir(
            parents=True,
            exist_ok=True
        )

    def load(
        self,
        entity: str
    ) -> Optional[str]:
        """
        Loads the last checkpoint for an entity.

        Returns:
            str: Last checkpoint value.
            None: If no checkpoint exists.
        """
        checkpoint_path = (
            self.base_path
            / f"{entity}.json"
        )

        if not checkpoint_path.exists():
            return None

        with checkpoint_path.open(
            mode="r",
            encoding="utf-8"
        ) as file:
            checkpoint = json.load(file)

        return checkpoint.get(
            "last_processed_at"
        )

    def save(
        self,
        entity: str,
        last_processed_at: str
    ) -> Path:
        """
        Saves the latest successful checkpoint
        for an entity.
        """
        checkpoint_path = (
            self.base_path
            / f"{entity}.json"
        )

        checkpoint = {
            "entity": entity,
            "last_processed_at": last_processed_at
        }

        with checkpoint_path.open(
            mode="w",
            encoding="utf-8"
        ) as file:
            json.dump(
                checkpoint,
                file,
                ensure_ascii=False,
                indent=2
            )

        return checkpoint_path