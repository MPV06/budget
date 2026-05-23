from datetime import date

from models.schema import Account, RecurringBill, BNPLPlan, BNPLInstallment
from services.dashboard_data import build_dashboard_view


def test_dashboard_view_sums_bills_and_bnpl_before_next_paycheck(session):
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=2000.0, available_balance=2000.0)
    session.add(a); session.commit(); session.refresh(a)

    session.add(RecurringBill(source="plaid_auto", merchant_name="Con Ed",
                              display_name="Con Ed", amount=100.0, cadence="monthly",
                              next_due_date=date(2026, 5, 25), category="needs",
                              is_active=True, confirmed_by_user=True))
    session.add(RecurringBill(source="plaid_auto", merchant_name="Rent",
                              display_name="Rent", amount=1200.0, cadence="monthly",
                              next_due_date=date(2026, 6, 1), category="needs",
                              is_active=True, confirmed_by_user=True))

    plan = BNPLPlan(source="manual", provider="affirm", merchant_name="Best Buy",
                    original_amount=200.0, total_payments=4, payment_amount=50.0,
                    cadence="biweekly", start_date=date(2026, 5, 1), is_active=True)
    session.add(plan); session.commit(); session.refresh(plan)
    session.add(BNPLInstallment(plan_id=plan.id, installment_number=2,
                                due_date=date(2026, 5, 22), amount=50.0,
                                status="scheduled"))
    session.commit()

    view = build_dashboard_view(session, today=date(2026, 5, 16),
                                next_paycheck=date(2026, 5, 29))
    assert view.balance == 2000.0
    assert view.bills_due_before_paycheck == 100.0
    assert view.bnpl_due_before_paycheck == 50.0
    assert view.safe_to_spend == 1850.0
