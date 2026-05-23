from collections import defaultdict
from datetime import date
from typing import List

from dateutil.relativedelta import relativedelta
from sqlmodel import Session, select

from models.schema import Transaction


def current_period_spend(session: Session, envelope_id: int,
                         start: date, end: date) -> float:
    rows = session.exec(
        select(Transaction).where(
            Transaction.envelope_id == envelope_id,
            Transaction.posted_date >= start,
            Transaction.posted_date <= end,
        )
    ).all()
    return round(sum(r.amount for r in rows), 2)


def monthly_totals_for_envelope(session: Session, envelope_id: int,
                                 months_back: int, today: date) -> List[float]:
    """Return spend totals for the last `months_back` complete months before `today`."""
    end = date(today.year, today.month, 1) - relativedelta(days=1)
    start = (end.replace(day=1)) - relativedelta(months=months_back - 1)

    rows = session.exec(
        select(Transaction).where(
            Transaction.envelope_id == envelope_id,
            Transaction.posted_date >= start,
            Transaction.posted_date <= end,
        )
    ).all()
    buckets = defaultdict(float)
    for r in rows:
        key = (r.posted_date.year, r.posted_date.month)
        buckets[key] += r.amount

    out = []
    cur = start
    for _ in range(months_back):
        out.append(round(buckets[(cur.year, cur.month)], 2))
        cur = cur + relativedelta(months=1)
    return out
