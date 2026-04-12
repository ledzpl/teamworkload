from __future__ import annotations

from datetime import date
import tempfile
import unittest

from workload_analytics.config import Granularity
from workload_analytics.dashboard.filters import DashboardFilterState
from workload_analytics.dashboard.queries import load_dashboard_data
from workload_analytics.dashboard.report import build_weekly_report
from tests.unit.test_dashboard_queries import _seed_dashboard_store


class WeeklyReportTest(unittest.TestCase):
    def test_build_weekly_report_includes_core_sections(self) -> None:
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

            report = build_weekly_report(data)

        self.assertEqual(report.file_name, "workload-report_2026-04-01_2026-04-30.md")
        self.assertIn("# 팀 워크로드 주간 리포트", report.content)
        self.assertIn("## 팀 활동 요약", report.content)
        self.assertIn("| 활성 개발자 | 2명 |", report.content)
        self.assertIn("## 개발자별 현황", report.content)
        self.assertIn("## PR 흐름 현황", report.content)
        self.assertIn("## Jira WIP 현황", report.content)
        self.assertIn("## 배포 현황", report.content)


if __name__ == "__main__":
    unittest.main()
