from __future__ import annotations

from datetime import UTC, date, datetime
import unittest

from workload_analytics.config import Granularity
from workload_analytics.pipelines.periods import bucket_period, utc_day_bounds


class PeriodBucketingTest(unittest.TestCase):
    def test_day_bucket_uses_same_start_and_end_date(self) -> None:
        window = bucket_period(datetime(2026, 4, 9, 15, 30), Granularity.DAY)

        self.assertEqual(window.start, date(2026, 4, 9))
        self.assertEqual(window.end, date(2026, 4, 9))

    def test_week_bucket_uses_monday_to_sunday_window(self) -> None:
        window = bucket_period(date(2026, 4, 9), Granularity.WEEK)

        self.assertEqual(window.start, date(2026, 4, 6))
        self.assertEqual(window.end, date(2026, 4, 12))

    def test_month_bucket_uses_full_calendar_month(self) -> None:
        window = bucket_period(date(2026, 2, 18), Granularity.MONTH)

        self.assertEqual(window.start, date(2026, 2, 1))
        self.assertEqual(window.end, date(2026, 2, 28))

    def test_utc_day_bounds_cover_full_end_date(self) -> None:
        start, end = utc_day_bounds(date(2026, 4, 1), date(2026, 4, 30))

        self.assertEqual(start, datetime(2026, 4, 1, 0, 0, tzinfo=UTC))
        self.assertEqual(
            end,
            datetime(2026, 4, 30, 23, 59, 59, 999999, tzinfo=UTC),
        )


if __name__ == "__main__":
    unittest.main()
