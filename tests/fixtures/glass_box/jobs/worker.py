"""Background job that reuses auth — third direct importer of auth_utils."""

from auth_utils import validate_token


def refresh_session(token: str) -> bool:
    return validate_token(token)
