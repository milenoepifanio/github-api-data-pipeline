from __future__ import annotations

import json

import pytest
import requests

from src.api import auth, client as client_module
from src.api.client import GitHubClient
from src.utils.exceptions import (
    AuthenticationError,
    BadRequestError,
    GitHubAPIError,
    GitHubConnectionError,
    RateLimitError,
    RequestTimeoutError,
    ResourceNotFoundError,
    ServerError,
)


def make_response(
    status_code: int,
    payload: dict | list | None = None,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response._content = json.dumps(payload or {}).encode("utf-8")
    return response


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> GitHubClient:
    monkeypatch.setattr(client_module, "get_auth_headers", lambda: {})
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    return GitHubClient(max_retries=1, backoff_factor=0.01)


def test_get_github_token_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-token")

    assert auth.get_github_token() == "unit-test-token"


def test_get_github_token_requires_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        auth.get_github_token()


def test_auth_headers_include_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-token")

    assert auth.get_auth_headers() == {
        "Authorization": "Bearer unit-test-token",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }


@pytest.mark.parametrize(
    "options",
    [
        {"timeout": 0},
        {"max_retries": -1},
        {"backoff_factor": 0},
        {"max_retry_wait": 0},
        {"base_url": "http://api.github.com"},
        {"base_url": "https://user:pass@api.github.com"},
        {"base_url": "https://api.github.com?token=x"},
    ],
)
def test_client_rejects_invalid_configuration(
    options: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client_module, "get_auth_headers", lambda: {})

    with pytest.raises(ValueError):
        GitHubClient(**options)


def test_get_builds_api_url_and_passes_request_options(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = make_response(200, [{"id": 1}])
    request_options = []

    def fake_get(**kwargs):
        request_options.append(kwargs)
        return response

    monkeypatch.setattr(client.session, "get", fake_get)
    actual = client.get("/repos/example/project", {"page": 2})

    assert actual is response
    assert request_options == [{
        "url": "https://api.github.com/repos/example/project",
        "params": {"page": 2},
        "timeout": 30,
        "allow_redirects": False,
    }]


@pytest.mark.parametrize(
    ("status_code", "exception"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, ResourceNotFoundError),
        (429, RateLimitError),
        (500, ServerError),
        (418, GitHubAPIError),
    ],
)
def test_http_errors_are_mapped_to_domain_exceptions(
    client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    exception: type[Exception],
) -> None:
    response = make_response(status_code)
    monkeypatch.setattr(client.session, "get", lambda **_: response)

    with pytest.raises(exception):
        client.get("/repos/example/project")


def test_forbidden_rate_limit_is_detected_from_headers(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = make_response(403, headers={"X-RateLimit-Remaining": "0"})
    monkeypatch.setattr(client.session, "get", lambda **_: response)

    with pytest.raises(RateLimitError):
        client.get("/repos/example/project")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com/repos/example/project",
        "https://other.example/repos/example/project",
        "https://user@api.github.com/repos/example/project",
        "https://api.github.com.evil.example/repos/example/project",
    ],
)
def test_get_url_blocks_untrusted_urls(
    client: GitHubClient, url: str
) -> None:
    with pytest.raises(GitHubAPIError, match="Unsafe"):
        client.get_url(url)


def test_get_rejects_absolute_endpoint(client: GitHubClient) -> None:
    with pytest.raises(GitHubAPIError, match="relative"):
        client.get("https://other.example/resource")


def test_get_retries_server_error_then_returns_success(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = [make_response(503), make_response(200, {"ok": True})]
    calls = []

    def fake_get(**kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(client.session, "get", fake_get)

    response = client.get("/repos/example/project")

    assert response.status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("request_error", "domain_error"),
    [
        (requests.exceptions.Timeout, RequestTimeoutError),
        (requests.exceptions.ConnectionError, GitHubConnectionError),
    ],
)
def test_transport_failures_are_retried_and_mapped(
    client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
    request_error: type[Exception],
    domain_error: type[Exception],
) -> None:
    calls = 0

    def failing_get(**kwargs):
        nonlocal calls
        calls += 1
        raise request_error("offline")

    monkeypatch.setattr(client.session, "get", failing_get)

    with pytest.raises(domain_error):
        client.get("/repos/example/project")

    assert calls == 2


def test_retry_after_is_used_for_rate_limit(
    client: GitHubClient,
) -> None:
    response = make_response(429, headers={"Retry-After": "12"})

    assert client._get_rate_limit_wait_time(response, attempt=0) == 12


def test_exponential_backoff_respects_maximum(client: GitHubClient) -> None:
    client.max_retry_wait = 0.025

    assert client._exponential_backoff(attempt=8) == 0.025