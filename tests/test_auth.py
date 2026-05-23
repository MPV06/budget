"""Auth tests — covers password hashing/verification + idle-timeout logic.

Note: `require_auth()` / `_render_login()` need a live Streamlit context;
those are exercised by the UI smoke tests via apply_app_chrome.
"""
import time
from unittest.mock import patch

import pytest

from services import auth


def test_hash_and_verify_round_trip():
    h = auth.hash_password("correct horse battery staple")
    assert h.startswith("$2b$") or h.startswith("$2a$"), "Should be a bcrypt hash"
    assert auth.verify_password("correct horse battery staple", h) is True
    assert auth.verify_password("wrong password", h) is False


def test_verify_password_handles_empty_inputs():
    h = auth.hash_password("anything")
    assert auth.verify_password("", h) is False
    assert auth.verify_password("anything", "") is False
    assert auth.verify_password("", "") is False


def test_verify_password_handles_malformed_hash():
    # Should not raise, just return False
    assert auth.verify_password("anything", "not-a-bcrypt-hash") is False
    assert auth.verify_password("anything", "$2b$invalid") is False


def test_get_password_hash_prefers_env_when_no_secrets(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", "$2b$12$fakehashfromenv")
    # Without a Streamlit context, st.secrets access raises — env fallback wins
    assert auth.get_password_hash() == "$2b$12$fakehashfromenv"


def test_get_password_hash_returns_empty_when_unset(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD_HASH", raising=False)
    assert auth.get_password_hash() == ""


def test_hashes_are_unique_per_call():
    """bcrypt uses a fresh salt each time — same password → different hashes."""
    h1 = auth.hash_password("samepw")
    h2 = auth.hash_password("samepw")
    assert h1 != h2
    # But both verify
    assert auth.verify_password("samepw", h1)
    assert auth.verify_password("samepw", h2)


# ─── Idle timeout / session state logic ────────────────────────────
class _FakeSession(dict):
    """Behaves like st.session_state but is a plain dict for testing."""
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e
    def __setattr__(self, k, v):
        self[k] = v


@pytest.fixture
def fake_st(monkeypatch):
    """Replace st.session_state with a plain dict for unit tests."""
    fake = _FakeSession()
    monkeypatch.setattr(auth.st, "session_state", fake)
    return fake


def test_is_authenticated_false_when_not_logged_in(fake_st):
    assert auth.is_authenticated() is False


def test_is_authenticated_true_within_window(fake_st):
    fake_st[auth._K_AUTH] = True
    fake_st[auth._K_LAST] = time.time()
    assert auth.is_authenticated() is True


def test_is_authenticated_expires_after_idle_timeout(fake_st):
    fake_st[auth._K_AUTH] = True
    fake_st[auth._K_LAST] = time.time() - (auth.IDLE_TIMEOUT_SECONDS + 1)
    assert auth.is_authenticated() is False
    # Session was flipped to false as side effect
    assert fake_st[auth._K_AUTH] is False


def test_seconds_until_unlock_zero_when_not_locked(fake_st):
    assert auth._seconds_until_unlock() == 0


def test_seconds_until_unlock_positive_during_lockout(fake_st):
    fake_st[auth._K_LOCKOUT_UNTIL] = time.time() + 300
    assert 295 <= auth._seconds_until_unlock() <= 300


def test_idle_window_slides_forward_on_each_check(fake_st):
    fake_st[auth._K_AUTH] = True
    old = time.time() - 60  # 1 min ago
    fake_st[auth._K_LAST] = old
    auth.is_authenticated()
    # Last-activity should now be ~now, not the old value
    assert fake_st[auth._K_LAST] > old
