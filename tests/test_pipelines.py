from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

import src.pipeline.main as main_module
from src.pipeline.commits import CommitsPipeline
from src.pipeline.resources import ResourcesPipeline


def make_commit(sha: str, date: str) -> dict:
    return {
        "sha": sha,
        "commit": {"committer": {"date": date}},
    }


def make_repository(repository_id: int, **overrides) -> dict:
    repository = {
        "id": repository_id,
        "name": f"repo-{repository_id}",
        "full_name": f"owner/repo-{repository_id}",
        "description": "sample",
        "private": False,
    }
    repository.update(overrides)
    return repository


def bare_commits_pipeline() -> CommitsPipeline:
    pipeline = CommitsPipeline.__new__(CommitsPipeline)
    pipeline.owner = "owner"
    pipeline.repository = "repo"
    pipeline.ingestion = Mock()
    pipeline.storage = Mock()
    pipeline.checkpoint_manager = Mock()
    pipeline.storage.save.return_value = "raw.json"
    pipeline.storage.save_commits_parquet.return_value = "raw.parquet"
    return pipeline


def bare_resources_pipeline(tmp_path) -> ResourcesPipeline:
    pipeline = ResourcesPipeline.__new__(ResourcesPipeline)
    pipeline.owner = "owner"
    pipeline.repository = "repo"
    pipeline.checkpoint_directory = tmp_path / "checkpoints"
    pipeline.checkpoint_directory.mkdir()
    pipeline.storage = Mock()
    pipeline.repositories_ingestion = Mock()
    pipeline.issues_ingestion = Mock()
    pipeline.pull_requests_ingestion = Mock()
    return pipeline


def test_commits_pipeline_full_load_persists_and_advances_checkpoint() -> None:
    pipeline = bare_commits_pipeline()
    commits = [
        make_commit("old", "2025-01-01T00:00:00Z"),
        make_commit("new", "2025-01-02T00:00:00Z"),
    ]
    pipeline.checkpoint_manager.load.return_value = None
    pipeline.ingestion.get_commits.return_value = commits

    pipeline.run()

    pipeline.ingestion.get_commits.assert_called_once_with(
        owner="owner", repository="repo", params={}
    )
    pipeline.storage.save.assert_called_once_with(
        entity="commits", data=commits, owner="owner", repository="repo"
    )
    pipeline.storage.save_commits_parquet.assert_called_once_with(
        data=commits, owner="owner", repository="repo"
    )
    pipeline.checkpoint_manager.save.assert_called_once_with(
        entity="commits", last_processed_at="2025-01-02T00:00:00Z"
    )


def test_commits_pipeline_incremental_load_filters_checkpoint_boundary() -> None:
    pipeline = bare_commits_pipeline()
    checkpoint = "2025-01-01T00:00:00Z"
    pipeline.checkpoint_manager.load.return_value = checkpoint
    pipeline.ingestion.get_commits.return_value = [
        make_commit("same", checkpoint),
        make_commit("new", "2025-01-01T00:00:01Z"),
    ]

    pipeline.run()

    pipeline.ingestion.get_commits.assert_called_once_with(
        owner="owner", repository="repo", params={"since": checkpoint}
    )
    pipeline.storage.save.assert_called_once_with(
        entity="commits",
        data=[make_commit("new", "2025-01-01T00:00:01Z")],
        owner="owner",
        repository="repo",
    )
    pipeline.checkpoint_manager.save.assert_called_once_with(
        entity="commits", last_processed_at="2025-01-01T00:00:01Z"
    )


def test_commits_pipeline_skips_persistence_when_no_records() -> None:
    pipeline = bare_commits_pipeline()
    pipeline.checkpoint_manager.load.return_value = "2025-01-01T00:00:00Z"
    pipeline.ingestion.get_commits.return_value = []

    pipeline.run()

    pipeline.storage.save.assert_not_called()
    pipeline.storage.save_commits_parquet.assert_not_called()
    pipeline.checkpoint_manager.save.assert_not_called()


def test_datetime_helpers_normalize_to_utc(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)

    parsed = pipeline._parse_datetime("2025-01-01T03:00:00+03:00")

    assert pipeline._format_datetime(parsed) == "2025-01-01T00:00:00Z"


