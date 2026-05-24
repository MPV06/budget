"""Tests for JSON export/import — round-trip correctness."""
from datetime import date

from models.schema import (
    RecurringBill, BNPLPlan, BNPLInstallment, Envelope,
    SavingsGoal, DebtAccount, SyncState,
)
from services.data_io import (
    export_to_dict, export_to_json,
    import_from_dict, import_from_json, SCHEMA_VERSION,
)


def _seed(session):
    """Populate a session with one of each user-data row."""
    session.add(RecurringBill(
        source="manual", merchant_name="Rent", display_name="Rent",
        amount=660, cadence="monthly",
        next_due_date=date(2026, 6, 1), category="needs",
        is_active=True, confirmed_by_user=True,
    ))
    session.add(Envelope(
        name="Groceries", current_budget_per_paycheck=200,
        plaid_category_filter="FOOD_AND_DRINK_GROCERIES", bucket="needs",
    ))
    session.add(SavingsGoal(
        name="Vacation", target_amount=5000, current_balance=1200,
        target_date=date(2027, 6, 1), priority=3, is_active=True,
    ))
    session.add(DebtAccount(
        name="Visa", balance=2500, apr_pct=22.0, min_payment=50,
        is_active=True,
    ))
    session.add(SyncState(key="manual_balance", value="1043"))
    session.commit()

    plan = BNPLPlan(
        source="manual", provider="affirm", merchant_name="Best Buy",
        original_amount=200, total_payments=4, payment_amount=50,
        cadence="biweekly", start_date=date(2026, 5, 1), is_active=True,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    session.add(BNPLInstallment(
        plan_id=plan.id, installment_number=1, due_date=date(2026, 5, 1),
        amount=50, status="scheduled",
    ))
    session.commit()


def test_export_returns_expected_top_level_keys(session):
    _seed(session)
    out = export_to_dict(session)
    expected = {
        "schema_version", "exported_at", "bills", "bnpl_plans",
        "bnpl_installments", "envelopes", "savings_goals",
        "debt_accounts", "sync_state",
    }
    assert expected.issubset(set(out.keys()))
    assert out["schema_version"] == SCHEMA_VERSION


def test_export_includes_seeded_rows(session):
    _seed(session)
    out = export_to_dict(session)
    assert len(out["bills"]) == 1
    assert out["bills"][0]["display_name"] == "Rent"
    assert len(out["envelopes"]) == 1
    assert len(out["savings_goals"]) == 1
    assert len(out["debt_accounts"]) == 1
    assert len(out["bnpl_plans"]) == 1
    assert len(out["bnpl_installments"]) == 1
    assert any(s["key"] == "manual_balance" for s in out["sync_state"])


def test_export_serializes_dates_as_iso_strings(session):
    _seed(session)
    out = export_to_dict(session)
    bill = out["bills"][0]
    assert bill["next_due_date"] == "2026-06-01"


def test_export_to_json_is_valid_json(session):
    _seed(session)
    s = export_to_json(session)
    import json
    parsed = json.loads(s)
    assert parsed["schema_version"] == SCHEMA_VERSION


def test_export_excludes_transactions_sync_cursor(session):
    session.add(SyncState(key="manual_balance", value="500"))
    session.add(SyncState(key="transactions_sync_cursor", value="abc123"))
    session.commit()
    out = export_to_dict(session)
    keys = [s["key"] for s in out["sync_state"]]
    assert "manual_balance" in keys
    assert "transactions_sync_cursor" not in keys


def test_round_trip_restores_all_data(session, engine):
    _seed(session)
    backup = export_to_dict(session)

    # Fresh session simulating a deployed app with empty DB
    from sqlmodel import Session
    with Session(engine) as fresh:
        # Wipe everything (replace=True default)
        counts = import_from_dict(fresh, backup, replace=True)

    assert counts["bills"] == 1
    assert counts["envelopes"] == 1
    assert counts["savings_goals"] == 1
    assert counts["debt_accounts"] == 1
    assert counts["bnpl_plans"] == 1
    assert counts["bnpl_installments"] == 1
    assert counts["sync_state"] == 1

    with Session(engine) as check:
        from sqlmodel import select
        bills = check.exec(select(RecurringBill)).all()
        assert len(bills) == 1
        assert bills[0].display_name == "Rent"
        assert bills[0].next_due_date == date(2026, 6, 1)

        ms = check.exec(select(SyncState).where(SyncState.key == "manual_balance")).one()
        assert ms.value == "1043"


def test_import_rejects_wrong_schema_version(session):
    import pytest
    with pytest.raises(ValueError, match="schema_version"):
        import_from_dict(session, {"schema_version": 999, "bills": []})


def test_import_rejects_non_dict_payload(session):
    import pytest
    with pytest.raises(ValueError):
        import_from_dict(session, "not a dict")


def test_import_replace_clears_existing_data(session):
    _seed(session)
    # Now import an EMPTY backup with replace=True — should wipe everything
    empty_backup = {"schema_version": SCHEMA_VERSION}
    import_from_dict(session, empty_backup, replace=True)
    from sqlmodel import select
    assert session.exec(select(RecurringBill)).all() == []
    assert session.exec(select(Envelope)).all() == []


def test_round_trip_via_json_string(session, engine):
    _seed(session)
    backup_json = export_to_json(session)

    from sqlmodel import Session
    with Session(engine) as fresh:
        counts = import_from_json(fresh, backup_json, replace=True)
    assert counts["bills"] == 1
