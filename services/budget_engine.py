from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class ObligationItem:
    due_date: date
    amount: float
    label: str


def safe_to_spend(
    balance: float,
    obligations: List[ObligationItem],
    next_paycheck_date: Optional[date] = None,
) -> float:
    """balance minus obligations strictly before next_paycheck_date.

    If next_paycheck_date is None, no cutoff is applied (all obligations counted).
    """
    if next_paycheck_date is None:
        relevant = obligations
    else:
        relevant = [o for o in obligations if o.due_date < next_paycheck_date]
    total = sum(o.amount for o in relevant)
    return round(balance - total, 2)


@dataclass
class EnvelopeSpend:
    name: str
    spent: float
    budget: float


@dataclass
class EnvelopeStatusResult:
    name: str
    spent: float
    budget: float
    remaining: float
    percent_used: float
    status: str  # OK | WARN | OVER


def paycheck_leftover(
    paycheck_amount: float,
    bills_in_period: float,
    bnpl_in_period: float,
    envelopes_allocated: float,
    debt_payments: float,
) -> float:
    return round(
        paycheck_amount - bills_in_period - bnpl_in_period
        - envelopes_allocated - debt_payments,
        2,
    )


def envelope_status(spend: EnvelopeSpend) -> EnvelopeStatusResult:
    remaining = round(spend.budget - spend.spent, 2)
    pct = (spend.spent / spend.budget * 100.0) if spend.budget > 0 else float("inf")
    if spend.spent > spend.budget:
        status = "OVER"
    elif spend.budget > 0 and spend.spent >= 0.8 * spend.budget:
        status = "WARN"
    else:
        status = "OK"
    return EnvelopeStatusResult(
        name=spend.name,
        spent=round(spend.spent, 2),
        budget=round(spend.budget, 2),
        remaining=remaining,
        percent_used=round(pct, 1) if pct != float("inf") else float("inf"),
        status=status,
    )


@dataclass
class FiftyThirtyTwentyResult:
    needs_pct: float
    wants_pct: float
    savings_pct: float
    on_target_needs: bool
    on_target_wants: bool
    on_target_savings: bool


def fifty_thirty_twenty(
    income: float, needs: float, wants: float, savings_or_debt: float
) -> FiftyThirtyTwentyResult:
    def pct(x):
        return round(x / income * 100.0, 1) if income > 0 else 0.0
    np_, wp_, sp_ = pct(needs), pct(wants), pct(savings_or_debt)
    within = lambda actual, target: abs(actual - target) <= 5.0  # noqa: E731
    return FiftyThirtyTwentyResult(
        needs_pct=np_,
        wants_pct=wp_,
        savings_pct=sp_,
        on_target_needs=within(np_, 50.0),
        on_target_wants=within(wp_, 30.0),
        on_target_savings=within(sp_, 20.0),
    )


def auto_budget_from_history(monthly_totals: List[float]) -> float:
    """Return per-paycheck budget from a list of monthly spend totals.

    Semi-monthly = 2 paychecks per month, so per-paycheck = monthly_avg / 2.
    """
    if not monthly_totals:
        return 0.0
    avg = sum(monthly_totals) / len(monthly_totals)
    return round(avg / 2.0, 2)
