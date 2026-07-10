"""Billing service: charges users after validating their token."""

from auth_utils import validate_token


def charge_user(user_id: str, token: str, amount_cents: int) -> dict:
    """Charge a user. Raises PermissionError when the token is invalid."""
    if not validate_token(token):
        raise PermissionError(f"invalid token for user {user_id}")
    return {"user_id": user_id, "charged_cents": amount_cents, "status": "ok"}
