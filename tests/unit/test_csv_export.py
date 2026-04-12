from __future__ import annotations

import csv
from datetime import date
from io import StringIO
import tempfile
import unittest

from workload_analytics.config import Granularity
from workload_analytics.dashboard.export import build_filtered_metrics_csv
from workload_analytics.dashboard.filters import DashboardFilterState
from workload_analytics.dashboard.queries import load_dashboard_data
from tests.unit.test_dashboard_queries import _seed_dashboard_store


class CsvExportTest(unittest.TestCase):
    def test_build_filtered_metrics_csv_matches_filtered_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_dashboard_store(sqlite_path)
            data = load_dashboard_data(
                sqlite_path=sqlite_path,
                filters=DashboardFilterState(
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 4, 30),
                    granularity=Granularity.WEEK,
                    developer_email=None,
                ),
            )

            exported = build_filtered_metrics_csv(data)
            rows = list(csv.DictReader(StringIO(exported.content)))

            self.assertEqual(
                exported.file_name,
                "workload-analytics_week_2026-04-01_2026-04-30.csv",
            )
            self.assertEqual(len(rows), len(data.filtered_metrics))
            self.assertEqual(rows[0]["developer_email"], "analyst@example.com")
            self.assertEqual(rows[1]["github_prs_merged"], "1")
            self.assertEqual(rows[2]["jira_issues_assigned"], "4")
            self.assertEqual(rows[0]["github_pr_cycle_time_hours"], "24.0")
            self.assertEqual(rows[1]["jira_review_issues"], "1")


if __name__ == "__main__":
    unittest.main()
