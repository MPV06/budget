"""Test the keyring-backed secret store with fallback to env."""
from unittest.mock import patch

from services import secret_store


def test_returns_keyring_value_when_set():
    with patch("services.secret_store.keyring.get_password", return_value="atok-keyring"):
        assert secret_store.get_plaid_access_token() == "atok-keyring"


def test_falls_back_to_env_when_keyring_empty(monkeypatch):
    monkeypatch.setenv("PLAID_ACCESS_TOKEN", "atok-env")
    with patch("services.secret_store.keyring.get_password", return_value=None):
        assert secret_store.get_plaid_access_token() == "atok-env"


def test_returns_empty_string_when_both_missing(monkeypatch):
    monkeypatch.delenv("PLAID_ACCESS_TOKEN", raising=False)
    with patch("services.secret_store.keyring.get_password", return_value=None):
        assert secret_store.get_plaid_access_token() == ""


def test_keyring_exception_falls_back_gracefully(monkeypatch):
    monkeypatch.setenv("PLAID_ACCESS_TOKEN", "atok-env")
    with patch("services.secret_store.keyring.get_password",
               side_effect=Exception("backend not available")):
        assert secret_store.get_plaid_access_token() == "atok-env"


def test_set_stores_in_keyring():
    with patch("services.secret_store.keyring.set_password") as set_pw:
        secret_store.set_plaid_access_token("new-token")
        set_pw.assert_called_once_with(secret_store.SERVICE,
                                        secret_store.USERNAME, "new-token")


def test_clear_handles_missing_key():
    import keyring.errors
    with patch("services.secret_store.keyring.delete_password",
               side_effect=keyring.errors.PasswordDeleteError("not found")):
        # Should not raise
        secret_store.clear_plaid_access_token()


def test_is_using_keyring_true_when_value_present():
    with patch("services.secret_store.keyring.get_password", return_value="abc"):
        assert secret_store.is_using_keyring() is True


def test_is_using_keyring_false_when_missing():
    with patch("services.secret_store.keyring.get_password", return_value=None):
        assert secret_store.is_using_keyring() is False
