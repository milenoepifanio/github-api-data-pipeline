import json

import pandas as pd
import pytest

from src.storage.raw import RawStorage
from src.utils.checkpoint import CheckpointManager


def test_raw_storage_saves_complete_json_under_date_partition(tmp_path) -> None:
    storage = RawStorage(tmp_path / "raw")
    payload = [{"title": "Issue", "body": "olá"}]

    output_path = storage.save("issues", payload, "owner", "repo")

    assert output_path.exists()
    assert output_path.parent.parent.name == "issues"
    assert output_path.parent.name.startswith("ingestion_date=")
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_save_commits_parquet_flattens_nested_fields_and_dates(tmp_path) -> None:
    storage = RawStorage(tmp_path / "raw")
    payload = [{
        "sha": "abc",
        "html_url": "https://github.com/owner/repo/commit/abc",
        "commit": {
            "message": "fix",
            "author": {"date": "2025-01-02T03:04:05Z"},
            "committer": {"date": "2025-01-02T03:05:05Z"},
        },
        "author": {"login": "octocat"},
    }]

    path = storage.save_commits_parquet(payload, "owner", "repo")
    frame = pd.read_parquet(path)

    assert frame.loc[0, "sha"] == "abc"
    assert frame.loc[0, "message"] == "fix"
    assert frame.loc[0, "author_login"] == "octocat"
    assert frame.loc[0, "commit_date"] == pd.Timestamp("2025-01-02T03:04:05Z")
    assert "ingestion_timestamp" in frame


def test_save_repositories_parquet_selects_repository_metadata(tmp_path) -> None:
    storage = RawStorage(tmp_path / "raw")
    payload = [{
        "id": 42,
        "name": "repo",
        "full_name": "owner/repo",
        "owner": {"login": "owner"},
        "stargazers_count": 9,
        "created_at": "not-a-date",
        "unused": "not persisted",
    }]

    frame = pd.read_parquet(
        storage.save_repositories_parquet(payload, "owner", "repo")
    )

    assert frame.loc[0, "id"] == 42
    assert frame.loc[0, "owner_login"] == "owner"
    assert pd.isna(frame.loc[0, "created_at"])
    assert "unused" not in frame.columns


def test_save_issues_parquet_flattens_user_and_labels(tmp_path) -> None:
    storage = RawStorage(tmp_path / "raw")
    payload = [{
        "id": 3,
        "number": 8,
        "user": {"login": "reporter"},
        "labels": [{"name": "bug"}, {"name": "urgent"}, "ignored"],
        "updated_at": "2025-02-03T00:00:00Z",
    }]

    frame = pd.read_parquet(
        storage.save_issues_parquet(payload, "owner", "repo")
    )

    assert frame.loc[0, "author_login"] == "reporter"
    assert list(frame.loc[0, "labels"]) == ["bug", "urgent"]
    assert frame.loc[0, "updated_at"] == pd.Timestamp("2025-02-03T00:00:00Z")


def test_save_pull_requests_parquet_flattens_branches(tmp_path) -> None:
    storage = RawStorage(tmp_path / "raw")
    payload = [{
        "number": 12,
        "user": {"login": "contributor"},
        "base": {"ref": "main"},
        "head": {"ref": "feature"},
        "merged_at": "2025-03-04T00:00:00Z",
    }]

    frame = pd.read_parquet(
        storage.save_pull_requests_parquet(payload, "owner", "repo")
    )

    assert frame.loc[0, "author_login"] == "contributor"
    assert frame.loc[0, "base_branch"] == "main"
    assert frame.loc[0, "head_branch"] == "feature"
    assert frame.loc[0, "merged_at"] == pd.Timestamp("2025-03-04T00:00:00Z")


@pytest.mark.parametrize(
    "save_method",
    [
        "save_commits_parquet",
        "save_repositories_parquet",
        "save_issues_parquet",
        "save_pull_requests_parquet",
    ],
)
def test_parquet_writers_reject_empty_records(tmp_path, save_method: str) -> None:
    storage = RawStorage(tmp_path / "raw")

    with pytest.raises(ValueError, match="No records"):
        getattr(storage, save_method)([], "owner", "repo")


def test_checkpoint_load_save_and_overwrite(tmp_path) -> None:
    manager = CheckpointManager(tmp_path / "checkpoints")

    assert manager.load("issues") is None
    first_path = manager.save("issues", "2025-01-01T00:00:00Z")
    assert manager.load("issues") == "2025-01-01T00:00:00Z"

    manager.save("issues", "2025-01-02T00:00:00Z")

    assert manager.load("issues") == "2025-01-02T00:00:00Z"
    assert json.loads(first_path.read_text(encoding="utf-8")) == {
        "entity": "issues",
        "last_processed_at": "2025-01-02T00:00:00Z",
    }


def test_checkpoint_load_propagates_invalid_json(tmp_path) -> None:
    checkpoint_directory = tmp_path / "checkpoints"
    checkpoint_directory.mkdir()
    (checkpoint_directory / "issues.json").write_text("{", encoding="utf-8")
    manager = CheckpointManager(checkpoint_directory)

    with pytest.raises(json.JSONDecodeError):
        manager.load("issues")