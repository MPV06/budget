"""Per-paycheck breakdown — what's hitting each upcoming paycheck.

Goal: answer "which bills hit THIS paycheck vs the NEXT one" so the user can
see why one paycheck looks healthier than another.

Bills are RECURRING — we project their next_due_date forward by cadence to
generate all instances inside the lookahead window.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List

from dateutil.relativedelta import relativedelta
from sqlmodel import Session, select

from models.schema import RecurringBill, BNPLInstallment, Envelope


_CADENCE_STEP = {
    "weekly":       lambda d: d + timedelta(days=7),
    "biweekly":     lambda d: d + timedelta(days=14),
    # semi_monthly is handled specially in build_paycheck_breakdowns — it emits
    # ONCE PER PAYCHECK PERIOD (matches user intuition: "this bill hits every paycheck")
    "monthly":      lambda d: d + relativedelta(months=1),
    "annual":       lambda d: d + relativedelta(years=1),
}

# Cadences that mean "exactly once per paycheck period, regardless of date math"
PER_PAYCHECK_CADENCES = {"semi_monthly", "per_paycheck"}


def project_bill_instances(
    next_due_date: date, cadence: str, window_start: date, window_end: date,
) -> List[date]:
    """Return all due-date instances of a recurring bill inside [window_start, window_end).

    Advances `next_due_date` forward by cadence until it's >= window_start,
    then emits every instance until window_end.
    """
    step = _CADENCE_STEP.get(cadence.lower())
    if step is None:
        # Unknown cadence — treat as one-time
        return [next_due_date] if window_start <= next_due_date < window_end else []

    cur = next_due_date
    # Skip past instances cheaply
    safety_max = 1200
    safety = 0
    while cur < window_start and safety < safety_max:
        cur = step(cur)
        safety += 1
    # Collect instances within the window
    out: List[date] = []
    safety = 0
    while cur < window_end and safety < safety_max:
        out.append(cur)
        cur = step(cur)
        safety += 1
    return out


@dataclass
class LineItem:
    label: str
    amount: float
    due_date: date
    kind: str  # 'bill' | 'bnpl' | 'envelope'


@dataclass
class PaycheckBreakdown:
    deposit_date: date           # actual deposit date (after weekend/holiday roll)
    scheduled_date: date         # the 15th or last day
    period_start: date           # = deposit_date (or today if before first paycheck)
    period_end: date             # = next paycheck's deposit_date
    paycheck_amount: float
    bills: List[LineItem] = field(default_factory=list)
    bnpl: List[LineItem] = field(default_factory=list)
    envelopes: List[LineItem] = field(default_factory=list)

    @property
    def bills_total(self) -> float:
        return round(sum(b.amount for b in self.bills), 2)

    @property
    def bnpl_total(self) -> float:
        return round(sum(b.amount for b in self.bnpl), 2)

    @property
    def envelopes_allocated(self) -> float:
        return round(sum(e.amount for e in self.envelopes), 2)

    @property
    def obligations_total(self) -> float:
        return round(self.bills_total + self.bnpl_total + self.envelopes_allocated, 2)

    @property
    def guilt_free(self) -> float:
        return round(self.paycheck_amount - self.obligations_total, 2)

    @property
    def days_in_period(self) -> int:
        return max((self.period_end - self.period_start).days, 1)

    @property
    def daily_guilt_free(self) -> float:
        return round(self.guilt_free / self.days_in_period, 2)


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

    upcoming = [p for p in pay_schedule if p.actual_deposit_date >= today][:n + 1]
    if len(upcoming) < 2:
        return []

    out: List[PaycheckBreakdown] = []
    for i in range(min(n, len(upcoming) - 1)):
        this_p = upcoming[i]
        next_p = upcoming[i + 1]
        start = this_p.actual_deposit_date
        end = next_p.actual_deposit_date

        period_bills = []
        for b in bills:
            cadence = (b.cadence or "monthly").lower()
            if cadence in PER_PAYCHECK_CADENCES:
                # Always emit exactly one instance per paycheck period.
                period_bills.append(LineItem(
                    label=b.display_name, amount=b.amount, due_date=start, kind="bill",
                ))
            else:
                instances = project_bill_instances(b.next_due_date, cadence, start, end)
                for d in instances:
                    period_bills.append(LineItem(
                        label=b.display_name, amount=b.amount, due_date=d, kind="bill",
                    ))
        period_bnpl = [
            LineItem(label=f"BNPL #{i_.installment_number}", amount=i_.amount,
                     due_date=i_.due_date, kind="bnpl")
            for i_ in installments if start <= i_.due_date < end
        ]
        period_envelopes = [
            LineItem(
                label=e.name,
                amount=round(
                    e.user_override if e.user_override is not None
                    else e.current_budget_per_paycheck,
                    2,
                ),
                due_date=start,
                kind="envelope",
            )
            for e in envelopes
        ]
        out.append(PaycheckBreakdown(
            deposit_date=this_p.actual_deposit_date,
            scheduled_date=this_p.scheduled_date,
            period_start=start,
            period_end=end,
            paycheck_amount=round(paycheck_amount, 2),
            bills=sorted(period_bills, key=lambda x: x.due_date),
            bnpl=sorted(period_bnpl, key=lambda x: x.due_date),
            envelopes=period_envelopes,
        ))
    return out


def average_guilt_free(breakdowns: List[PaycheckBreakdown]) -> float:
    """Average guilt-free spending across all breakdowns (helps user see typical state)."""
    if not breakdowns:
        return 0.0
    return round(sum(b.guilt_free for b in breakdowns) / len(breakdowns), 2)
