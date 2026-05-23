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
    # Force fresh engine for the temp DB
    import services.db
    services.db._engine = None


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception(page):
    at = AppTest.from_file(page, default_timeout=10)
    at.run()
    assert not at.exception, f"{page} raised: {[str(e) for e in at.exception]}"
