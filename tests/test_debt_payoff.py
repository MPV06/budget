from services.debt_payoff import (
    Debt, simulate_payoff,
    front_end_dti, back_end_dti, dti_status,
)


def test_avalanche_targets_highest_rate_first():
    debts = [
        Debt("CC", balance=5000, apr_pct=22, min_payment=100),
        Debt("PL", balance=3000, apr_pct=15, min_payment=75),
        Debt("Student", balance=12000, apr_pct=6, min_payment=150),
    ]
    result = simulate_payoff(debts, extra_monthly=200, strategy="avalanche")
    # First debt paid off should be the highest-rate one (CC)
    assert result.order[0] == "CC"
    assert result.months_to_debt_free > 0


def test_snowball_targets_smallest_balance_first():
    debts = [
        Debt("CC", balance=5000, apr_pct=22, min_payment=100),
        Debt("PL", balance=3000, apr_pct=15, min_payment=75),
        Debt("Student", balance=12000, apr_pct=6, min_payment=150),
    ]
    result = simulate_payoff(debts, extra_monthly=200, strategy="snowball")
    # First debt paid off should be the smallest balance (PL)
    assert result.order[0] == "PL"


def test_avalanche_pays_less_total_interest_than_snowball_typically():
    debts = [
        Debt("CC", balance=5000, apr_pct=22, min_payment=100),
        Debt("PL", balance=3000, apr_pct=15, min_payment=75),
        Debt("Student", balance=12000, apr_pct=6, min_payment=150),
    ]
    aval = simulate_payoff(debts, extra_monthly=200, strategy="avalanche")
    snow = simulate_payoff(debts, extra_monthly=200, strategy="snowball")
    assert aval.total_interest_paid <= snow.total_interest_paid


def test_dti_calculations():
    # Housing 1500 / 6000 gross = 25%
    assert front_end_dti(1500, 6000) == 25.0
    # Total debt 2000 / 6000 = 33.3%
    assert back_end_dti(2000, 6000) == 33.3


def test_dti_status_thresholds():
    assert dti_status(25.0, "front") == "OK"
    assert dti_status(30.0, "front") == "WARN"
    assert dti_status(35.0, "front") == "OVER"
    assert dti_status(33.0, "back") == "OK"
    assert dti_status(40.0, "back") == "WARN"
    assert dti_status(50.0, "back") == "OVER"


def test_dti_zero_income_returns_zero():
    assert front_end_dti(1000, 0) == 0.0
    assert back_end_dti(1000, 0) == 0.0
