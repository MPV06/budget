"""Savings goal math — required PMT to hit a target by a deadline.

Per the savings-goals standard:
    PMT = FV * r / [(1+r)^n - 1]   (sinking-fund formula)

Inflation-adjust future targets when they are far out.
"""
from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta


@dataclass
class GoalPlan:
    target_amount: float
    target_amount_real: float  # inflation-adjusted (today's dollars)
    months: int
    required_monthly: float
    on_track: bool


def required_monthly_savings(
    target: float,
    current_balance: float,
    months: int,
    annual_return_pct: float = 4.0,
) -> float:
    """Return the monthly PMT needed to reach `target` in `months` months.

    `annual_return_pct=4.0` matches HYSA rates — conservative for short-term goals.
    Returns 0 if target is already met.
    """
    if target <= current_balance:
        return 0.0
    if months <= 0:
        raise ValueError("months must be > 0")
    needed = target - current_balance * ((1 + annual_return_pct / 100 / 12) ** months)
    if needed <= 0:
        return 0.0
    r = annual_return_pct / 100 / 12
    if r == 0:
        return round(needed / months, 2)
    pmt = needed * r / ((1 + r) ** months - 1)
    return round(pmt, 2)


def months_until(target_date: date, today: date) -> int:
    """Whole months between today and the target date (rounded down to >= 1)."""
    if target_date <= today:
        return 0
    delta = relativedelta(target_date, today)
    months = delta.years * 12 + delta.months
    return max(months, 1)


def inflation_adjust(today_amount: float, years: float, inflation_pct: float = 3.0) -> float:
    """Bump today's dollars to future dollars at compound inflation."""
    return round(today_amount * (1 + inflation_pct / 100) ** years, 2)


def build_plan(
    target_today_dollars: float,
    current_balance: float,
    target_date: date,
    today: date,
    affordable_monthly: float,
    annual_return_pct: float = 4.0,
    inflation_pct: float = 3.0,
) -> GoalPlan:
    """Assemble a complete plan for a goal."""
    months = months_until(target_date, today)
    years = (target_date - today).days / 365.25
    target_nominal = inflation_adjust(target_today_dollars, years, inflation_pct) if years > 1 else target_today_dollars
    required = required_monthly_savings(
        target=target_nominal, current_balance=current_balance,
        months=max(months, 1), annual_return_pct=annual_return_pct,
    )
    return GoalPlan(
        target_amount=round(target_nominal, 2),
        target_amount_real=round(target_today_dollars, 2),
        months=months,
        required_monthly=required,
        on_track=affordable_monthly >= required,
    )
