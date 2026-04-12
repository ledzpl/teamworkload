from __future__ import annotations

from datetime import UTC, date, datetime
import tempfile
import unittest

from workload_analytics.config import Granularity
from workload_analytics.dashboard.filters import DashboardFilterState
from workload_analytics.dashboard.queries import (
    apply_dashboard_search,
    build_trend_points,
    default_filter_state,
    load_dashboard_data,
)
from workload_analytics.models import DeveloperPeriodMetrics, TeamPeriodDeliveryMetrics
from workload_analytics.storage import SQLiteStore


def _seed_dashboard_store(sqlite_path: str) -> SQLiteStore:
    store = SQLiteStore(sqlite_path=sqlite_path)
    store.replace_sync_snapshot(
        run_id="dashboard-run",
        started_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 20, 9, 1, tzinfo=UTC),
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        granularity=Granularity.WEEK,
        raw_pull_requests=(),
        raw_commits=(),
        raw_jira_issues=(),
        normalized_pull_requests=(),
        normalized_commits=(),
        normalized_jira_issues=(),
        aggregates=(
            DeveloperPeriodMetrics(
                granularity=Granularity.WEEK,
                developer_email="analyst@example.com",
                period_start=date(2026, 4, 6),
                period_end=date(2026, 4, 12),
                github_prs_merged=2,
                github_commits_landed=1,
                github_lines_added=10,
                github_lines_deleted=1,
                jira_issues_assigned=1,
                github_pr_cycle_time_hours=24.0,
                github_prs_with_cycle_time=2,
                github_pr_review_wait_hours=3.0,
                github_prs_with_review_wait=1,
                github_prs_stale=0,
                github_prs_small=1,
                github_prs_medium=1,
                github_prs_large=0,
                jira_in_progress_issues=1,
            ),
            DeveloperPeriodMetrics(
                granularity=Granularity.WEEK,
                developer_email="engineer@example.com",
                period_start=date(2026, 4, 6),
                period_end=date(2026, 4, 12),
                github_prs_merged=1,
                github_commits_landed=3,
                github_lines_added=30,
                github_lines_deleted=5,
                jira_issues_assigned=2,
                github_pr_cycle_time_hours=12.0,
                github_prs_with_cycle_time=1,
                github_pr_review_wait_hours=6.0,
                github_prs_with_review_wait=1,
                github_prs_stale=1,
                github_prs_small=0,
                github_prs_medium=1,
                github_prs_large=0,
                jira_todo_issues=1,
                jira_review_issues=1,
            ),
            DeveloperPeriodMetrics(
                granularity=Granularity.WEEK,
                developer_email="engineer@example.com",
                period_start=date(2026, 4, 13),
                period_end=date(2026, 4, 19),
                github_prs_merged=0,
                github_commits_landed=2,
                github_lines_added=12,
                github_lines_deleted=2,
                jira_issues_assigned=4,
                jira_done_issues=3,
                jira_other_issues=1,
            ),
        ),
        delivery_metrics=(
            TeamPeriodDeliveryMetrics(
                granularity=Granularity.WEEK,
                period_start=date(2026, 4, 6),
                period_end=date(2026, 4, 12),
                successful_deployments=2,
                failed_deployments=1,
                deployment_lead_time_hours=8.0,
                deployments_with_lead_time=2,
            ),
        ),
        github_repository_count=2,
        discovered_repository_count=2,
        excluded_repository_count=0,
        jira_project_count=2,
        matched_developer_count=2,
        unmatched_record_count=1,
        persisted_row_count=3,
    )
    return store


