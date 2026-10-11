
from pathlib import Path
from tempfile import TemporaryDirectory

from src.utils.checkpoint import CheckpointManager


def test_checkpoint():
    """
    Validates checkpoint creation, loading and updating
    using an isolated temporary directory.

    This test does not modify production checkpoints.
    """

    print("\n=== CHECKPOINT TEST ===")

    with TemporaryDirectory() as temp_dir:

        checkpoint_manager = CheckpointManager(
            base_path=temp_dir
        )

        entity = "commits"

        # -----------------------------------------
        # TEST 1: INITIAL STATE
        # -----------------------------------------

        checkpoint = checkpoint_manager.load(
            entity=entity
        )

        assert checkpoint is None, (
            "A new checkpoint should not exist."
        )

        print("Initial checkpoint state: OK")

        # -----------------------------------------
        # TEST 2: SAVE CHECKPOINT
        # -----------------------------------------

        first_timestamp = "2026-10-05T14:20:00Z"

        checkpoint_path = checkpoint_manager.save(
            entity=entity,
            last_processed_at=first_timestamp
        )

        assert checkpoint_path.exists(), (
            "Checkpoint file was not created."
        )

        checkpoint = checkpoint_manager.load(
            entity=entity
        )

        assert checkpoint == first_timestamp, (
            "Saved checkpoint value does not match."
        )

        print("Checkpoint creation and loading: OK")

        # -----------------------------------------
        # TEST 3: UPDATE CHECKPOINT
        # -----------------------------------------

        updated_timestamp = "2026-10-11T13:44:59Z"

        checkpoint_manager.save(
            entity=entity,
            last_processed_at=updated_timestamp
        )

        checkpoint = checkpoint_manager.load(
            entity=entity
        )

        assert checkpoint == updated_timestamp, (
            "Updated checkpoint value does not match."
        )

        print("Checkpoint update: OK")

        # -----------------------------------------
        # TEST 4: FILE CONTENT
        # -----------------------------------------

        import json

        with checkpoint_path.open(
            mode="r",
            encoding="utf-8"
        ) as file:
            checkpoint_data = json.load(file)

        assert checkpoint_data["entity"] == entity
        assert (
            checkpoint_data["last_processed_at"]
            == updated_timestamp
        )

        print("Checkpoint JSON structure: OK")

        # -----------------------------------------
        # TEST 5: PERSISTENCE ACROSS INSTANCES
        # -----------------------------------------

        new_manager = CheckpointManager(
            base_path=temp_dir
        )

        recovered_checkpoint = new_manager.load(
            entity=entity
        )

        assert recovered_checkpoint == updated_timestamp, (
            "Checkpoint was not recovered correctly."
        )

        print("Checkpoint recovery across instances: OK")

    # -----------------------------------------
    # TEST 6: TEMPORARY DIRECTORY CLEANUP
    # -----------------------------------------

    assert not Path(temp_dir).exists(), (
        "Temporary checkpoint directory was not removed."
    )

    print("Temporary directory cleanup: OK")

    print("\nAll checkpoint checks passed.")


if __name__ == "__main__":
    test_checkpoint()
