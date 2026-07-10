"""Read-only dashboard: shows whether a session token is still valid."""

from auth_utils import validate_token


def render_session_banner(token: str) -> str:
    """Return the banner text for the current session state."""
    if validate_token(token):
        return "Session active"
    return "Session expired — log in again"
