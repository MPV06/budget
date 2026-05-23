from datetime import date

from models.schema import RecurringBill, SavingsGoal, SyncState
from services.savings_summary import (
    build_summary, add_per_paycheck_save_line, savings_rate_pct,
)


def test_summary_aggregates_savings_bills(session):
    # User's Excel had "Save -$500" on paycheck 1, "Save -$750" on paycheck 2
    session.add(RecurringBill(
        source="manual", merchant_name="Save P1", display_name="Save P1",
        amount=500, cadence="monthly",
        next_due_date=date(2026, 6, 5), category="savings",
        is_active=True, confirmed_by_user=True,
    ))
    session.add(RecurringBill(
        source="manual", merchant_name="Save P2", display_name="Save P2",
        amount=750, cadence="monthly",
        next_due_date=date(2026, 6, 20), category="savings",
        is_active=True, confirmed_by_user=True,
    ))
    # A non-savings bill (should not be counted)
    session.add(RecurringBill(
        source="manual", merchant_name="Rent", display_name="Rent",
        amount=1500, cadence="monthly",
        next_due_date=date(2026, 6, 1), category="needs",
        is_active=True, confirmed_by_user=True,
    ))
    session.commit()

    summary = build_summary(session)
    # Two savings lines
    assert len(summary.per_paycheck_savings_lines) == 2
    # 500 monthly = 250/paycheck, 750 monthly = 375/paycheck → 625/paycheck total
    assert summary.per_paycheck_savings_total == 625.0
    assert summary.per_month_savings_total == 1250.0
    assert summary.per_year_savings_total == 15000.0


def test_summary_includes_per_paycheck_cadence(session):
    # semi_monthly = once per paycheck (=2x monthly)
    session.add(RecurringBill(
        source="manual", merchant_name="Auto-save", display_name="Auto-save",
        amount=200, cadence="semi_monthly",
        next_due_date=date(2026, 6, 1), category="savings",
        is_active=True, confirmed_by_user=True,
    ))
    session.commit()
    summary = build_summary(session)
    assert summary.per_paycheck_savings_total == 200.0
    assert summary.per_month_savings_total == 400.0


def test_summary_includes_emergency_fund(session):
    session.add(SyncState(key="emergency_fund_balance", value="8500"))
    session.add(SyncState(key="monthly_essentials_override", value="2000"))
    session.commit()
    summary = build_summary(session)
    assert summary.emergency_fund_balance == 8500.0
    assert summary.emergency_fund_target == 12000.0  # 6 * 2000


def test_summary_includes_goals(session):
    session.add(SavingsGoal(
        name="Vacation", target_amount=5000, current_balance=1200,
        target_date=date(2027, 6, 1), priority=3, is_active=True,
    ))
    session.add(SavingsGoal(
        name="Inactive goal", target_amount=999, current_balance=0,
        target_date=date(2027, 6, 1), priority=5, is_active=False,
    ))
    session.commit()
    summary = build_summary(session)
    assert len(summary.goals) == 1
    assert summary.goals[0].name == "Vacation"
    assert summary.goals_saved_total == 1200.0


def test_add_per_paycheck_save_line_creates_active_savings_bill(session):
    bill = add_per_paycheck_save_line(session, name="My new save", amount=300)
    assert bill.category == "savings"
    assert bill.cadence == "semi_monthly"
    assert bill.amount == 300
    assert bill.is_active is True


def test_savings_rate_pct():
    assert savings_rate_pct(500, 2890) == 17.3
    assert savings_rate_pct(0, 2890) == 0.0
    assert savings_rate_pct(500, 0) is None


def test_total_assets_saved(session):
    session.add(SyncState(key="emergency_fund_balance", value="5000"))
    session.add(SavingsGoal(
        name="House", target_amount=20000, current_balance=3000,
        target_date=date(2028, 1, 1), priority=2, is_active=True,
    ))
    session.commit()
    summary = build_summary(session)
    assert summary.total_assets_saved == 8000.0
