
"""
Manual functional validation for repository change tracking.

Scenarios:
    1. CREATED
    2. UPDATED
    3. MISSING
    4. RESTORED
    5. NO CHANGES
    6. Missing repository state preservation
    7. Snapshot persistence failure
    8. Event persistence failure
    9. Idempotent event retry across dates
    10. Checkpoint persistence failure

This script:
    - Does not call the GitHub API
    - Does not require a GitHub token
    - Does not modify real Raw files
    - Does not modify real checkpoints

Execution:
    python -m notebooks.test_repository_changes
"""

import json
import os
import tempfile

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.pipeline.resources import ResourcesPipeline


# ==================================================
# SIMULATED REPOSITORY STATE
# ==================================================

def repository_state(
    name: str,
    signature: str,
    is_present: bool = True
) -> dict:
    """
    Builds a simulated repository checkpoint record.
    """

    return {
        "name": name,
        "full_name": f"example/{name}",
        "signature": signature,
        "is_present": is_present
    }


def api_repository(
    repository_id: int,
    name: str,
    description: str
) -> dict:
    """
    Builds a simulated GitHub API repository response.
    """

    return {
        "id": repository_id,
        "name": name,
        "full_name": f"example/{name}",
        "description": description,
        "private": False,
        "fork": False,
        "archived": False,
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 0,
        "forks_count": 0,
        "open_issues_count": 0,
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "2026-10-11T10:00:00Z",
        "pushed_at": "2026-10-11T10:00:00Z",
        "html_url": f"https://github.com/example/{name}"
    }


# ==================================================
# CHANGE DETECTION TESTS
# ==================================================

