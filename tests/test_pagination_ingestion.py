from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
import requests

from src.api.pagination import GitHubPaginator
from src.ingestion.commits import CommitsIngestion
from src.ingestion.issues import IssuesIngestion
from src.ingestion.pull_requests import PullRequestsIngestion
from src.ingestion.repositories import RepositoriesIngestion


def make_response(data, next_url: str | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(data).encode("utf-8")
    if next_url:
        response.headers["Link"] = f'<{next_url}>; rel="next"'
    return response


@pytest.mark.parametrize("per_page", [0, 101, -1])
def test_paginator_rejects_invalid_page_size(per_page: int) -> None:
    with pytest.raises(ValueError, match="per_page"):
        GitHubPaginator(client=Mock(), per_page=per_page)


def test_paginate_fetches_pages_and_preserves_input_params() -> None:
    client = Mock()
    first_page = make_response([{"id": 1}], "https://api.github.com/page=2")
    second_page = make_response([{"id": 2}])
    client.get.return_value = first_page
    client.get_url.return_value = second_page
    params = {"state": "all"}
    paginator = GitHubPaginator(client=client, per_page=25)

    pages = list(paginator.paginate("/repos/example/project/issues", params))

    assert pages == [[{"id": 1}], [{"id": 2}]]
    client.get.assert_called_once_with(
        endpoint="/repos/example/project/issues",
        params={"state": "all", "per_page": 25},
    )
    client.get_url.assert_called_once_with("https://api.github.com/page=2")
    assert params == {"state": "all"}


def test_paginate_stops_on_empty_page() -> None:
    client = Mock()
    client.get.return_value = make_response([])
    paginator = GitHubPaginator(client=client)

    assert list(paginator.paginate("/user/repos")) == []
    client.get_url.assert_not_called()


def test_paginate_rejects_non_list_response() -> None:
    client = Mock()
    client.get.return_value = make_response({"message": "bad payload"})
    paginator = GitHubPaginator(client=client)

    with pytest.raises(ValueError, match="Expected a list"):
        list(paginator.paginate("/user/repos"))


def test_commits_ingestion_flattens_pages_and_forwards_arguments() -> None:
    paginator = Mock()
    paginator.paginate.return_value = iter([[{"sha": "a"}], [{"sha": "b"}]])
    ingestion = CommitsIngestion(paginator)

    result = ingestion.get_commits("owner", "repo", {"since": "date"})

    assert result == [{"sha": "a"}, {"sha": "b"}]
    paginator.paginate.assert_called_once_with(
        endpoint="/repos/owner/repo/commits",
        params={"since": "date"},
    )


def test_issues_ingestion_excludes_pull_requests() -> None:
    paginator = Mock()
    paginator.paginate.return_value = iter([[
        {"number": 1},
        {"number": 2, "pull_request": {"url": "api"}},
    ]])

    result = IssuesIngestion(paginator).get_issues("owner", "repo")

    assert result == [{"number": 1}]
    paginator.paginate.assert_called_once_with(
        endpoint="/repos/owner/repo/issues",
        params=None,
    )


def test_pull_requests_ingestion_flattens_pages() -> None:
    paginator = Mock()
    paginator.paginate.return_value = iter([[{"number": 4}], [{"number": 5}]])

    result = PullRequestsIngestion(paginator).get_pull_requests("owner", "repo")

    assert result == [{"number": 4}, {"number": 5}]
    paginator.paginate.assert_called_once_with(
        endpoint="/repos/owner/repo/pulls",
        params=None,
    )


def test_repository_ingestion_reads_one_repository_and_list() -> None:
    client = Mock()
    client.get.return_value.json.return_value = {"id": 7}
    paginator = Mock()
    paginator.paginate.return_value = iter([[{"id": 7}], [{"id": 8}]])
    ingestion = RepositoriesIngestion(client, paginator)

    repository = ingestion.get_repository("owner", "repo")
    repositories = ingestion.get_repositories({"visibility": "public"})

    assert repository == {"id": 7}
    assert repositories == [{"id": 7}, {"id": 8}]
    client.get.assert_called_once_with(endpoint="/repos/owner/repo")
    paginator.paginate.assert_called_once_with(
        endpoint="/user/repos",
        params={"visibility": "public"},
    )