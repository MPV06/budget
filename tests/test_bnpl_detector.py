from datetime import date
from services.bnpl_detector import detect_provider, project_schedule


def test_detect_affirm():
    assert detect_provider("AFFIRM PURCHASE") == "affirm"
    assert detect_provider("Affirm Inc") == "affirm"


def test_detect_chase_pay_in_4():
    assert detect_provider("CHASE PAY IN 4 PMT") == "chase_pay_in_4"
    assert detect_provider("Chase Pay-in-4 Installment") == "chase_pay_in_4"


def test_detect_klarna_afterpay():
    assert detect_provider("KLARNA*PURCHASE") == "klarna"
    assert detect_provider("AFTERPAY US INC") == "afterpay"


def test_detect_none_for_normal_merchant():
    assert detect_provider("STARBUCKS #1234") is None


def test_project_schedule_4_biweekly():
    start = date(2026, 5, 1)
    plan = project_schedule(start=start, total_payments=4, payment_amount=25.00,
                            cadence="biweekly")
    assert len(plan) == 4
    assert plan[0].due_date == date(2026, 5, 1)
    assert plan[1].due_date == date(2026, 5, 15)
    assert plan[2].due_date == date(2026, 5, 29)
    assert plan[3].due_date == date(2026, 6, 12)
    assert all(p.amount == 25.00 for p in plan)
    assert [p.installment_number for p in plan] == [1, 2, 3, 4]


def test_project_schedule_monthly():
    start = date(2026, 5, 1)
    plan = project_schedule(start=start, total_payments=3, payment_amount=100.00,
                            cadence="monthly")
    assert [p.due_date for p in plan] == [date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1)]
