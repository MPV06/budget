from typing import Any

ALLOWED_METHODS = frozenset({
    "accounts_get",
    "transactions_sync",
    "transactions_recurring_get",
    "item_get",
})


class ReadOnlyViolation(RuntimeError):
    pass


class PlaidReadOnlyClient:
    """Whitelist wrapper around plaid.ApiClient. Only ALLOWED_METHODS proxy through."""

    def __init__(self, raw_client: Any):
        self._raw = raw_client

    def __getattr__(self, name: str):
        if name in ALLOWED_METHODS:
            return getattr(self._raw, name)
        raise ReadOnlyViolation(
            f"Method '{name}' is not in the read-only whitelist. "
            f"Allowed: {sorted(ALLOWED_METHODS)}"
        )
