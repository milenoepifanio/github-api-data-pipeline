class GitHubAPIError(Exception):
    """
    Base exception for errors related to the GitHub API.
    """
    pass


class BadRequestError(GitHubAPIError):
    """
    Raised when the GitHub API returns HTTP 400.
    """
    pass


class AuthenticationError(GitHubAPIError):
    """
    Raised when authentication or authorization fails.
    """
    pass


class ResourceNotFoundError(GitHubAPIError):
    """
    Raised when the requested GitHub resource does not exist.
    """
    pass


class RateLimitError(GitHubAPIError):
    """
    Raised when the GitHub API rate limit is exceeded.
    """
    pass


class ServerError(GitHubAPIError):
    """
    Raised when the GitHub API returns a server-side error.
    """
    pass


class RequestTimeoutError(GitHubAPIError):
    """
    Raised when a request to the GitHub API times out.
    """
    pass


class GitHubConnectionError(GitHubAPIError):
    """
    Raised when a connection to the GitHub API cannot be established.
    """
    pass