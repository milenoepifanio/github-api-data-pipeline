import os

from dotenv import load_dotenv


load_dotenv()


def get_github_token() -> str:
    """
    Retrieves the GitHub access token from environment variables.

    Returns:
        str: GitHub Personal Access Token.

    Raises:
        ValueError: If GITHUB_TOKEN is not configured.
    """
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        raise ValueError(
            "GITHUB_TOKEN environment variable is not configured."
        )

    return token


def get_auth_headers() -> dict[str, str]:
    """
    Builds the authentication headers required by the GitHub API.

    Returns:
        dict[str, str]: HTTP headers containing authentication
        and GitHub API configuration.
    """
    return {
        "Authorization": f"Bearer {get_github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10"
    }