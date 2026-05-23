import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from sqlmodel import select

from models.schema import Account, Transaction, RecurringBill, Envelope
from services.plaid_sync import sync_transactions, sync_accounts, sync_recurring, sync_all

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_sync_handles_paginated_added_and_removed(session):
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit(); session.refresh(a)

    page1 = _load("plaid_sync_page1.json")
    page2 = _load("plaid_sync_page2.json")
    raw = MagicMock()
    raw.transactions_sync.side_effect = [page1, page2]

    final_cursor = sync_transactions(
        session=session, plaid_client=raw, access_token="atok", initial_cursor=None,
    )

    assert final_cursor == "cursor_v2"
    rows = session.exec(select(Transaction)).all()
    plaid_ids = {r.plaid_transaction_id for r in rows}
    assert plaid_ids == {"tx_002", "tx_003"}


def test_sync_is_idempotent_on_replay(session):
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit()

    page = {
        "added": [{"transaction_id": "tx_x", "account_id": "acct_1",
                   "date": "2026-05-01", "amount": 10.0, "name": "X",
                   "merchant_name": "X",
                   "personal_finance_category": {"primary": "X", "detailed": "X"},
                   "pending": False}],
        "modified": [], "removed": [],
        "next_cursor": "c1", "has_more": False,
    }
    raw = MagicMock()
    raw.transactions_sync.side_effect = [page, page]

    sync_transactions(session, raw, "atok", initial_cursor=None)
    sync_transactions(session, raw, "atok", initial_cursor=None)

    assert len(session.exec(select(Transaction)).all()) == 1


def test_sync_accounts_inserts_and_updates_balance(session):
    raw = MagicMock()
    raw.accounts_get.return_value = _load("plaid_accounts.json")

    sync_accounts(session, raw, access_token="atok")
    rows = session.exec(select(Account)).all()
    assert len(rows) == 1
    assert rows[0].current_balance == 1523.45
    assert rows[0].available_balance == 1450.00

    raw.accounts_get.return_value = {
        "accounts": [{"account_id": "acct_1", "name": "Chase Total Checking",
                      "type": "depository", "subtype": "checking",
                      "balances": {"current": 1000.00, "available": 950.00}}]
    }
    sync_accounts(session, raw, access_token="atok")
    rows = session.exec(select(Account)).all()
    assert len(rows) == 1
    assert rows[0].current_balance == 1000.00


def test_sync_recurring_inserts_new_streams_unconfirmed(session):
    raw = MagicMock()
    raw.transactions_recurring_get.return_value = _load("plaid_recurring.json")

    sync_recurring(session, raw, access_token="atok")
    rows = session.exec(select(RecurringBill)).all()
    assert len(rows) == 2
    netflix = next(r for r in rows if r.merchant_name == "Netflix")
    assert netflix.amount == 15.99
    assert netflix.cadence == "monthly"
    assert netflix.source == "plaid_auto"
    assert netflix.confirmed_by_user is False
    assert netflix.next_due_date == date(2026, 6, 5)


def test_sync_recurring_updates_existing_stream(session):
    raw = MagicMock()
    raw.transactions_recurring_get.return_value = _load("plaid_recurring.json")
    sync_recurring(session, raw, "atok")

    updated = _load("plaid_recurring.json")
    updated["outflow_streams"][0]["last_amount"]["amount"] = 17.99
    updated["outflow_streams"][0]["predicted_next_date"] = "2026-07-05"
    raw.transactions_recurring_get.return_value = updated
    sync_recurring(session, raw, "atok")

    netflix = session.exec(
        select(RecurringBill).where(RecurringBill.merchant_name == "Netflix")
    ).one()
    assert netflix.amount == 17.99
    assert netflix.next_due_date == date(2026, 7, 5)


def test_sync_all_runs_accounts_then_transactions_then_recurring(session):
    raw = MagicMock()
    raw.accounts_get.return_value = _load("plaid_accounts.json")
    raw.transactions_sync.side_effect = [_load("plaid_sync_page1.json"),
                                          _load("plaid_sync_page2.json")]
    raw.transactions_recurring_get.return_value = _load("plaid_recurring.json")

    sync_all(session, raw, access_token="atok")

    assert len(session.exec(select(Account)).all()) == 1
    plaid_ids = {t.plaid_transaction_id for t in session.exec(select(Transaction)).all()}
    assert plaid_ids == {"tx_002", "tx_003"}
    assert len(session.exec(select(RecurringBill)).all()) == 2


def test_sync_transactions_auto_assigns_envelope(session):
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit()
    for n, pfc, bucket in [
        ("Groceries", "FOOD_AND_DRINK_GROCERIES", "needs"),
        ("Restaurants", "FOOD_AND_DRINK_RESTAURANTS", "wants"),
        ("Gas", "TRANSPORTATION_GAS", "needs"),
    ]:
        session.add(Envelope(name=n, current_budget_per_paycheck=0.0,
                             plaid_category_filter=pfc, bucket=bucket))
    session.commit()

    raw = MagicMock()
    raw.transactions_sync.side_effect = [_load("plaid_sync_page1.json"),
                                          _load("plaid_sync_page2.json")]

    sync_transactions(session, raw, "atok", None)

    by_id = {t.plaid_transaction_id: t for t in session.exec(select(Transaction)).all()}
    gas_env = session.exec(select(Envelope).where(Envelope.name == "Gas")).one()
    assert by_id["tx_002"].envelope_id == gas_env.id
    grocery_env = session.exec(select(Envelope).where(Envelope.name == "Groceries")).one()
    assert by_id["tx_003"].envelope_id == grocery_env.id
