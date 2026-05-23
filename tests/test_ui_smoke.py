"""Smoke tests: every Streamlit page should run to completion without exceptions.

Uses Streamlit's AppTest harness — executes the script in-process and reports
any uncaught exception. Does NOT verify rendering output, just that nothing
crashes during the initial run.
"""

import pytest
from streamlit.testing.v1 import AppTest

PAGES = [
    "app.py",
    "pages/1_Dashboard.py",
    "pages/2_Bills.py",
    "pages/3_Envelopes.py",
    "pages/4_BNPL.py",
    "pages/5_Goals.py",
    "pages/6_Transactions.py",
    "pages/7_Settings.py",
    "pages/8_Emergency_Fund.py",
    "pages/9_Debt.py",
    "pages/10_Save.py",
]


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAID_CLIENT_ID", "test_id")
    monkeypatch.setenv("PLAID_SECRET", "test_secret")
    monkeypatch.setenv("PLAID_ENV", "sandbox")
    monkeypatch.setenv("PLAID_ACCESS_TOKEN", "")
    monkeypatch.setenv("PAYCHECK_NET_AMOUNT", "2500.00")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "budget.db"))
    # Auth bypass: set a known hash and pre-authenticate the harness session
    from services import auth
    monkeypatch.setenv("APP_PASSWORD_HASH", auth.hash_password("test-pw"))
    # Force fresh engine for the temp DB
    import services.db
    services.db._engine = None


def _authenticate(at):
    """Pre-set the session state so apply_app_chrome's auth gate lets the page render."""
    import time
    from services import auth
    at.session_state[auth._K_AUTH] = True
    at.session_state[auth._K_LAST] = time.time()
    at.session_state[auth._K_ATTEMPTS] = 0
    at.session_state[auth._K_LOCKOUT_UNTIL] = 0.0


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception(page):
    at = AppTest.from_file(page, default_timeout=10)
    _authenticate(at)
    at.run()
    assert not at.exception, f"{page} raised: {[str(e) for e in at.exception]}"


def test_unauthenticated_page_shows_login_form():
    """Without pre-authenticating, the page should stop at the login form
    (no exception, but no page content rendered either)."""
    at = AppTest.from_file("pages/1_Dashboard.py", default_timeout=10)
    at.run()
    assert not at.exception
    # Login form has the password input
    text_inputs = [t for t in at.text_input if t.placeholder == "Password"]
    assert len(text_inputs) == 1, "Expected exactly one password input when unauthenticated"
