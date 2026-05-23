import pytest
from services.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("PLAID_CLIENT_ID", "id123")
    monkeypatch.setenv("PLAID_SECRET", "secret123")
    monkeypatch.setenv("PLAID_ENV", "sandbox")
    monkeypatch.setenv("PAYCHECK_NET_AMOUNT", "2500.00")
    monkeypatch.setenv("DB_PATH", "./data/test.db")

    s = Settings(_env_file=None)
    assert s.plaid_client_id == "id123"
    assert s.plaid_secret == "secret123"
    assert s.plaid_env == "sandbox"
    assert s.paycheck_net_amount == 2500.00
    assert s.db_path == "./data/test.db"


def test_settings_rejects_invalid_env(monkeypatch):
    monkeypatch.setenv("PLAID_CLIENT_ID", "id")
    monkeypatch.setenv("PLAID_SECRET", "sec")
    monkeypatch.setenv("PLAID_ENV", "garbage")
    monkeypatch.setenv("PAYCHECK_NET_AMOUNT", "100")
    monkeypatch.setenv("DB_PATH", "./x")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
