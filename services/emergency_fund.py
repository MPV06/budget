"""Emergency fund sizing per emergency-fund standards.

3-6 months of *essential* expenses (not total spending). Adjusted by income
stability per the standard rule of thumb.
"""
from dataclasses import dataclass
from typing import Literal

IncomeStability = Literal["dual_stable", "single_stable", "variable", "high_risk"]


@dataclass
class EmergencyFundTarget:
    monthly_essentials: float
    months_recommended: int
    target_amount: float
    months_low: int
    months_high: int
    target_low: float
    target_high: float
    rationale: str


_RULES: dict[IncomeStability, tuple[int, int, int, str]] = {
    # (low, recommended, high, rationale)
    "dual_stable": (3, 4, 6, "Dual income, both stable: 3-month baseline, 4 recommended."),
    "single_stable": (3, 6, 6, "Single income, stable job: 3-6 months; 6 is the safer default."),
    "variable": (6, 9, 12, "Variable income (commission, freelance, gig): 6-12 months."),
    "high_risk": (6, 9, 12, "High job-search risk (executive, niche industry): 6-12 months."),
}


def size_emergency_fund(
    monthly_essentials: float,
    stability: IncomeStability,
) -> EmergencyFundTarget:
    """Return target sized to essential expenses and income stability."""
    if monthly_essentials < 0:
        raise ValueError("monthly_essentials cannot be negative")
    low, rec, high, why = _RULES[stability]
    return EmergencyFundTarget(
        monthly_essentials=round(monthly_essentials, 2),
        months_recommended=rec,
        target_amount=round(monthly_essentials * rec, 2),
        months_low=low,
        months_high=high,
        target_low=round(monthly_essentials * low, 2),
        target_high=round(monthly_essentials * high, 2),
        rationale=why,
    )


def months_of_runway(balance: float, monthly_essentials: float) -> float:
    """How many months of essentials does the current balance cover?"""
    if monthly_essentials <= 0:
        return float("inf")
    return round(balance / monthly_essentials, 2)