class DashboardQueriesTest(unittest.TestCase):
    def test_default_filter_state_handles_fresh_sqlite_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"

            filters = default_filter_state(sqlite_path)

            self.assertEqual(filters.start_date, date.today())
            self.assertEqual(filters.end_date, date.today())
            self.assertEqual(filters.granularity, Granularity.WEEK)

    def test_load_dashboard_data_handles_fresh_sqlite_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"

            data = load_dashboard_data(
                sqlite_path=sqlite_path,
                filters=DashboardFilterState(
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 4, 3),
                    granularity=Granularity.DAY,
                    developer_email=None,
                ),
            )

            self.assertEqual(data.developer_options, ())
            self.assertEqual(data.filtered_metrics, ())
            self.assertEqual(data.summary.active_developers, 0)
            self.assertEqual(data.summary.period_count, 3)
            self.assertEqual(data.summary.github_prs_merged, 0)
            self.assertEqual(data.summary.github_commits_landed, 0)
            self.assertEqual(data.summary.jira_issues_assigned, 0)
            self.assertEqual(data.summary.successful_deployments, 0)
            self.assertEqual(
                [item.period_start for item in data.trend_points],
                [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)],
            )
            self.assertEqual(
                [item.period_start for item in data.delivery_trend_points],
                [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)],
            )
            self.assertEqual(data.comparison_rows, ())
            self.assertEqual(data.provider_split.scope_label, "Team total")
            self.assertIsNone(data.latest_sync_status)

    def test_load_dashboard_data_builds_summary_and_views(self) -> None:
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
                team_members=("staff.engineer@example.com",),
            )

            self.assertEqual(
                data.developer_options,
                (
                    "analyst@example.com",
                    "engineer@example.com",
                    "staff.engineer@example.com",
                ),
            )
            self.assertEqual(data.summary.active_developers, 2)
            self.assertEqual(data.summary.period_count, 5)
            self.assertEqual(data.summary.github_prs_merged, 3)
            self.assertEqual(data.summary.github_commits_landed, 6)
            self.assertEqual(data.summary.github_lines_added, 52)
            self.assertEqual(data.summary.github_lines_deleted, 8)
            self.assertEqual(data.summary.jira_issues_assigned, 7)
            self.assertEqual(data.summary.github_pr_cycle_time_hours, 36.0)
            self.assertEqual(data.summary.github_prs_with_cycle_time, 3)
            self.assertEqual(data.summary.github_pr_review_wait_hours, 9.0)
            self.assertEqual(data.summary.github_prs_stale, 1)
            self.assertEqual(data.summary.jira_in_progress_issues, 1)
            self.assertEqual(data.summary.jira_review_issues, 1)
            self.assertEqual(data.summary.jira_done_issues, 3)
            self.assertEqual(data.summary.successful_deployments, 2)
            self.assertEqual(data.summary.failed_deployments, 1)
            self.assertEqual(data.summary.deployment_lead_time_hours, 8.0)
            self.assertEqual(len(data.trend_points), 5)
            self.assertEqual(data.trend_points[0].period_start, date(2026, 3, 30))
            self.assertEqual(data.trend_points[0].github_prs_merged, 0)
            self.assertEqual(data.trend_points[1].github_prs_merged, 3)
            self.assertEqual(data.trend_points[1].github_prs_stale, 1)
            self.assertEqual(data.trend_points[-1].period_start, date(2026, 4, 27))
            self.assertEqual(data.trend_points[-1].jira_issues_assigned, 0)
            self.assertEqual(data.delivery_trend_points[1].successful_deployments, 2)
            self.assertEqual(data.delivery_trend_points[1].failed_deployments, 1)
            self.assertEqual(data.comparison_rows[0].developer_email, "analyst@example.com")
            self.assertEqual(data.comparison_rows[1].jira_todo_issues, 1)
            self.assertEqual(data.provider_split.scope_label, "Team total")
            self.assertEqual(data.latest_sync_status.github_repository_count, 2)
            self.assertEqual(data.latest_sync_status.discovered_repository_count, 2)
            self.assertEqual(data.latest_sync_status.excluded_repository_count, 0)

    def test_load_dashboard_data_respects_developer_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_dashboard_store(sqlite_path)

            data = load_dashboard_data(
                sqlite_path=sqlite_path,
                filters=DashboardFilterState(
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 4, 30),
                    granularity=Granularity.WEEK,
                    developer_email="engineer@example.com",
                ),
                team_members=("staff.engineer@example.com",),
            )

            self.assertEqual(len(data.filtered_metrics), 2)
            self.assertEqual(data.summary.active_developers, 1)
            self.assertEqual(data.summary.github_prs_merged, 1)
            self.assertEqual(data.summary.github_commits_landed, 5)
            self.assertEqual(data.summary.jira_issues_assigned, 6)
            self.assertEqual(data.summary.github_prs_stale, 1)
            self.assertEqual(data.summary.jira_review_issues, 1)
            self.assertEqual(data.provider_split.scope_label, "engineer@example.com")

    def test_load_dashboard_data_includes_periods_overlapping_selected_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_dashboard_store(sqlite_path)

            data = load_dashboard_data(
                sqlite_path=sqlite_path,
                filters=DashboardFilterState(
                    start_date=date(2026, 4, 10),
                    end_date=date(2026, 4, 10),
                    granularity=Granularity.WEEK,
                    developer_email=None,
                ),
                team_members=("staff.engineer@example.com",),
            )

            self.assertEqual(len(data.filtered_metrics), 2)
            self.assertEqual(
                data.developer_options,
                (
                    "analyst@example.com",
                    "engineer@example.com",
                    "staff.engineer@example.com",
                ),
            )
            self.assertEqual(data.summary.active_developers, 2)
            self.assertEqual(data.summary.github_prs_merged, 3)
            self.assertEqual(data.summary.github_commits_landed, 4)
            self.assertEqual(data.summary.jira_issues_assigned, 3)
            self.assertEqual(data.summary.successful_deployments, 2)
            self.assertEqual(len(data.trend_points), 1)
            self.assertEqual(data.trend_points[0].period_start, date(2026, 4, 6))
            self.assertEqual(data.delivery_trend_points[0].failed_deployments, 1)

    def test_default_filter_state_uses_latest_sync_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_dashboard_store(sqlite_path)

            filters = default_filter_state(sqlite_path)

            self.assertEqual(filters.start_date, date(2026, 4, 1))
            self.assertEqual(filters.end_date, date(2026, 4, 30))
            self.assertEqual(filters.granularity, Granularity.WEEK)

    def test_build_trend_points_includes_zero_value_daily_periods(self) -> None:
        trend_points = build_trend_points(
            (
                DeveloperPeriodMetrics(
                    granularity=Granularity.DAY,
                    developer_email="engineer@example.com",
                    period_start=date(2026, 4, 2),
                    period_end=date(2026, 4, 2),
                    github_prs_merged=1,
                    github_commits_landed=2,
                    github_lines_added=14,
                    github_lines_deleted=3,
                    jira_issues_assigned=0,
                ),
            ),
            filters=DashboardFilterState(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 3),
                granularity=Granularity.DAY,
                developer_email=None,
            ),
        )

        self.assertEqual(
            [item.period_start for item in trend_points],
            [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)],
        )
        self.assertEqual(trend_points[0].github_commits_landed, 0)
        self.assertEqual(trend_points[1].github_commits_landed, 2)
        self.assertEqual(trend_points[2].jira_issues_assigned, 0)

    def test_load_dashboard_data_keeps_team_members_without_activity_in_sidebar_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_dashboard_store(sqlite_path)

            data = load_dashboard_data(
                sqlite_path=sqlite_path,
                filters=DashboardFilterState(
                    start_date=date(2026, 4, 20),
                    end_date=date(2026, 4, 20),
                    granularity=Granularity.WEEK,
                    developer_email=None,
                ),
                team_members=(
                    "analyst@example.com",
                    "engineer@example.com",
                    "manager@example.com",
                ),
            )

            self.assertEqual(
                data.developer_options,
                (
                    "analyst@example.com",
                    "engineer@example.com",
                    "manager@example.com",
                ),
            )
            self.assertEqual(len(data.filtered_metrics), 0)

    def test_apply_dashboard_search_filters_metrics_and_rebuilds_views(self) -> None:
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

            searched = apply_dashboard_search(data, query="engineer 2026-04-13")

            self.assertEqual(len(searched.filtered_metrics), 1)
            self.assertEqual(searched.filtered_metrics[0].developer_email, "engineer@example.com")
            self.assertEqual(searched.summary.active_developers, 1)
            self.assertEqual(searched.summary.github_commits_landed, 2)
            self.assertEqual(searched.summary.jira_issues_assigned, 4)
            self.assertEqual(searched.summary.successful_deployments, 2)
            self.assertEqual(len(searched.comparison_rows), 1)
            self.assertEqual(searched.comparison_rows[0].developer_email, "engineer@example.com")
            self.assertEqual(searched.provider_split.github_commits_landed, 2)


if __name__ == "__main__":
    unittest.main()
