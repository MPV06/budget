"""Aggregate every dollar earmarked for saving across the app.

Sources counted as savings:
1. RecurringBill with category='savings' (e.g., your "Save -$500" line item)
2. SavingsGoal current_balance (named goals like Vacation Fund)
3. Emergency Fund balance (tracked in SyncState by emergency-fund page)
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from dateutil.relativedelta import relativedelta
from sqlmodel import Session, select

from models.schema import RecurringBill, SavingsGoal, SyncState


@dataclass
class SavingsLine:
    label: str
    amount: float
    source: str  # 'bill' | 'goal' | 'emergency'


@dataclass
class SavingsSummary:
    per_paycheck_savings_lines: List[SavingsLine] = field(default_factory=list)
    emergency_fund_balance: float = 0.0
    emergency_fund_target: float = 0.0
    goals: List[SavingsGoal] = field(default_factory=list)

    @property
    def per_paycheck_savings_total(self) -> float:
        return round(sum(line.amount for line in self.per_paycheck_savings_lines), 2)

    @property
    def per_month_savings_total(self) -> float:
        # Semi-monthly = 2 paychecks per month
        return round(self.per_paycheck_savings_total * 2, 2)

    @property
    def per_year_savings_total(self) -> float:
        return round(self.per_month_savings_total * 12, 2)

    @property
    def goals_saved_total(self) -> float:
        return round(sum(g.current_balance for g in self.goals), 2)

    @property
    def total_assets_saved(self) -> float:
        return round(self.emergency_fund_balance + self.goals_saved_total, 2)


def _monthly_equivalent(amount: float, cadence: str) -> float:
    c = (cadence or "monthly").lower()
    if c == "monthly":
        return amount
    if c == "weekly":
        return amount * 52 / 12
    if c == "biweekly":
        return amount * 26 / 12
    if c in {"semi_monthly", "per_paycheck"}:
        return amount * 2
    if c == "annual":
        return amount / 12
    return amount


def build_summary(session: Session) -> SavingsSummary:
    """Aggregate every savings stream."""
    bills = session.exec(
        select(RecurringBill).where(
            RecurringBill.is_active == True,  # noqa: E712
            RecurringBill.category == "savings",
        )
    ).all()
    per_paycheck_lines: List[SavingsLine] = []
    for b in bills:
        # Normalize every cadence to a per-paycheck dollar amount
        monthly = _monthly_equivalent(b.amount, b.cadence)
        per_pay = monthly / 2  # semi-monthly = 2 paychecks/month
        per_paycheck_lines.append(SavingsLine(
            label=b.display_name, amount=round(per_pay, 2), source="bill",
        ))

    # Emergency fund balance stored on Emergency Fund page in SyncState
    ef_row = session.exec(
        select(SyncState).where(SyncState.key == "emergency_fund_balance")
    ).first()
    ef_balance = float(ef_row.value) if ef_row else 0.0
    ef_target_row = session.exec(
        select(SyncState).where(SyncState.key == "monthly_essentials_override")
    ).first()
    ef_target = (float(ef_target_row.value) * 6) if ef_target_row else 0.0

    goals = session.exec(
        select(SavingsGoal).where(SavingsGoal.is_active == True)  # noqa: E712
        .order_by(SavingsGoal.priority, SavingsGoal.target_date)
    ).all()

    return SavingsSummary(
        per_paycheck_savings_lines=per_paycheck_lines,
        emergency_fund_balance=ef_balance,
        emergency_fund_target=ef_target,
        goals=list(goals),
    )


def add_per_paycheck_save_line(session: Session, name: str, amount: float) -> RecurringBill:
    """Quick helper: create a savings line that hits every paycheck."""
    if amount <= 0:
        raise ValueError("amount must be > 0")
    bill = RecurringBill(
        source="manual",
        merchant_name=name,
        display_name=name,
        amount=amount,
        cadence="semi_monthly",       # = once per paycheck
        next_due_date=date.today(),
        category="savings",
        is_active=True,
        confirmed_by_user=True,
        notes="Created via Save page quick-add",
    )
    session.add(bill)
    session.commit()
    session.refresh(bill)
    return bill


def savings_rate_pct(per_paycheck_savings: float, paycheck_amount: float) -> Optional[float]:
    """Savings rate vs the 15% / 25% / 50% benchmarks from savings-goals standard."""
    if paycheck_amount <= 0:
        return None
    return round(per_paycheck_savings / paycheck_amount * 100, 1)
