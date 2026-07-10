"""Shared authentication helpers. Fixture code — parsed by Focus, never executed."""

FIXTURE_SECRET = "glass-box-fake-token"


def validate_token(token: str) -> bool:
    """Return True when the token matches the fixture secret."""
    return token == FIXTURE_SECRET


def hash_password(password: str) -> str:
    """Fake hash for fixture purposes only — never real cryptography."""
    return password[::-1]
