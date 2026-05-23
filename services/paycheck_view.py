"""Per-paycheck breakdown — what's hitting each upcoming paycheck.

Goal: answer "which bills hit THIS paycheck vs the NEXT one" so the user can
see why one paycheck looks healthier than another.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List

from sqlmodel import Session, select

from models.schema import RecurringBill, BNPLInstallment, Envelope


@dataclass
class LineItem:
    label: str
    amount: float
    due_date: date
    kind: str  # 'bill' | 'bnpl'


@dataclass
class PaycheckBreakdown:
    deposit_date: date           # actual deposit date (after weekend/holiday roll)
    scheduled_date: date         # the 15th or last day
    period_start: date           # = deposit_date (or today if before first paycheck)
    period_end: date             # = next paycheck's deposit_date
    paycheck_amount: float
    bills: List[LineItem] = field(default_factory=list)
    bnpl: List[LineItem] = field(default_factory=list)
    envelopes_allocated: float = 0.0

    @property
    def bills_total(self) -> float:
        return round(sum(b.amount for b in self.bills), 2)

    @property
    def bnpl_total(self) -> float:
        return round(sum(b.amount for b in self.bnpl), 2)

    @property
    def obligations_total(self) -> float:
        return round(self.bills_total + self.bnpl_total + self.envelopes_allocated, 2)

    @property
    def guilt_free(self) -> float:
        return round(self.paycheck_amount - self.obligations_total, 2)


def build_paycheck_breakdowns(
    session: Session,
    pay_schedule: List,           # list of PaycheckDate (.actual_deposit_date / .scheduled_date)
    today: date,
    paycheck_amount: float,
    n: int = 4,
) -> List[PaycheckBreakdown]:
    """Return per-paycheck breakdowns for the next `n` paychecks starting from today.

    Bills/BNPL are assigned to the paycheck that PRECEDES their due date
    (you cover next month's rent from this paycheck's leftover after rent hits).

    More precisely: a bill due on `d` belongs to the paycheck-period that
    *contains* `d`. The period for paycheck N runs [N.deposit, N+1.deposit).
    The first period in the list is [today, P1.deposit) — what your
    *current* balance has to cover before the next deposit arrives.
    """
    bills = session.exec(
        select(RecurringBill).where(RecurringBill.is_active == True)  # noqa: E712
    ).all()
    installments = session.exec(
        select(BNPLInstallment).where(BNPLInstallment.status == "scheduled")
    ).all()
    envelopes = session.exec(select(Envelope)).all()
    envelopes_per_paycheck = sum(
        (e.user_override if e.user_override is not None else e.current_budget_per_paycheck)
        for e in envelopes
    )

    upcoming = [p for p in pay_schedule if p.actual_deposit_date >= today][:n + 1]
    if len(upcoming) < 2:
        return []

    out: List[PaycheckBreakdown] = []
    for i in range(min(n, len(upcoming) - 1)):
        this_p = upcoming[i]
        next_p = upcoming[i + 1]
        start = this_p.actual_deposit_date
        end = next_p.actual_deposit_date

        period_bills = [
            LineItem(label=b.display_name, amount=b.amount,
                     due_date=b.next_due_date, kind="bill")
            for b in bills if start <= b.next_due_date < end
        ]
        period_bnpl = [
            LineItem(label=f"BNPL #{i_.installment_number}", amount=i_.amount,
                     due_date=i_.due_date, kind="bnpl")
            for i_ in installments if start <= i_.due_date < end
        ]
        out.append(PaycheckBreakdown(
            deposit_date=this_p.actual_deposit_date,
            scheduled_date=this_p.scheduled_date,
            period_start=start,
            period_end=end,
            paycheck_amount=round(paycheck_amount, 2),
            bills=sorted(period_bills, key=lambda x: x.due_date),
            bnpl=sorted(period_bnpl, key=lambda x: x.due_date),
            envelopes_allocated=round(envelopes_per_paycheck, 2),
        ))
    return out


def average_guilt_free(breakdowns: List[PaycheckBreakdown]) -> float:
    """Average guilt-free spending across all breakdowns (helps user see typical state)."""
    if not breakdowns:
        return 0.0
    return round(sum(b.guilt_free for b in breakdowns) / len(breakdowns), 2)
