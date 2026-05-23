from datetime import date
from services.paycheck_calendar import adjust_for_weekend_and_holiday, generate_paycheck_dates


def test_weekday_unchanged():
    assert adjust_for_weekend_and_holiday(date(2026, 5, 15)) == date(2026, 5, 15)  # Friday


def test_saturday_moves_to_friday():
    # 2026-05-16 is Saturday
    assert adjust_for_weekend_and_holiday(date(2026, 5, 16)) == date(2026, 5, 15)


def test_sunday_moves_to_friday():
    # 2026-05-17 is Sunday
    assert adjust_for_weekend_and_holiday(date(2026, 5, 17)) == date(2026, 5, 15)


def test_july_4_2026_is_saturday_moves_to_thursday():
    # July 4 2026 is Saturday. Federal observance moves Independence Day to Fri July 3,
    # so the previous business day is Thu July 2.
    assert adjust_for_weekend_and_holiday(date(2026, 7, 4)) == date(2026, 7, 2)


def test_christmas_2026_friday_holiday_moves_to_thursday():
    # 2026-12-25 is Friday and a holiday — moves to Thursday 24th
    assert adjust_for_weekend_and_holiday(date(2026, 12, 25)) == date(2026, 12, 24)


def test_new_years_day_2026_thursday_holiday():
    # 2026-01-01 is Thursday and a holiday — moves to 2025-12-31 Wed
    assert adjust_for_weekend_and_holiday(date(2026, 1, 1)) == date(2025, 12, 31)


def test_generate_paycheck_dates_12_months():
    dates = generate_paycheck_dates(start=date(2026, 1, 1), months=12)
    assert len(dates) == 24
    assert dates[0].scheduled_date == date(2026, 1, 15)
    assert dates[1].scheduled_date == date(2026, 1, 31)
    feb_last = next(d for d in dates if d.scheduled_date.month == 2 and d.scheduled_date.day > 27)
    assert feb_last.scheduled_date == date(2026, 2, 28)


def test_generate_includes_actual_deposit_date():
    dates = generate_paycheck_dates(start=date(2026, 5, 1), months=1)
    may_15 = next(d for d in dates if d.scheduled_date == date(2026, 5, 15))
    assert may_15.actual_deposit_date == date(2026, 5, 15)
    may_31 = next(d for d in dates if d.scheduled_date == date(2026, 5, 31))
    assert may_31.actual_deposit_date == date(2026, 5, 29)
