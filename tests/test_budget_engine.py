from datetime import date
from services.budget_engine import (
    safe_to_spend, ObligationItem,
    paycheck_leftover, envelope_status, EnvelopeSpend,
    fifty_thirty_twenty, auto_budget_from_history,
)


def test_safe_to_spend_no_obligations():
    assert safe_to_spend(balance=1000.0, obligations=[]) == 1000.0


def test_safe_to_spend_subtracts_obligations_before_cutoff():
    obs = [
        ObligationItem(due_date=date(2026, 5, 20), amount=100.0, label="Electric"),
        ObligationItem(due_date=date(2026, 5, 25), amount=50.0, label="Phone"),
    ]
    assert safe_to_spend(balance=1000.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == 850.0


def test_safe_to_spend_ignores_obligations_after_cutoff():
    obs = [
        ObligationItem(due_date=date(2026, 5, 20), amount=100.0, label="Electric"),
        ObligationItem(due_date=date(2026, 6, 5), amount=999.0, label="Rent next month"),
    ]
    assert safe_to_spend(balance=1000.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == 900.0


def test_safe_to_spend_can_go_negative():
    obs = [ObligationItem(due_date=date(2026, 5, 20), amount=1500.0, label="Rent")]
    assert safe_to_spend(balance=1000.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == -500.0


def test_obligation_on_cutoff_date_is_excluded():
    # Convention: obligations strictly before next_paycheck deposit are counted.
    obs = [ObligationItem(due_date=date(2026, 5, 29), amount=100.0, label="Edge")]
    assert safe_to_spend(balance=500.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == 500.0


def test_paycheck_leftover_basic():
    result = paycheck_leftover(
        paycheck_amount=2500.0, bills_in_period=800.0, bnpl_in_period=100.0,
        envelopes_allocated=600.0, debt_payments=300.0,
    )
    assert result == 700.0


def test_paycheck_leftover_can_be_negative():
    result = paycheck_leftover(
        paycheck_amount=1000.0, bills_in_period=800.0, bnpl_in_period=100.0,
        envelopes_allocated=600.0, debt_payments=0.0,
    )
    assert result == -500.0


def test_envelope_status_ok():
    s = envelope_status(EnvelopeSpend(name="Groceries", spent=100.0, budget=200.0))
    assert s.remaining == 100.0
    assert s.percent_used == 50.0
    assert s.status == "OK"


def test_envelope_status_warn_at_80():
    s = envelope_status(EnvelopeSpend(name="Gas", spent=80.0, budget=100.0))
    assert s.status == "WARN"


def test_envelope_status_over_at_101():
    s = envelope_status(EnvelopeSpend(name="Restaurants", spent=101.0, budget=100.0))
    assert s.status == "OVER"
    assert s.remaining == -1.0


def test_envelope_status_zero_budget_is_over_if_any_spend():
    s = envelope_status(EnvelopeSpend(name="X", spent=1.0, budget=0.0))
    assert s.status == "OVER"


def test_503020_balanced():
    result = fifty_thirty_twenty(income=1000.0, needs=500.0, wants=300.0, savings_or_debt=200.0)
    assert result.needs_pct == 50.0
    assert result.wants_pct == 30.0
    assert result.savings_pct == 20.0
    assert result.on_target_needs is True
    assert result.on_target_wants is True
    assert result.on_target_savings is True


def test_503020_off_target():
    result = fifty_thirty_twenty(income=1000.0, needs=700.0, wants=200.0, savings_or_debt=100.0)
    assert result.needs_pct == 70.0
    assert result.on_target_needs is False
    assert result.on_target_wants is False
    assert result.on_target_savings is False


def test_503020_within_5pp_is_on_target():
    result = fifty_thirty_twenty(income=1000.0, needs=540.0, wants=280.0, savings_or_debt=180.0)
    assert result.on_target_needs is True
    assert result.on_target_wants is True
    assert result.on_target_savings is True


def test_503020_zero_income_safe():
    result = fifty_thirty_twenty(income=0.0, needs=0.0, wants=0.0, savings_or_debt=0.0)
    assert result.needs_pct == 0.0


def test_auto_budget_3_month_average_per_paycheck():
    # 3 months: 400, 440, 420 ⇒ avg 420/mo ⇒ 210/paycheck
    assert auto_budget_from_history(monthly_totals=[400.0, 440.0, 420.0]) == 210.0


def test_auto_budget_empty_history_returns_zero():
    assert auto_budget_from_history(monthly_totals=[]) == 0.0
