from datetime import date

import pytest

from services.savings_goal import (
    required_monthly_savings, months_until, inflation_adjust, build_plan,
)


def test_required_monthly_zero_when_target_already_met():
    assert required_monthly_savings(target=1000, current_balance=1000, months=12) == 0.0


def test_required_monthly_simple():
    # Save 1200 in 12 months from 0, at ~0 interest: 100/mo
    pmt = required_monthly_savings(target=1200, current_balance=0, months=12, annual_return_pct=0)
    assert pmt == 100.0


def test_required_monthly_with_interest():
    # 12000 in 60 months from 0 at 4%/year ≈ 181/mo
    pmt = required_monthly_savings(target=12000, current_balance=0, months=60, annual_return_pct=4)
    assert 175 < pmt < 185


def test_required_monthly_invalid_months_raises():
    with pytest.raises(ValueError):
        required_monthly_savings(target=1000, current_balance=0, months=0)


def test_months_until_strict():
    assert months_until(date(2027, 5, 23), date(2026, 5, 23)) == 12
    assert months_until(date(2026, 5, 23), date(2026, 5, 23)) == 0


def test_inflation_adjust_compounds():
    # 1000 today, 10 years, 3% inflation ≈ 1343.92
    fv = inflation_adjust(today_amount=1000, years=10, inflation_pct=3.0)
    assert 1343 < fv < 1345


def test_build_plan_on_track():
    today = date(2026, 5, 23)
    plan = build_plan(
        target_today_dollars=1200, current_balance=0,
        target_date=date(2027, 5, 23), today=today,
        affordable_monthly=200, annual_return_pct=0, inflation_pct=0,
    )
    assert plan.required_monthly == 100.0
    assert plan.on_track is True


def test_build_plan_off_track():
    today = date(2026, 5, 23)
    plan = build_plan(
        target_today_dollars=12000, current_balance=0,
        target_date=date(2027, 5, 23), today=today,
        affordable_monthly=100, annual_return_pct=0, inflation_pct=0,
    )
    assert plan.required_monthly == 1000.0
    assert plan.on_track is False
