"""HTTP surface: exposes billing over a POST route."""

from billing.service import charge_user


class _Router:
    """Minimal stand-in for a web framework router — parsed, never run."""

    def post(self, path: str):
        def decorator(func):
            return func

        return decorator


router = _Router()


@router.post("/charge")
def charge(user_id: str, token: str, amount_cents: int) -> dict:
    return charge_user(user_id, token, amount_cents)
