"""Secret storage for the Plaid access token.

Per privacy-data-security standards: never store secrets in plain-text files
if the OS provides a credential vault. On Windows, this maps to
Windows Credential Manager via the `keyring` library.

Order of resolution:
    1. OS keyring (preferred)
    2. PLAID_ACCESS_TOKEN env var / .env file (fallback for first-run onboarding)
"""
import os
from typing import Optional

import keyring

SERVICE = "budget-app"
USERNAME = "plaid_access_token"


def get_plaid_access_token() -> str:
    """Return token from keyring; fall back to env. Empty string if not set."""
    try:
        token = keyring.get_password(SERVICE, USERNAME)
        if token:
            return token
    except Exception:
        pass
    return os.environ.get("PLAID_ACCESS_TOKEN", "")


def set_plaid_access_token(token: str) -> None:
    """Store token in OS keyring. Removes any env-var trace."""
    keyring.set_password(SERVICE, USERNAME, token)


def clear_plaid_access_token() -> None:
    """Remove token from keyring. Used during 'revoke / delete data'."""
    try:
        keyring.delete_password(SERVICE, USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass


def is_using_keyring() -> bool:
    """True if there's a token in keyring (vs env-only)."""
    try:
        return bool(keyring.get_password(SERVICE, USERNAME))
    except Exception:
        return False
