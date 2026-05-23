from dataclasses import dataclass
from datetime import date

from models.schema import RecurringBill, BNPLPlan, BNPLInstallment, Envelope
from services.paycheck_view import build_paycheck_breakdowns, average_guilt_free


@dataclass
class _Pay:
    scheduled_date: date
    actual_deposit_date: date


SCHEDULE = [
    _Pay(date(2026, 5, 15), date(2026, 5, 15)),
    _Pay(date(2026, 5, 31), date(2026, 5, 29)),  # weekend roll
    _Pay(date(2026, 6, 15), date(2026, 6, 15)),
    _Pay(date(2026, 6, 30), date(2026, 6, 30)),
    _Pay(date(2026, 7, 15), date(2026, 7, 15)),
]


def test_bills_assigned_to_paycheck_that_precedes_due_date(session):
    # Rent due 6/1 → covered by paycheck depositing 5/29
    session.add(RecurringBill(source="manual", merchant_name="Rent", display_name="Rent",
                              amount=1500, cadence="monthly",
                              next_due_date=date(2026, 6, 1), category="needs",
                              is_active=True, confirmed_by_user=True))
    # Electric due 6/12 → also covered by 5/29 paycheck (period ends 6/15)
    session.add(RecurringBill(source="manual", merchant_name="Electric", display_name="Electric",
                              amount=120, cadence="monthly",
                              next_due_date=date(2026, 6, 12), category="needs",
                              is_active=True, confirmed_by_user=True))
    # Netflix due 6/20 → covered by 6/15 paycheck
    session.add(RecurringBill(source="manual", merchant_name="Netflix", display_name="Netflix",
                              amount=16, cadence="monthly",
                              next_due_date=date(2026, 6, 20), category="wants",
                              is_active=True, confirmed_by_user=True))
    session.commit()

    breakdowns = build_paycheck_breakdowns(
        session, SCHEDULE, today=date(2026, 5, 20),
        paycheck_amount=2500, n=3,
    )
    # First period = 5/29 -> 6/15: rent + electric belong here
    assert breakdowns[0].deposit_date == date(2026, 5, 29)
    assert breakdowns[0].bills_total == 1620.0
    # Second period = 6/15 -> 6/30: netflix
    assert breakdowns[1].deposit_date == date(2026, 6, 15)
    assert breakdowns[1].bills_total == 16.0


def test_guilt_free_calculation_per_paycheck(session):
    session.add(RecurringBill(source="manual", merchant_name="Rent", display_name="Rent",
                              amount=1500, cadence="monthly",
                              next_due_date=date(2026, 6, 1), category="needs",
                              is_active=True, confirmed_by_user=True))
    e = Envelope(name="Groceries", current_budget_per_paycheck=200,
                 plaid_category_filter="X", bucket="needs")
    session.add(e)
    session.commit()

    breakdowns = build_paycheck_breakdowns(
        session, SCHEDULE, today=date(2026, 5, 20),
        paycheck_amount=2500, n=2,
    )
    # Paycheck 1: 2500 - 1500 (rent) - 200 (envelope) = 800
    assert breakdowns[0].guilt_free == 800.0
    # Paycheck 2: 2500 - 0 (no bills) - 200 (envelope) = 2300
    assert breakdowns[1].guilt_free == 2300.0


def test_average_guilt_free(session):
    # No bills, just envelopes
    e = Envelope(name="Groceries", current_budget_per_paycheck=100,
                 plaid_category_filter="X", bucket="needs")
    session.add(e); session.commit()
    breakdowns = build_paycheck_breakdowns(
        session, SCHEDULE, today=date(2026, 5, 20), paycheck_amount=2000, n=3,
    )
    assert average_guilt_free(breakdowns) == 1900.0


def test_bnpl_included_in_period(session):
    plan = BNPLPlan(source="manual", provider="affirm", merchant_name="Best Buy",
                    original_amount=200, total_payments=4, payment_amount=50,
                    cadence="biweekly", start_date=date(2026, 5, 1), is_active=True)
    session.add(plan); session.commit(); session.refresh(plan)
    session.add(BNPLInstallment(plan_id=plan.id, installment_number=2,
                                due_date=date(2026, 6, 5), amount=50, status="scheduled"))
    session.commit()

    breakdowns = build_paycheck_breakdowns(
        session, SCHEDULE, today=date(2026, 5, 20), paycheck_amount=2500, n=2,
    )
    assert breakdowns[0].bnpl_total == 50.0
    assert len(breakdowns[0].bnpl) == 1
