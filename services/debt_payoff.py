"""Debt payoff math: avalanche vs snowball, DTI, payoff timeline.

Per debt-management standard:
- Avalanche orders by highest APR first (math-optimal, minimum interest paid)
- Snowball orders by smallest balance first (psychology-optimal, higher adherence)
- DTI front-end = housing / gross monthly income (< 28%)
- DTI back-end = all debt / gross monthly income (< 36%, FHA up to 43%)
"""
from dataclasses import dataclass, field
from typing import List, Literal


@dataclass
class Debt:
    name: str
    balance: float
    apr_pct: float
    min_payment: float


@dataclass
class PayoffStep:
    month: int
    debt_name: str
    payment: float
    interest_paid: float
    principal_paid: float
    remaining_balance: float


@dataclass
class PayoffResult:
    strategy: Literal["avalanche", "snowball"]
    order: List[str]
    months_to_debt_free: int
    total_interest_paid: float
    payoff_log: List[PayoffStep] = field(default_factory=list)


def _next_target(debts: List[Debt], strategy: str) -> Debt:
    active = [d for d in debts if d.balance > 0]
    if not active:
        raise ValueError("No active debts")
    if strategy == "avalanche":
        return max(active, key=lambda d: d.apr_pct)
    return min(active, key=lambda d: d.balance)


def simulate_payoff(
    debts: List[Debt],
    extra_monthly: float,
    strategy: Literal["avalanche", "snowball"],
    max_months: int = 600,
) -> PayoffResult:
    """Simulate paying off debts under the chosen strategy.

    Each month: pay minimums on all, then direct extra + freed-up payments to
    the current target. Stop when all balances are 0.
    """
    # Work on copies — don't mutate caller's data
    ds = [Debt(d.name, d.balance, d.apr_pct, d.min_payment) for d in debts]
    log: List[PayoffStep] = []
    order: List[str] = []
    total_interest = 0.0

    for month in range(1, max_months + 1):
        if all(d.balance <= 0 for d in ds):
            break
        # 1) Accrue this month's interest
        for d in ds:
            if d.balance > 0:
                interest = d.balance * (d.apr_pct / 100 / 12)
                d.balance += interest
                total_interest += interest

        # 2) Compute available payment pool
        active = [d for d in ds if d.balance > 0]
        # Minimums on every active debt
        pool = extra_monthly + sum(d.min_payment for d in ds)  # consistent monthly outlay
        # First apply minimums to all active
        for d in active:
            pay = min(d.min_payment, d.balance)
            d.balance -= pay
            pool -= pay
        # 3) Direct remaining pool to current target
        if pool > 0:
            still_active = [d for d in ds if d.balance > 0]
            if still_active:
                target = _next_target(still_active, strategy)
                pay = min(pool, target.balance)
                target.balance -= pay
                pool -= pay

        # 4) Capture payoff events
        for d in ds:
            if d.balance <= 0 and d.name not in order and any(d.name == x.name for x in ds):
                order.append(d.name)

    months = month if any(d.balance <= 0 for d in ds) else max_months
    months_to_debt_free = months
    if not all(d.balance <= 0 for d in ds):
        # Didn't finish within max_months
        months_to_debt_free = -1

    return PayoffResult(
        strategy=strategy,
        order=order,
        months_to_debt_free=months_to_debt_free,
        total_interest_paid=round(total_interest, 2),
        payoff_log=log,
    )


def front_end_dti(housing_monthly: float, gross_monthly_income: float) -> float:
    """Housing PITI / gross monthly income. Guideline: < 28%."""
    if gross_monthly_income <= 0:
        return 0.0
    return round(housing_monthly / gross_monthly_income * 100, 1)


def back_end_dti(all_debt_monthly: float, gross_monthly_income: float) -> float:
    """All debt payments / gross monthly income. Guideline: < 36%, FHA up to 43%."""
    if gross_monthly_income <= 0:
        return 0.0
    return round(all_debt_monthly / gross_monthly_income * 100, 1)


def dti_status(dti_pct: float, kind: Literal["front", "back"]) -> str:
    """Return 'OK', 'WARN', or 'OVER' per standard guidelines."""
    if kind == "front":
        limits = (28, 31)
    else:
        limits = (36, 43)
    if dti_pct < limits[0]:
        return "OK"
    if dti_pct <= limits[1]:
        return "WARN"
    return "OVER"
