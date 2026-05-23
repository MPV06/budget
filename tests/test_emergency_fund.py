import pytest
from services.emergency_fund import size_emergency_fund, months_of_runway


def test_dual_stable_uses_4mo_default():
    t = size_emergency_fund(monthly_essentials=2000, stability="dual_stable")
    assert t.months_recommended == 4
    assert t.target_amount == 8000.0
    assert t.target_low == 6000.0
    assert t.target_high == 12000.0


def test_single_stable_uses_6mo():
    t = size_emergency_fund(monthly_essentials=2500, stability="single_stable")
    assert t.months_recommended == 6
    assert t.target_amount == 15000.0


def test_variable_uses_9mo_default_with_12_high():
    t = size_emergency_fund(monthly_essentials=2000, stability="variable")
    assert t.months_recommended == 9
    assert t.target_high == 24000.0


def test_negative_essentials_raises():
    with pytest.raises(ValueError):
        size_emergency_fund(monthly_essentials=-100, stability="single_stable")


def test_runway_at_3_months():
    assert months_of_runway(balance=6000, monthly_essentials=2000) == 3.0


def test_runway_zero_essentials_is_infinite():
    assert months_of_runway(balance=1000, monthly_essentials=0) == float("inf")
