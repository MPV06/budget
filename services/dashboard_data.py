from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlmodel import Session, select

from models.schema import Account, RecurringBill, BNPLInstallment, Envelope, SyncState
from services.budget_engine import (
    ObligationItem, safe_to_spend, paycheck_leftover, fifty_thirty_twenty,
    FiftyThirtyTwentyResult,
)


MANUAL_BALANCE_KEY = "manual_balance"


@dataclass
class DashboardView:
    balance: float
    has_balance_source: bool
    bills_due_before_paycheck: float
    bnpl_due_before_paycheck: float
    bills_this_period: float
    bnpl_this_period: float
    envelopes_this_period: float
    paycheck_amount: float
    leftover_this_paycheck: float
    safe_to_spend: float
    upcoming_bills: List[ObligationItem]
    upcoming_bnpl: List[ObligationItem]
    fifty_thirty_twenty: Optional[FiftyThirtyTwentyResult] = None
    needs_total: float = 0.0
    wants_total: float = 0.0
    savings_total: float = 0.0


def _get_manual_balance(session: Session) -> Optional[float]:
    row = session.exec(select(SyncState).where(SyncState.key == MANUAL_BALANCE_KEY)).first()
    if row is None:
        return None
    try:
        return float(row.value)
    except (TypeError, ValueError):
        return None


def set_manual_balance(session: Session, amount: float) -> None:
    row = session.exec(select(SyncState).where(SyncState.key == MANUAL_BALANCE_KEY)).first()
    if row is None:
        session.add(SyncState(key=MANUAL_BALANCE_KEY, value=str(amount)))
    else:
        row.value = str(amount)
        session.add(row)
    session.commit()


def build_dashboard_view(
    session: Session,
    today: date,
    next_paycheck: date,
    paycheck_amount: float = 0.0,
    period_end: Optional[date] = None,
) -> DashboardView:
    """Build dashboard data.

    `next_paycheck` = next deposit (used to compute safe-to-spend cutoff).
    `period_end` = end of *this* pay period (used to sum bills/BNPL hitting this paycheck).
                   Defaults to `next_paycheck` if not provided.
    """
    if period_end is None:
        period_end = next_paycheck

    # Balance source preference: if there's an actual Plaid-synced checking account
    # (regardless of current balance — $0 is a real balance), use Plaid. Otherwise
    # fall back to user-entered manual balance.
    checking_accounts = session.exec(
        select(Account).where(Account.subtype == "checking")
    ).all()
    manual_balance = _get_manual_balance(session)
    if checking_accounts:
        balance = sum(a.current_balance for a in checking_accounts)
        has_balance_source = True
    elif manual_balance is not None:
        balance = manual_balance
        has_balance_source = True
    else:
        balance = 0.0
        has_balance_source = False

    # Upcoming bills before the next paycheck (for safe-to-spend)
    bills = session.exec(
        select(RecurringBill).where(RecurringBill.is_active == True)  # noqa: E712
    ).all()
    upcoming_bills = [
        ObligationItem(due_date=b.next_due_date, amount=b.amount, label=b.display_name)
        for b in bills
        if today <= b.next_due_date < next_paycheck
    ]

    installments = session.exec(
        select(BNPLInstallment).where(BNPLInstallment.status == "scheduled")
    ).all()
    upcoming_bnpl = [
        ObligationItem(due_date=i.due_date, amount=i.amount, label=f"BNPL #{i.installment_number}")
        for i in installments
        if today <= i.due_date < next_paycheck
    ]

    obligations = upcoming_bills + upcoming_bnpl
    sts = safe_to_spend(balance, obligations, next_paycheck_date=next_paycheck)

    # This pay period totals (covers what the *next* paycheck has to absorb)
    bills_this_period = sum(b.amount for b in bills
                            if today <= b.next_due_date < period_end)
    bnpl_this_period = sum(i.amount for i in installments
                           if today <= i.due_date < period_end)

    envelopes = session.exec(select(Envelope)).all()
    envelopes_this_period = sum(
        (e.user_override if e.user_override is not None else e.current_budget_per_paycheck)
        for e in envelopes
    )

    leftover = paycheck_leftover(
        paycheck_amount=paycheck_amount,
        bills_in_period=bills_this_period,
        bnpl_in_period=bnpl_this_period,
        envelopes_allocated=envelopes_this_period,
        debt_payments=0.0,
    )

    # 50/30/20 view based on this paycheck's allocations
    needs = sum(b.amount for b in bills
                if b.category == "needs" and today <= b.next_due_date < period_end)
    needs += sum(
        (e.user_override if e.user_override is not None else e.current_budget_per_paycheck)
        for e in envelopes if e.bucket == "needs"
    )
    wants = sum(b.amount for b in bills
                if b.category == "wants" and today <= b.next_due_date < period_end)
    wants += sum(
        (e.user_override if e.user_override is not None else e.current_budget_per_paycheck)
        for e in envelopes if e.bucket == "wants"
    )
    # All BNPL counted as wants by default (discretionary purchases on installment)
    wants += bnpl_this_period
    # Savings = leftover after obligations + bills marked 'savings'
    savings = max(0.0, leftover) + sum(
        b.amount for b in bills
        if b.category == "savings" and today <= b.next_due_date < period_end
    )

    ftt = fifty_thirty_twenty(
        income=paycheck_amount, needs=needs, wants=wants, savings_or_debt=savings,
    ) if paycheck_amount > 0 else None

    return DashboardView(
        balance=round(balance, 2),
        has_balance_source=has_balance_source,
        bills_due_before_paycheck=round(sum(o.amount for o in upcoming_bills), 2),
        bnpl_due_before_paycheck=round(sum(o.amount for o in upcoming_bnpl), 2),
        bills_this_period=round(bills_this_period, 2),
        bnpl_this_period=round(bnpl_this_period, 2),
        envelopes_this_period=round(envelopes_this_period, 2),
        paycheck_amount=round(paycheck_amount, 2),
        leftover_this_paycheck=leftover,
        safe_to_spend=sts,
        upcoming_bills=upcoming_bills,
        upcoming_bnpl=upcoming_bnpl,
        fifty_thirty_twenty=ftt,
        needs_total=round(needs, 2),
        wants_total=round(wants, 2),
        savings_total=round(savings, 2),
    )
