
from unittest.mock import Mock, patch

import requests

from src.api.client import GitHubClient
from src.utils.exceptions import (
    AuthenticationError,
    GitHubAPIError,
    RateLimitError,
    RequestTimeoutError,
    ServerError,
)


def make_response(
    status_code,
    headers=None,
    message=None
):
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = {
        "message": message or ""
    }
    return response


def make_client():
    return GitHubClient(
        max_retries=2,
        backoff_factor=1,
        max_retry_wait=5
    )


def test_authentication():
    client = make_client()

    client.session.get = Mock(
        return_value=make_response(401)
    )

    try:
        client.get("/user")
        raise AssertionError("Expected AuthenticationError")
    except AuthenticationError:
        pass

    assert client.session.get.call_count == 1
    print("HTTP 401 without retry: OK")


def test_forbidden():
    client = make_client()

    client.session.get = Mock(
        return_value=make_response(403)
    )

    try:
        client.get("/user")
        raise AssertionError("Expected AuthenticationError")
    except AuthenticationError:
        pass

    assert client.session.get.call_count == 1
    print("HTTP 403 without rate limit: OK")


def test_server_retry():
    client = make_client()

    client.session.get = Mock(
        side_effect=[
            make_response(503),
            make_response(200)
        ]
    )

    with patch(
        "src.api.client.time.sleep"
    ) as mocked_sleep:

        response = client.get("/user")

    assert response.status_code == 200
    assert client.session.get.call_count == 2
    mocked_sleep.assert_called_once_with(1)

    print("HTTP 503 retry and recovery: OK")


def test_timeout_exhaustion():
    client = make_client()

    client.session.get = Mock(
        side_effect=requests.exceptions.Timeout()
    )

    with patch(
        "src.api.client.time.sleep"
    ):

        try:
            client.get("/user")
            raise AssertionError("Expected RequestTimeoutError")
        except RequestTimeoutError:
            pass

    assert client.session.get.call_count == 3

    print("Timeout retries exhausted: OK")


def test_secondary_rate_limit():
    client = make_client()

    client.session.get = Mock(
        side_effect=[
            make_response(
                403,
                headers={"Retry-After": "2"},
                message="Secondary rate limit exceeded"
            ),
            make_response(200)
        ]
    )

    with patch(
        "src.api.client.time.sleep"
    ) as mocked_sleep:

        response = client.get("/user")

    assert response.status_code == 200
    mocked_sleep.assert_called_once_with(2.0)

    print("Secondary rate limit recovery: OK")


def test_rate_limit_wait_cap():
    client = make_client()

    client.session.get = Mock(
        return_value=make_response(
            429,
            headers={"Retry-After": "120"}
        )
    )

    try:
        client.get("/user")
        raise AssertionError("Expected RateLimitError")
    except RateLimitError:
        pass

    assert client.session.get.call_count == 1

    print("Rate limit maximum wait: OK")


def test_unsafe_pagination_url():
    client = make_client()

    client.session.get = Mock()

    try:
        client.get_url("https://example.com/steal")
        raise AssertionError("Expected GitHubAPIError")
    except GitHubAPIError:
        pass

    client.session.get.assert_not_called()

    print("Unsafe pagination URL blocked: OK")


def test_invalid_configuration():
    try:
        GitHubClient(timeout=0)
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass

    print("Invalid configuration rejected: OK")


def main():
    test_authentication()
    test_forbidden()
    test_server_retry()
    test_timeout_exhaustion()
    test_secondary_rate_limit()
    test_rate_limit_wait_cap()
    test_unsafe_pagination_url()
    test_invalid_configuration()

    print("\nAll client recovery checks passed.")


if __name__ == "__main__":
    main()
