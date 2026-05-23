"""Lightweight perf benchmarks to prove caching wins.

Not part of the regular pytest run — invoke explicitly:
    pytest tests/test_perf_bench.py --no-cov -v --no-header
"""
import time
from datetime import date

from services.paycheck_calendar import (
    generate_paycheck_dates, adjust_for_weekend_and_holiday,
    _generate_paycheck_tuple,
)


def test_paycheck_calendar_cache_hit_is_fast():
    """Cache hit should be at least 100x faster than first computation."""
    start = date(2026, 1, 1)
    _generate_paycheck_tuple.cache_clear()
    adjust_for_weekend_and_holiday.cache_clear()

    t0 = time.perf_counter()
    for _ in range(100):
        generate_paycheck_dates(start, 12)
    miss_then_hit = time.perf_counter() - t0  # 1 miss + 99 hits

    t1 = time.perf_counter()
    for _ in range(1000):
        generate_paycheck_dates(start, 12)
    all_hits = time.perf_counter() - t1

    per_hit_us = (all_hits / 1000) * 1_000_000
    print(f"\n  paycheck_calendar avg per call (cache hit): {per_hit_us:.1f} µs")
    # A cache hit should be under 100 microseconds for a 12-month calendar
    assert per_hit_us < 100, f"Cache hit too slow: {per_hit_us:.1f} µs"


def test_adjust_holiday_cache_hit_is_constant_time():
    adjust_for_weekend_and_holiday.cache_clear()
    d = date(2026, 7, 4)  # Saturday holiday — worst case

    t0 = time.perf_counter()
    for _ in range(10000):
        adjust_for_weekend_and_holiday(d)
    elapsed = time.perf_counter() - t0
    per_call_ns = (elapsed / 10000) * 1_000_000_000
    print(f"\n  adjust_for_weekend_and_holiday cache hit: {per_call_ns:.0f} ns/call")
    assert per_call_ns < 50_000, f"Should be sub-microsecond: {per_call_ns:.0f} ns"


def test_db_engine_is_singleton():
    """Engine should be created exactly once across many get_engine() calls."""
    from services.db import get_engine
    engines = {id(get_engine()) for _ in range(100)}
    assert len(engines) == 1, f"Expected 1 engine; got {len(engines)}"
