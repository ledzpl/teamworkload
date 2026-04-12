from __future__ import annotations

from contextlib import closing
from datetime import UTC, date, datetime
import sqlite3
import tempfile
import unittest

from workload_analytics.config import Granularity
from workload_analytics.models import (
    DeveloperPeriodMetrics,
    GithubCommitEvent,
    GithubPullRequestEvent,
    JiraAssignedIssueEvent,
    TeamPeriodDeliveryMetrics,
)
from workload_analytics.storage import SQLiteStore


class SQLiteStoreSchemaTest(unittest.TestCase):
    def test_initialize_creates_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(sqlite_path=f"{temp_dir}/workload.sqlite3")

            store.initialize()

            self.assertEqual(
                store.list_tables(),
                (
                    "developer_period_metrics",
                    "normalized_github_commits",
                    "normalized_github_deployments",
                    "normalized_github_pull_requests",
                    "normalized_jira_assigned_issues",
                    "raw_github_commits",
                    "raw_github_deployments",
                    "raw_github_pull_requests",
                    "raw_jira_assigned_issues",
                    "sync_runs",
                    "team_period_delivery_metrics",
                ),
            )

    def test_replace_sync_snapshot_replaces_overlapping_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(sqlite_path=f"{temp_dir}/workload.sqlite3")
            started_at = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
            completed_at = datetime(2026, 4, 9, 10, 1, tzinfo=UTC)

            first_metrics = (
                DeveloperPeriodMetrics(
                    granularity=Granularity.WEEK,
                    developer_email="engineer@example.com",
                    period_start=date(2026, 4, 6),
                    period_end=date(2026, 4, 12),
                    github_prs_merged=1,
                    github_commits_landed=2,
                    github_lines_added=20,
                    github_lines_deleted=5,
                    jira_issues_assigned=3,
                    github_pr_cycle_time_hours=30.0,
                    github_prs_with_cycle_time=1,
                    github_pr_review_wait_hours=4.5,
                    github_prs_with_review_wait=1,
                    github_prs_stale=0,
                    github_prs_small=1,
                    github_prs_medium=0,
                    github_prs_large=0,
                    jira_todo_issues=1,
                    jira_in_progress_issues=1,
                    jira_review_issues=1,
                ),
            )
            second_metrics = (
                DeveloperPeriodMetrics(
                    granularity=Granularity.WEEK,
                    developer_email="engineer@example.com",
                    period_start=date(2026, 4, 6),
                    period_end=date(2026, 4, 12),
                    github_prs_merged=0,
                    github_commits_landed=1,
                    github_lines_added=9,
                    github_lines_deleted=1,
                    jira_issues_assigned=1,
                ),
            )

            store.replace_sync_snapshot(
                run_id="run-1",
                started_at=started_at,
                completed_at=completed_at,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(
                    GithubPullRequestEvent(
                        repository="org/api",
                        pull_request_number=101,
                        author_email="engineer@example.com",
                        merged_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                        lines_added=12,
                        lines_deleted=2,
                    ),
                ),
                normalized_commits=(
                    GithubCommitEvent(
                        repository="org/api",
                        commit_sha="abc123",
                        author_email="engineer@example.com",
                        committed_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                        lines_added=20,
                        lines_deleted=5,
                    ),
                ),
                normalized_jira_issues=(
                    JiraAssignedIssueEvent(
                        project_key="ENG",
                        issue_key="ENG-100",
                        assignee_email="engineer@example.com",
                        updated_at=datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        status_name="In Progress",
                        status_bucket="in_progress",
                    ),
                ),
                aggregates=first_metrics,
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=4,
            )

            store.replace_sync_snapshot(
                run_id="run-2",
                started_at=started_at,
                completed_at=completed_at,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(),
                normalized_commits=(
                    GithubCommitEvent(
                        repository="org/api",
                        commit_sha="def456",
                        author_email="engineer@example.com",
                        committed_at=datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
                        lines_added=9,
                        lines_deleted=1,
                    ),
                ),
                normalized_jira_issues=(
                    JiraAssignedIssueEvent(
                        project_key="ENG",
                        issue_key="ENG-101",
                        assignee_email="engineer@example.com",
                        updated_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
                        status_name="Review",
                        status_bucket="review",
                    ),
                ),
                aggregates=second_metrics,
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=3,
            )

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual(len(metrics), 1)
            self.assertEqual(metrics[0].github_prs_merged, 0)
            self.assertEqual(metrics[0].github_commits_landed, 1)
            self.assertEqual(store.table_row_count("sync_runs"), 2)

    def test_replace_sync_snapshot_persists_pr_flow_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(sqlite_path=f"{temp_dir}/workload.sqlite3")
            now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)

            store.replace_sync_snapshot(
                run_id="run-pr-flow",
                started_at=now,
                completed_at=now,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(),
                normalized_commits=(),
                normalized_deployments=(),
                normalized_jira_issues=(),
                delivery_metrics=(
                    TeamPeriodDeliveryMetrics(
                        granularity=Granularity.WEEK,
                        period_start=date(2026, 4, 6),
                        period_end=date(2026, 4, 12),
                        successful_deployments=1,
                        failed_deployments=1,
                        deployment_lead_time_hours=2.5,
                        deployments_with_lead_time=1,
                    ),
                ),
                aggregates=(
                    DeveloperPeriodMetrics(
                        granularity=Granularity.WEEK,
                        developer_email="engineer@example.com",
                        period_start=date(2026, 4, 6),
                        period_end=date(2026, 4, 12),
                        github_prs_merged=2,
                        github_commits_landed=0,
                        github_lines_added=0,
                        github_lines_deleted=0,
                        jira_issues_assigned=0,
                        github_pr_cycle_time_hours=216.0,
                        github_prs_with_cycle_time=2,
                        github_pr_review_wait_hours=6.0,
                        github_prs_with_review_wait=1,
                        github_prs_stale=1,
                        github_prs_small=1,
                        github_prs_medium=0,
                        github_prs_large=1,
                        jira_todo_issues=1,
                        jira_in_progress_issues=1,
                        jira_review_issues=1,
                        jira_done_issues=0,
                        jira_other_issues=0,
                    ),
                ),
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=1,
            )

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)

            self.assertEqual(metrics[0].github_pr_cycle_time_hours, 216.0)
            self.assertEqual(metrics[0].github_prs_with_cycle_time, 2)
            self.assertEqual(metrics[0].github_pr_review_wait_hours, 6.0)
            self.assertEqual(metrics[0].github_prs_stale, 1)
            self.assertEqual(metrics[0].github_prs_large, 1)
            self.assertEqual(metrics[0].jira_todo_issues, 1)
            self.assertEqual(metrics[0].jira_in_progress_issues, 1)
            self.assertEqual(metrics[0].jira_review_issues, 1)
            delivery_metrics = store.fetch_team_period_delivery_metrics(
                granularity=Granularity.WEEK
            )
            self.assertEqual(delivery_metrics[0].successful_deployments, 1)
            self.assertEqual(delivery_metrics[0].failed_deployments, 1)
            self.assertEqual(delivery_metrics[0].deployment_lead_time_hours, 2.5)

    def test_insert_jira_sync_data_preserves_other_granularities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(sqlite_path=f"{temp_dir}/workload.sqlite3")
            now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
            store.replace_sync_snapshot(
                run_id="run-week",
                started_at=now,
                completed_at=now,
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
                        developer_email="engineer@example.com",
                        period_start=date(2026, 4, 6),
                        period_end=date(2026, 4, 12),
                        github_prs_merged=1,
                        github_commits_landed=1,
                        github_lines_added=10,
                        github_lines_deleted=1,
                        jira_issues_assigned=1,
                    ),
                ),
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=1,
            )
            store.replace_sync_snapshot(
                run_id="run-month",
                started_at=now,
                completed_at=now,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.MONTH,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(),
                normalized_commits=(),
                normalized_jira_issues=(),
                aggregates=(
                    DeveloperPeriodMetrics(
                        granularity=Granularity.MONTH,
                        developer_email="engineer@example.com",
                        period_start=date(2026, 4, 1),
                        period_end=date(2026, 4, 30),
                        github_prs_merged=4,
                        github_commits_landed=7,
                        github_lines_added=70,
                        github_lines_deleted=7,
                        jira_issues_assigned=4,
                    ),
                ),
                delivery_metrics=(
                    TeamPeriodDeliveryMetrics(
                        granularity=Granularity.MONTH,
                        period_start=date(2026, 4, 1),
                        period_end=date(2026, 4, 30),
                        successful_deployments=3,
                    ),
                ),
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=2,
            )

            store.insert_jira_sync_data(
                run_id="jira-week",
                granularity=Granularity.WEEK,
                raw_jira_issues=(),
                normalized_jira_issues=(),
                aggregates=(
                    DeveloperPeriodMetrics(
                        granularity=Granularity.WEEK,
                        developer_email="engineer@example.com",
                        period_start=date(2026, 4, 6),
                        period_end=date(2026, 4, 12),
                        github_prs_merged=1,
                        github_commits_landed=1,
                        github_lines_added=10,
                        github_lines_deleted=1,
                        jira_issues_assigned=5,
                    ),
                ),
                delivery_metrics=(),
            )

            week_metrics = store.fetch_developer_period_metrics(
                granularity=Granularity.WEEK
            )
            month_metrics = store.fetch_developer_period_metrics(
                granularity=Granularity.MONTH
            )
            month_delivery = store.fetch_team_period_delivery_metrics(
                granularity=Granularity.MONTH
            )

            self.assertEqual(week_metrics[0].jira_issues_assigned, 5)
            self.assertEqual(month_metrics[0].jira_issues_assigned, 4)
            self.assertEqual(month_delivery[0].successful_deployments, 3)

    def test_replace_sync_snapshot_deletes_rows_through_end_of_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(sqlite_path=f"{temp_dir}/workload.sqlite3")
            started_at = datetime(2026, 4, 30, 23, 0, tzinfo=UTC)
            completed_at = datetime(2026, 4, 30, 23, 1, tzinfo=UTC)

            store.replace_sync_snapshot(
                run_id="run-1",
                started_at=started_at,
                completed_at=completed_at,
                start_date=date(2026, 4, 30),
                end_date=date(2026, 4, 30),
                granularity=Granularity.DAY,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(),
                normalized_commits=(
                    GithubCommitEvent(
                        repository="org/api",
                        commit_sha="end-of-day",
                        author_email="engineer@example.com",
                        committed_at=datetime(
                            2026,
                            4,
                            30,
                            23,
                            59,
                            59,
                            500000,
                            tzinfo=UTC,
                        ),
                        lines_added=2,
                        lines_deleted=1,
                    ),
                ),
                normalized_jira_issues=(),
                aggregates=(),
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=1,
            )

            store.replace_sync_snapshot(
                run_id="run-2",
                started_at=started_at,
                completed_at=completed_at,
                start_date=date(2026, 4, 30),
                end_date=date(2026, 4, 30),
                granularity=Granularity.DAY,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(),
                normalized_commits=(),
                normalized_jira_issues=(),
                aggregates=(),
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=0,
                unmatched_record_count=0,
                persisted_row_count=0,
            )

            self.assertEqual(store.table_row_count("normalized_github_commits"), 0)

    def test_initialize_adds_missing_sync_run_columns_for_existing_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            connection = sqlite3.connect(sqlite_path)
            connection.execute(
                """
                CREATE TABLE sync_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    granularity TEXT NOT NULL,
                    github_repository_count INTEGER NOT NULL,
                    jira_project_count INTEGER NOT NULL,
                    matched_developer_count INTEGER NOT NULL,
                    unmatched_record_count INTEGER NOT NULL,
                    persisted_row_count INTEGER NOT NULL
                )
                """
            )
            connection.commit()
            connection.close()

            store = SQLiteStore(sqlite_path=sqlite_path)
            store.initialize()

            with closing(sqlite3.connect(sqlite_path)) as migrated_connection:
                columns = migrated_connection.execute(
                    "PRAGMA table_info(sync_runs)"
                ).fetchall()

            column_names = {column[1] for column in columns}
            self.assertIn("discovered_repository_count", column_names)
            self.assertIn("excluded_repository_count", column_names)

    def test_initialize_adds_assigned_jira_metric_column_for_existing_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            connection = sqlite3.connect(sqlite_path)
            connection.execute(
                """
                CREATE TABLE developer_period_metrics (
                    granularity TEXT NOT NULL,
                    developer_email TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    github_prs_merged INTEGER NOT NULL,
                    github_commits_landed INTEGER NOT NULL,
                    github_lines_added INTEGER NOT NULL,
                    github_lines_deleted INTEGER NOT NULL,
                    jira_issues_done INTEGER NOT NULL,
                    synced_run_id TEXT NOT NULL,
                    PRIMARY KEY (granularity, developer_email, period_start)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO developer_period_metrics (
                    granularity,
                    developer_email,
                    period_start,
                    period_end,
                    github_prs_merged,
                    github_commits_landed,
                    github_lines_added,
                    github_lines_deleted,
                    jira_issues_done,
                    synced_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "week",
                    "engineer@example.com",
                    "2026-04-06",
                    "2026-04-12",
                    1,
                    2,
                    20,
                    5,
                    3,
                    "run-1",
                ),
            )
            connection.commit()
            connection.close()

            store = SQLiteStore(sqlite_path=sqlite_path)
            store.initialize()

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual(len(metrics), 1)
            self.assertEqual(metrics[0].jira_issues_assigned, 3)

    def test_table_row_count_rejects_unknown_table_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(sqlite_path=f"{temp_dir}/workload.sqlite3")
            store.initialize()

            with self.assertRaises(ValueError) as context:
                store.table_row_count("missing_table")

            self.assertIn("Unknown SQLite table", str(context.exception))


if __name__ == "__main__":
    unittest.main()
