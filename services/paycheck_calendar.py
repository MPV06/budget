import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import List, Tuple

import holidays

US_HOLIDAYS = holidays.country_holidays("US")


@dataclass(frozen=True)  # frozen → hashable, enables lru_cache on consumers
class PaycheckDate:
    scheduled_date: date
    actual_deposit_date: date


@lru_cache(maxsize=4096)
def adjust_for_weekend_and_holiday(d: date) -> date:
    """Roll back to previous business day if d is weekend or US federal holiday.

    lru_cache: each unique date is computed once across the app's lifetime.
    Pay dates repeat across renders so the hit rate is near 100% in steady state.
    """
    cur = d
    while cur.weekday() >= 5 or cur in US_HOLIDAYS:
        cur -= timedelta(days=1)
    return cur


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


@lru_cache(maxsize=64)
def _generate_paycheck_tuple(start: date, months: int) -> Tuple[PaycheckDate, ...]:
    """Inner cached implementation — returns a tuple (hashable, immutable)."""
    out = []
    cur = date(start.year, start.month, 1)
    for _ in range(months):
        mid = date(cur.year, cur.month, 15)
        last = _last_day_of_month(cur.year, cur.month)
        out.append(PaycheckDate(scheduled_date=mid, actual_deposit_date=adjust_for_weekend_and_holiday(mid)))
        out.append(PaycheckDate(scheduled_date=last, actual_deposit_date=adjust_for_weekend_and_holiday(last)))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return tuple(out)


def generate_paycheck_dates(start: date, months: int) -> List[PaycheckDate]:
    """Generate semi-monthly pay dates (15th + last day) for `months` months from `start`.

    Cached via lru_cache: same (start, months) returns the same list instantly on subsequent calls.
    Returns a fresh list (callers may mutate) wrapping the cached tuple.
    """
    return list(_generate_paycheck_tuple(start, months))


def next_paycheck_after(d: date, calendar_: List[PaycheckDate]) -> PaycheckDate:
    """Return the next PaycheckDate strictly after `d` (using actual_deposit_date)."""
    for p in calendar_:
        if p.actual_deposit_date > d:
            return p
    raise ValueError("No paycheck found after the given date — extend the calendar")
