import requests
from unittest.mock import Mock, patch

from src.api.client import GitHubClient
from src.utils.exceptions import (
    GitHubConnectionError,
    RateLimitError,
    RequestTimeoutError,
    ServerError,
)


def create_response(
    status_code: int,
    headers: dict = None
) -> Mock:
    """
    Creates a mocked HTTP response.
    """
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}

    return response


# ============================================================
# 1. SERVER ERROR RETRY
# ============================================================

def test_server_error_retry():
    """
    Tests retry and exponential backoff
    for temporary server errors.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_503 = create_response(
        status_code=503
    )

    response_200 = create_response(
        status_code=200
    )

    with patch.object(
        client.session,
        "get",
        side_effect=[
            response_503,
            response_503,
            response_200
        ]
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            response = client.get(
                endpoint="/test"
            )

            print(
                "\n=== 1. SERVER ERROR RETRY ==="
            )
            print(
                f"Final status: {response.status_code}"
            )
            print(
                f"Requests performed: {mock_get.call_count}"
            )
            print(
                "Wait times:",
                [
                    call.args[0]
                    for call in mock_sleep.call_args_list
                ]
            )


# ============================================================
# 2. TIMEOUT RETRY
# ============================================================

def test_timeout_retry():
    """
    Tests retry and exponential backoff
    after request timeout.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_200 = create_response(
        status_code=200
    )

    with patch.object(
        client.session,
        "get",
        side_effect=[
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            response_200
        ]
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            response = client.get(
                endpoint="/test"
            )

            print(
                "\n=== 2. TIMEOUT RETRY ==="
            )
            print(
                f"Final status: {response.status_code}"
            )
            print(
                f"Requests performed: {mock_get.call_count}"
            )
            print(
                "Wait times:",
                [
                    call.args[0]
                    for call in mock_sleep.call_args_list
                ]
            )


# ============================================================
# 3. CONNECTION ERROR RETRY
# ============================================================

def test_connection_error_retry():
    """
    Tests retry and exponential backoff
    after connection errors.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_200 = create_response(
        status_code=200
    )

    with patch.object(
        client.session,
        "get",
        side_effect=[
            requests.exceptions.ConnectionError(),
            requests.exceptions.ConnectionError(),
            response_200
        ]
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            response = client.get(
                endpoint="/test"
            )

            print(
                "\n=== 3. CONNECTION ERROR RETRY ==="
            )
            print(
                f"Final status: {response.status_code}"
            )
            print(
                f"Requests performed: {mock_get.call_count}"
            )
            print(
                "Wait times:",
                [
                    call.args[0]
                    for call in mock_sleep.call_args_list
                ]
            )


# ============================================================
# 4. RATE LIMIT - RETRY-AFTER
# ============================================================

def test_rate_limit_retry_after():
    """
    Tests HTTP 429 retry using Retry-After.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_429 = create_response(
        status_code=429,
        headers={
            "Retry-After": "5"
        }
    )

    response_200 = create_response(
        status_code=200
    )

    with patch.object(
        client.session,
        "get",
        side_effect=[
            response_429,
            response_200
        ]
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            response = client.get(
                endpoint="/test"
            )

            print(
                "\n=== 4. RATE LIMIT - RETRY-AFTER ==="
            )
            print(
                f"Final status: {response.status_code}"
            )
            print(
                f"Requests performed: {mock_get.call_count}"
            )
            print(
                "Wait times:",
                [
                    call.args[0]
                    for call in mock_sleep.call_args_list
                ]
            )


# ============================================================
# 5. RATE LIMIT - X-RATELIMIT-RESET
# ============================================================

def test_rate_limit_reset():
    """
    Tests HTTP 403 rate limit retry using
    X-RateLimit-Reset.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_403 = create_response(
        status_code=403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1010"
        }
    )

    response_200 = create_response(
        status_code=200
    )

    with patch.object(
        client.session,
        "get",
        side_effect=[
            response_403,
            response_200
        ]
    ) as mock_get:

        with patch(
            "src.api.client.time.time",
            return_value=1000.0
        ):

            with patch(
                "src.api.client.time.sleep"
            ) as mock_sleep:

                response = client.get(
                    endpoint="/test"
                )

                print(
                    "\n=== 5. RATE LIMIT - "
                    "X-RATELIMIT-RESET ==="
                )
                print(
                    f"Final status: "
                    f"{response.status_code}"
                )
                print(
                    f"Requests performed: "
                    f"{mock_get.call_count}"
                )
                print(
                    "Wait times:",
                    [
                        call.args[0]
                        for call
                        in mock_sleep.call_args_list
                    ]
                )


# ============================================================
# 6. RATE LIMIT - FALLBACK BACKOFF
# ============================================================

def test_rate_limit_fallback():
    """
    Tests exponential backoff when rate limit
    headers are unavailable.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_429 = create_response(
        status_code=429
    )

    response_200 = create_response(
        status_code=200
    )

    with patch.object(
        client.session,
        "get",
        side_effect=[
            response_429,
            response_429,
            response_200
        ]
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            response = client.get(
                endpoint="/test"
            )

            print(
                "\n=== 6. RATE LIMIT - "
                "FALLBACK BACKOFF ==="
            )
            print(
                f"Final status: "
                f"{response.status_code}"
            )
            print(
                f"Requests performed: "
                f"{mock_get.call_count}"
            )
            print(
                "Wait times:",
                [
                    call.args[0]
                    for call
                    in mock_sleep.call_args_list
                ]
            )


# ============================================================
# 7. SERVER ERROR - MAX RETRIES
# ============================================================

def test_server_error_max_retries():
    """
    Tests whether persistent server errors
    raise ServerError.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_503 = create_response(
        status_code=503
    )

    with patch.object(
        client.session,
        "get",
        return_value=response_503
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            print(
                "\n=== 7. SERVER ERROR - "
                "MAX RETRIES ==="
            )

            try:
                client.get(
                    endpoint="/test"
                )

            except ServerError as error:
                print(
                    type(error).__name__
                )
                print(error)
                print(
                    f"Requests performed: "
                    f"{mock_get.call_count}"
                )
                print(
                    "Wait times:",
                    [
                        call.args[0]
                        for call
                        in mock_sleep.call_args_list
                    ]
                )


# ============================================================
# 8. RATE LIMIT - MAX RETRIES
# ============================================================

def test_rate_limit_max_retries():
    """
    Tests whether persistent rate limiting
    raises RateLimitError.
    """
    client = GitHubClient(
        max_retries=3,
        backoff_factor=1.0
    )

    response_429 = create_response(
        status_code=429,
        headers={
            "Retry-After": "5"
        }
    )

    with patch.object(
        client.session,
        "get",
        return_value=response_429
    ) as mock_get:

        with patch(
            "src.api.client.time.sleep"
        ) as mock_sleep:

            print(
                "\n=== 8. RATE LIMIT - "
                "MAX RETRIES ==="
            )

            try:
                client.get(
                    endpoint="/test"
                )

            except RateLimitError as error:
                print(
                    type(error).__name__
                )
                print(error)
                print(
                    f"Requests performed: "
                    f"{mock_get.call_count}"
                )
                print(
                    "Wait times:",
                    [
                        call.args[0]
                        for call
                        in mock_sleep.call_args_list
                    ]
                )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "\n========================================"
    )
    print(
        " GITHUB CLIENT - RESILIENCE TESTS"
    )
    print(
        "========================================"
    )

    test_server_error_retry()
    test_timeout_retry()
    test_connection_error_retry()
    test_rate_limit_retry_after()
    test_rate_limit_reset()
    test_rate_limit_fallback()
    test_server_error_max_retries()
    test_rate_limit_max_retries()

    print(
        "\n========================================"
    )
    print(
        " TEST EXECUTION FINISHED"
    )
    print(
        "========================================"
    )