def check_change_detection(
    pipeline: ResourcesPipeline
) -> None:

    previous_state = {
        "101": repository_state(
            name="project-a",
            signature="hash-a"
        ),
        "102": repository_state(
            name="project-b",
            signature="hash-b"
        )
    }

    # ==================================================
    # TEST 1 - CREATED
    # ==================================================

    created_state = {
        **previous_state,
        "103": repository_state(
            name="project-c",
            signature="hash-c"
        )
    }

    changes = pipeline._detect_repository_changes(
        previous_state=previous_state,
        current_state=created_state
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "CREATED"
    assert changes[0]["repository_id"] == "103"

    print("CREATED: OK")

    # ==================================================
    # TEST 2 - UPDATED
    # ==================================================

    updated_state = {
        **previous_state,
        "101": repository_state(
            name="project-a",
            signature="hash-a-updated"
        )
    }

    changes = pipeline._detect_repository_changes(
        previous_state=previous_state,
        current_state=updated_state
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "UPDATED"
    assert changes[0]["repository_id"] == "101"

    print("UPDATED: OK")

    # ==================================================
    # TEST 3 - MISSING
    # ==================================================

    missing_state = {
        "101": previous_state["101"]
    }

    changes = pipeline._detect_repository_changes(
        previous_state=previous_state,
        current_state=missing_state
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "MISSING"
    assert changes[0]["repository_id"] == "102"

    print("MISSING: OK")

    # ==================================================
    # TEST 4 - RESTORED
    # ==================================================

    previous_missing_state = {
        "101": previous_state["101"],
        "102": repository_state(
            name="project-b",
            signature="hash-b",
            is_present=False
        )
    }

    restored_state = {
        "101": previous_state["101"],
        "102": previous_state["102"]
    }

    changes = pipeline._detect_repository_changes(
        previous_state=previous_missing_state,
        current_state=restored_state
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "RESTORED"
    assert changes[0]["repository_id"] == "102"

    print("RESTORED: OK")

    # ==================================================
    # TEST 5 - NO CHANGES
    # ==================================================

    changes = pipeline._detect_repository_changes(
        previous_state=previous_state,
        current_state=previous_state
    )

    assert len(changes) == 0

    print("NO CHANGES: OK")

    # ==================================================
    # TEST 6 - MISSING STATE PRESERVATION
    # ==================================================

    merged_state = pipeline._merge_repository_states(
        previous_state=previous_state,
        current_state=missing_state
    )

    assert "102" in merged_state
    assert merged_state["102"]["is_present"] is False
    assert merged_state["102"]["signature"] == "hash-b"

    print(
        "Missing repository retained in state: OK"
    )


# ==================================================
# FAILURE SIMULATION
# ==================================================

def check_failure_recovery(
    pipeline: ResourcesPipeline,
    temporary_directory: Path
) -> None:
    """
    Simulates persistence failures using temporary
    checkpoints and mocked ingestion/persistence.
    """

    previous_state = {
        "101": repository_state(
            name="project-a",
            signature="old-signature"
        )
    }

    execution_datetime = datetime.now(
        timezone.utc
    )

    # Create a real checkpoint in the temporary folder.
    pipeline._save_repositories_state(
        state=previous_state,
        execution_datetime=execution_datetime
    )

    checkpoint_path = (
        pipeline._repositories_state_path()
    )

    original_checkpoint = (
        checkpoint_path.read_bytes()
    )

    # Simulated API response with an updated repository.
    simulated_records = [
        api_repository(
            repository_id=101,
            name="project-a",
            description="Updated description"
        )
    ]

    pipeline.repositories_ingestion = SimpleNamespace(
        get_repositories=lambda params: simulated_records
    )

    # ==================================================
    # TEST 7 - SNAPSHOT FAILURE
    # ==================================================

    with patch.object(
        pipeline,
        "_persist",
        side_effect=OSError(
            "simulated snapshot failure"
        )
    ):

        try:
            pipeline.run_repositories()

        except OSError as error:
            assert str(error) == (
                "simulated snapshot failure"
            )

        else:
            raise AssertionError(
                "Snapshot failure was not propagated."
            )

    assert (
        checkpoint_path.read_bytes()
        == original_checkpoint
    )

    print(
        "Snapshot failure keeps checkpoint: OK"
    )

    # ==================================================
    # TEST 8 - EVENT FAILURE
    # ==================================================

    with (
        patch.object(
            pipeline,
            "_persist",
            return_value=None
        ),
        patch.object(
            pipeline,
            "_save_repository_changes",
            side_effect=OSError(
                "simulated event failure"
            )
        )
    ):

        try:
            pipeline.run_repositories()

        except OSError as error:
            assert str(error) == (
                "simulated event failure"
            )

        else:
            raise AssertionError(
                "Event failure was not propagated."
            )

    assert (
        checkpoint_path.read_bytes()
        == original_checkpoint
    )

    print(
        "Event failure keeps checkpoint: OK"
    )

    # ==================================================
    # TEST 9 - IDEMPOTENT EVENT RETRY
    # ==================================================

    current_state = pipeline._build_repository_state(
        simulated_records
    )

    changes = pipeline._detect_repository_changes(
        previous_state=previous_state,
        current_state=current_state
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "UPDATED"

    previous_working_directory = Path.cwd()

    try:

        # Use temporary working directory so the
        # events never reach the real project folder.
        os.chdir(
            temporary_directory
        )

        pipeline._save_repository_changes(
            changes=changes,
            execution_datetime=execution_datetime,
            previous_state=previous_state
        )

        events_directory = Path(
            "data/changes/repositories/batches"
        )

        event_files = list(
            events_directory.glob("*.json")
        )

        assert len(event_files) == 1

        event_path = event_files[0]

        original_event_content = (
            event_path.read_bytes()
        )

        # Retry with the same state and changes,
        # but on a different execution date.
        pipeline._save_repository_changes(
            changes=changes,
            execution_datetime=(
                execution_datetime + timedelta(days=1)
            ),
            previous_state=previous_state
        )

        event_files_after_retry = list(
            events_directory.glob("*.json")
        )

        assert len(event_files_after_retry) == 1

        assert (
            event_path.read_bytes()
            == original_event_content
        )

        saved_events = json.loads(
            original_event_content
        )

        assert len(saved_events) == 1

        assert (
            saved_events[0]["change_type"]
            == "UPDATED"
        )

        print(
            "Event retry across dates is idempotent: OK"
        )

    finally:

        os.chdir(
            previous_working_directory
        )

    # ==================================================
    # TEST 10 - CHECKPOINT WRITE FAILURE
    # ==================================================

    # Mock snapshot persistence so the test reaches
    # checkpoint persistence without requiring
    # RawStorage.save() or Parquet methods.

    previous_working_directory = Path.cwd()

    try:

        os.chdir(
            temporary_directory
        )

        with (
            patch.object(
                pipeline,
                "_persist",
                return_value=None
            ),
            patch.object(
                pipeline,
                "_save_repositories_state",
                side_effect=OSError(
                    "simulated checkpoint failure"
                )
            )
        ):

            try:
                pipeline.run_repositories()

            except OSError as error:
                assert str(error) == (
                    "simulated checkpoint failure"
                )

            else:
                raise AssertionError(
                    "Checkpoint failure was not propagated."
                )

        assert (
            checkpoint_path.read_bytes()
            == original_checkpoint
        )

        print(
            "Checkpoint write failure preserves baseline: OK"
        )

    finally:

        os.chdir(
            previous_working_directory
        )


# ==================================================
# MAIN EXECUTION
# ==================================================

def main() -> None:
    """
    Runs isolated functional checks without
    constructing a real GitHubClient.
    """

    with tempfile.TemporaryDirectory(
        prefix="github_repository_validation_"
    ) as temporary_path:

        temporary_directory = Path(
            temporary_path
        ).resolve()

        # Avoid calling the real ResourcesPipeline
        # constructor, which creates an API client.
        pipeline = object.__new__(
            ResourcesPipeline
        )

        pipeline.owner = "example"
        pipeline.repository = "sample"

        pipeline.checkpoint_directory = (
            temporary_directory / "checkpoints"
        )

        pipeline.checkpoint_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        # Simulated storage configuration.
        # No real Raw files will be created.
        pipeline.storage = SimpleNamespace(
            base_path=temporary_directory / "raw"
        )

        # Validate change detection and state merge.
        check_change_detection(
            pipeline=pipeline
        )

        # Validate failure handling and event retries.
        check_failure_recovery(
            pipeline=pipeline,
            temporary_directory=temporary_directory
        )

    print(
        "\nAll isolated repository checks passed."
    )


if __name__ == "__main__":
    main()
