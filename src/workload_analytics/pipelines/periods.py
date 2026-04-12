from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from workload_analytics.config import Granularity


@dataclass(frozen=True, slots=True)
class PeriodWindow:
    granularity: Granularity
    start: date
    end: date


def bucket_period(value: date | datetime, granularity: Granularity) -> PeriodWindow:
    anchor = value.date() if isinstance(value, datetime) else value

    if granularity is Granularity.DAY:
        return PeriodWindow(granularity=granularity, start=anchor, end=anchor)

    if granularity is Granularity.WEEK:
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        return PeriodWindow(granularity=granularity, start=start, end=end)

    start = anchor.replace(day=1)
    _, month_days = calendar.monthrange(anchor.year, anchor.month)
    end = anchor.replace(day=month_days)
    return PeriodWindow(granularity=granularity, start=start, end=end)


def utc_day_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start_date, time.min, tzinfo=UTC),
        datetime.combine(end_date, time.max, tzinfo=UTC),
    )
