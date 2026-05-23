from dataclasses import dataclass
from datetime import date
from typing import List

from sqlmodel import Session, select

from models.schema import Account, RecurringBill, BNPLInstallment
from services.budget_engine import ObligationItem, safe_to_spend


@dataclass
class DashboardView:
    balance: float
    bills_due_before_paycheck: float
    bnpl_due_before_paycheck: float
    safe_to_spend: float
    upcoming_bills: List[ObligationItem]
    upcoming_bnpl: List[ObligationItem]


def build_dashboard_view(session: Session, today: date, next_paycheck: date) -> DashboardView:
    balance = sum(a.current_balance for a in session.exec(
        select(Account).where(Account.subtype == "checking")
    ).all())

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

    return DashboardView(
        balance=round(balance, 2),
        bills_due_before_paycheck=round(sum(o.amount for o in upcoming_bills), 2),
        bnpl_due_before_paycheck=round(sum(o.amount for o in upcoming_bnpl), 2),
        safe_to_spend=sts,
        upcoming_bills=upcoming_bills,
        upcoming_bnpl=upcoming_bnpl,
    )
