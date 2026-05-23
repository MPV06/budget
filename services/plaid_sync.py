from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from models.schema import (
    Account, Transaction, RecurringBill, SyncState,
    Envelope,
)
from services.categorizer import categorize


_CADENCE_MAP = {
    "WEEKLY": "weekly",
    "BIWEEKLY": "biweekly",
    "SEMI_MONTHLY": "semi_monthly",
    "MONTHLY": "monthly",
    "ANNUALLY": "annual",
    "UNKNOWN": "monthly",
}

_CURSOR_KEY = "transactions_sync_cursor"


def _parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def _resolve_envelope_id(session: Session, plaid_category: Optional[str],
                         merchant: Optional[str]) -> Optional[int]:
    if not plaid_category:
        return None
    envelope_name = categorize(plaid_category, merchant=merchant)
    if envelope_name is None:
        return None
    env = session.exec(select(Envelope).where(Envelope.name == envelope_name)).first()
    return env.id if env else None


def _upsert_transaction(session: Session, payload: dict) -> None:
    plaid_id = payload["transaction_id"]
    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()
    account = session.exec(
        select(Account).where(Account.plaid_account_id == payload["account_id"])
    ).first()
    if account is None:
        raise ValueError(f"Unknown account {payload['account_id']} — sync accounts first")

    pfc = payload.get("personal_finance_category") or {}
    pfc_primary = pfc.get("primary")
    merchant = payload.get("merchant_name")
    env_id = _resolve_envelope_id(session, pfc_primary, merchant)

    if existing is None:
        session.add(Transaction(
            plaid_transaction_id=plaid_id,
            account_id=account.id,
            posted_date=_parse_date(payload["date"]),
            amount=float(payload["amount"]),
            merchant_name=merchant,
            name=payload.get("name", ""),
            plaid_category=pfc_primary,
            plaid_detailed=pfc.get("detailed"),
            pending=bool(payload.get("pending", False)),
            envelope_id=env_id,
        ))
    else:
        existing.posted_date = _parse_date(payload["date"])
        existing.amount = float(payload["amount"])
        existing.merchant_name = merchant
        existing.name = payload.get("name", "")
        existing.plaid_category = pfc_primary
        existing.plaid_detailed = pfc.get("detailed")
        existing.pending = bool(payload.get("pending", False))
        if existing.envelope_id is None:
            existing.envelope_id = env_id
        session.add(existing)


def _remove_transaction(session: Session, plaid_id: str) -> None:
    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()
    if existing is not None:
        session.delete(existing)


def sync_transactions(
    session: Session,
    plaid_client,
    access_token: str,
    initial_cursor: Optional[str],
) -> str:
    """Pull all pages from /transactions/sync; returns final cursor."""
    cursor = initial_cursor
    while True:
        req = {"access_token": access_token}
        if cursor is not None:
            req["cursor"] = cursor
        resp = plaid_client.transactions_sync(req)

        for tx in resp.get("added", []):
            _upsert_transaction(session, tx)
        for tx in resp.get("modified", []):
            _upsert_transaction(session, tx)
        for tx in resp.get("removed", []):
            _remove_transaction(session, tx["transaction_id"])

        session.commit()
        cursor = resp["next_cursor"]
        if not resp.get("has_more", False):
            break
    return cursor


def sync_accounts(session: Session, plaid_client, access_token: str) -> None:
    resp = plaid_client.accounts_get({"access_token": access_token})
    now = datetime.utcnow()
    for a in resp.get("accounts", []):
        existing = session.exec(
            select(Account).where(Account.plaid_account_id == a["account_id"])
        ).first()
        balances = a.get("balances", {})
        if existing is None:
            session.add(Account(
                plaid_account_id=a["account_id"],
                name=a["name"],
                type=a["type"],
                subtype=a.get("subtype", ""),
                current_balance=float(balances.get("current") or 0.0),
                available_balance=float(balances.get("available") or 0.0),
                last_synced_at=now,
            ))
        else:
            existing.name = a["name"]
            existing.current_balance = float(balances.get("current") or 0.0)
            existing.available_balance = float(balances.get("available") or 0.0)
            existing.last_synced_at = now
            session.add(existing)
    session.commit()


def _categorize_pfc_for_503020(pfc_primary: str) -> str:
    """Default 50/30/20 bucket mapping for recurring bills."""
    needs = {"RENT_AND_UTILITIES", "LOAN_PAYMENTS", "TRANSPORTATION", "MEDICAL",
             "GENERAL_SERVICES", "FOOD_AND_DRINK_GROCERIES"}
    if pfc_primary in needs:
        return "needs"
    return "wants"


def sync_recurring(session: Session, plaid_client, access_token: str) -> None:
    resp = plaid_client.transactions_recurring_get({"access_token": access_token})
    for stream in resp.get("outflow_streams", []):
        stream_id = stream["stream_id"]
        last_amt = float(stream["last_amount"]["amount"])
        pfc = (stream.get("personal_finance_category") or {}).get("primary", "")
        existing = session.exec(
            select(RecurringBill).where(RecurringBill.plaid_stream_id == stream_id)
        ).first()
        next_due = _parse_date(stream["predicted_next_date"])
        if existing is None:
            session.add(RecurringBill(
                source="plaid_auto",
                plaid_stream_id=stream_id,
                merchant_name=stream.get("merchant_name") or stream.get("description", ""),
                display_name=stream.get("merchant_name") or stream.get("description", ""),
                amount=last_amt,
                cadence=_CADENCE_MAP.get(stream.get("frequency", "UNKNOWN"), "monthly"),
                next_due_date=next_due,
                category=_categorize_pfc_for_503020(pfc),
                is_active=bool(stream.get("is_active", True)),
                confidence="HIGH" if stream.get("status") == "MATURE" else "MEDIUM",
                confirmed_by_user=False,
            ))
        else:
            existing.amount = last_amt
            existing.next_due_date = next_due
            existing.is_active = bool(stream.get("is_active", True))
            session.add(existing)
    session.commit()


def _load_cursor(session: Session) -> Optional[str]:
    row = session.exec(select(SyncState).where(SyncState.key == _CURSOR_KEY)).first()
    return row.value if row else None


def _save_cursor(session: Session, cursor: str) -> None:
    row = session.exec(select(SyncState).where(SyncState.key == _CURSOR_KEY)).first()
    if row is None:
        session.add(SyncState(key=_CURSOR_KEY, value=cursor))
    else:
        row.value = cursor
        session.add(row)
    session.commit()


def sync_all(session: Session, plaid_client, access_token: str) -> None:
    """One-shot full sync: accounts → transactions → recurring."""
    sync_accounts(session, plaid_client, access_token)
    cursor = _load_cursor(session)
    new_cursor = sync_transactions(session, plaid_client, access_token, cursor)
    _save_cursor(session, new_cursor)
    sync_recurring(session, plaid_client, access_token)