def test_resources_checkpoint_round_trip_is_atomic(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    checkpoint_data = {
        "last_processed_at": "2025-01-01T00:00:00Z",
        "recent_records": {"1": "2025-01-01T00:00:00Z"},
    }

    pipeline._save_checkpoint("issues", **checkpoint_data)

    assert pipeline._load_checkpoint("issues") == checkpoint_data
    assert not pipeline._checkpoint_path("issues").with_suffix(".tmp").exists()


def test_filter_incremental_uses_watermark_overlap_and_record_identity(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    watermark = "2025-01-01T00:00:00Z"
    same_time_changed = "2024-12-31T23:59:30Z"
    records = [
        {"id": 1, "updated_at": watermark},
        {"id": 2, "updated_at": same_time_changed},
        {"id": 3, "updated_at": "2024-12-31T23:58:59Z"},
        {"id": 4, "updated_at": "2025-01-01T00:00:01Z"},
        {"id": 5},
        {"updated_at": "2025-01-01T00:00:02Z"},
    ]
    checkpoint = {
        "last_processed_at": watermark,
        "recent_records": {"1": watermark, "2": "2024-12-31T23:59:29Z"},
    }

    result = pipeline._filter_incremental(records, checkpoint)

    assert [record["id"] for record in result] == [2, 4]


def test_filter_incremental_returns_all_records_without_checkpoint(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    records = [{"id": 1}, {"id": 2}]

    assert pipeline._filter_incremental(
        records,
        {"last_processed_at": None, "recent_records": {}},
    ) == records


def test_update_checkpoint_keeps_overlap_records(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    previous = {
        "last_processed_at": "2025-01-01T00:00:00Z",
        "recent_records": {
            "stale": "2024-12-31T23:58:00Z",
            "recent": "2024-12-31T23:59:30Z",
        },
    }
    records = [
        {"id": 2, "updated_at": "2025-01-01T00:00:10Z"},
        {"id": 3, "updated_at": "2025-01-01T00:00:00Z"},
    ]

    pipeline._update_checkpoint("issues", records, previous)

    saved = json.loads(pipeline._checkpoint_path("issues").read_text())
    assert saved["last_processed_at"] == "2025-01-01T00:00:10Z"
    assert saved["recent_records"] == {
        "recent": "2024-12-31T23:59:30Z",
        "2": "2025-01-01T00:00:10Z",
        "3": "2025-01-01T00:00:00Z",
    }


def test_repository_signature_is_stable_and_ignores_untracked_fields() -> None:
    first = make_repository(1, stars=1)
    second = make_repository(1, stars=99)

    assert ResourcesPipeline._repository_signature(first) == (
        ResourcesPipeline._repository_signature(second)
    )


@pytest.mark.parametrize(
    ("repositories", "message"),
    [
        ([{"name": "no-id"}], "without ID"),
        ([make_repository(1), make_repository(1)], "Duplicate repository ID"),
    ],
)
def test_build_repository_state_rejects_invalid_ids(
    tmp_path, repositories: list[dict], message: str
) -> None:
    pipeline = bare_resources_pipeline(tmp_path)

    with pytest.raises(ValueError, match=message):
        pipeline._build_repository_state(repositories)


def test_detect_repository_changes_classifies_all_event_types(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    previous = {
        "1": {"full_name": "owner/one", "signature": "old", "is_present": True},
        "2": {"full_name": "owner/two", "signature": "gone", "is_present": True},
        "3": {"full_name": "owner/three", "signature": "same", "is_present": False},
        "4": {"full_name": "owner/four", "signature": "same", "is_present": True},
    }
    current = {
        "1": {"full_name": "owner/one", "signature": "new", "is_present": True},
        "3": {"full_name": "owner/three", "signature": "same", "is_present": True},
        "4": {"full_name": "owner/four", "signature": "same", "is_present": True},
        "5": {"full_name": "owner/five", "signature": "new", "is_present": True},
    }

    changes = pipeline._detect_repository_changes(previous, current)

    assert [(change["repository_id"], change["change_type"]) for change in changes] == [
        ("1", "UPDATED"),
        ("2", "MISSING"),
        ("3", "RESTORED"),
        ("5", "CREATED"),
    ]


def test_merge_repository_states_preserves_missing_repositories(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    previous = {"1": {"name": "old", "is_present": True}}
    current = {"2": {"name": "new", "is_present": True}}

    merged = pipeline._merge_repository_states(previous, current)

    assert merged["1"]["is_present"] is False
    assert merged["2"] == current["2"]


def test_atomic_json_write_preserves_existing_file_on_serialization_error(
    tmp_path,
) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"previous": true}', encoding="utf-8")

    with pytest.raises(TypeError):
        ResourcesPipeline._atomic_json_write(path, {"invalid": object()})

    assert json.loads(path.read_text(encoding="utf-8")) == {"previous": True}
    assert not path.with_name("state.json.tmp").exists()


def test_repository_batch_id_is_deterministic(tmp_path) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    old_state = {"1": {"signature": "old"}}
    changes = [{"repository_id": "1", "change_type": "UPDATED"}]

    first = pipeline._repository_batch_id(old_state, changes)
    second = pipeline._repository_batch_id(old_state, changes)

    assert first == second
    assert len(first) == 64


def test_save_repository_changes_is_idempotent(tmp_path, monkeypatch) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    monkeypatch.chdir(tmp_path)
    previous_state = {}
    changes = [{
        "repository_id": "1",
        "repository_name": "owner/repo-1",
        "change_type": "CREATED",
    }]
    detected_at = ResourcesPipeline._parse_datetime("2025-01-01T00:00:00Z")

    pipeline._save_repository_changes(changes, detected_at, previous_state)
    batch_id = pipeline._repository_batch_id(previous_state, changes)
    batch_path = (
        tmp_path
        / "data/changes/repositories/batches"
        / f"owner_{batch_id}.json"
    )
    first_content = json.loads(batch_path.read_text(encoding="utf-8"))
    pipeline._save_repository_changes(changes, detected_at, previous_state)

    assert len(first_content) == 1
    assert first_content[0]["batch_id"] == batch_id
    assert json.loads(batch_path.read_text(encoding="utf-8")) == first_content


@pytest.mark.parametrize(
    ("entity", "expected_since"),
    [
        ("issues", "2024-12-31T23:59:00Z"),
        ("pull_requests", None),
    ],
)
def test_incremental_resource_pipeline_applies_entity_specific_overlap(
    tmp_path, entity: str, expected_since: str | None
) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    watermark = "2025-01-01T00:00:00Z"
    checkpoint = {"last_processed_at": watermark, "recent_records": {}}
    record = {"id": 1, "updated_at": "2025-01-01T00:00:01Z"}
    ingestion = Mock(return_value=[record])
    pipeline._load_checkpoint = Mock(return_value=checkpoint)
    pipeline._persist = Mock()
    pipeline._update_checkpoint = Mock()

    pipeline._run_incremental(entity, ingestion)

    params = ingestion.call_args.kwargs["params"]
    assert params["state"] == "all"
    assert params.get("since") == expected_since
    pipeline._persist.assert_called_once_with(entity=entity, records=[record])
    pipeline._update_checkpoint.assert_called_once_with(
        entity=entity, records=[record], previous_checkpoint=checkpoint
    )


def test_repository_pipeline_saves_checkpoint_after_snapshot_and_events(
    tmp_path,
) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    pipeline._repositories_state_path().write_text(
        '{"repositories": {}}', encoding="utf-8"
    )
    pipeline.repositories_ingestion.get_repositories.return_value = [
        make_repository(1)
    ]
    operations = Mock()
    pipeline._persist = operations.persist
    pipeline._save_repository_changes = operations.save_events
    pipeline._save_repositories_state = operations.save_state

    pipeline.run_repositories()

    assert [call[0] for call in operations.mock_calls] == [
        "persist",
        "save_events",
        "save_state",
    ]


def test_repository_pipeline_does_not_advance_checkpoint_if_persistence_fails(
    tmp_path,
) -> None:
    pipeline = bare_resources_pipeline(tmp_path)
    pipeline._repositories_state_path().write_text(
        '{"repositories": {}}', encoding="utf-8"
    )
    pipeline.repositories_ingestion.get_repositories.return_value = [
        make_repository(1)
    ]
    pipeline._persist = Mock(side_effect=OSError("disk full"))
    pipeline._save_repository_changes = Mock()
    pipeline._save_repositories_state = Mock()

    with pytest.raises(OSError, match="disk full"):
        pipeline.run_repositories()

    pipeline._save_repository_changes.assert_not_called()
    pipeline._save_repositories_state.assert_not_called()


def test_main_runs_pipelines_in_order(monkeypatch) -> None:
    calls = []

    class FakeCommitsPipeline:
        def __init__(self, **kwargs):
            calls.append(("create_commits", kwargs))

        def run(self):
            calls.append(("run_commits", None))

    class FakeResourcesPipeline:
        def __init__(self, **kwargs):
            calls.append(("create_resources", kwargs))

        def run(self):
            calls.append(("run_resources", None))

    monkeypatch.setattr(main_module, "CommitsPipeline", FakeCommitsPipeline)
    monkeypatch.setattr(main_module, "ResourcesPipeline", FakeResourcesPipeline)

    main_module.main()

    assert [call[0] for call in calls] == [
        "create_commits",
        "run_commits",
        "create_resources",
        "run_resources",
    ]


def test_main_does_not_start_resources_after_commit_failure(monkeypatch) -> None:
    class FailingCommitsPipeline:
        def __init__(self, **kwargs):
            pass

        def run(self):
            raise RuntimeError("commit pipeline failed")

    resources_constructor = Mock()
    monkeypatch.setattr(main_module, "CommitsPipeline", FailingCommitsPipeline)
    monkeypatch.setattr(main_module, "ResourcesPipeline", resources_constructor)

    with pytest.raises(RuntimeError, match="commit pipeline failed"):
        main_module.main()

    resources_constructor.assert_not_called()