from __future__ import annotations

from contextlib import closing
from datetime import UTC, date, datetime
import tempfile
import unittest

from scripts.sync_jira_only import (
    _load_normalized_commits,
    _load_normalized_deployments,
    _load_normalized_prs,
)
from workload_analytics.config import Granularity
from workload_analytics.models import (
    DeveloperPeriodMetrics,
    GithubCommitEvent,
    GithubDeploymentEvent,
    GithubPullRequestEvent,
)
from workload_analytics.pipelines.periods import utc_day_bounds
from workload_analytics.storage import SQLiteStore
from workload_analytics.storage.sqlite_helpers import connect_sqlite


class SyncJiraOnlyLoadersTest(unittest.TestCase):
    def test_existing_github_loaders_limit_rows_to_sync_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            store = SQLiteStore(sqlite_path=sqlite_path)
            now = datetime(2026, 4, 30, 10, 0, tzinfo=UTC)

            store.replace_sync_snapshot(
                run_id="april-run",
                started_at=now,
                completed_at=now,
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
                        merged_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
                        lines_added=10,
                        lines_deleted=2,
                    ),
                ),
                normalized_commits=(
                    GithubCommitEvent(
                        repository="org/api",
                        commit_sha="april-commit",
                        author_email="engineer@example.com",
                        committed_at=datetime(2026, 4, 11, 12, 0, tzinfo=UTC),
                        lines_added=12,
                        lines_deleted=3,
                    ),
                ),
                normalized_deployments=(
                    GithubDeploymentEvent(
                        repository="org/api",
                        deployment_id=1001,
                        environment="production",
                        deployed_at=datetime(2026, 4, 12, 12, 0, tzinfo=UTC),
                        status="success",
                        lead_time_hours=1.5,
                    ),
                ),
                normalized_jira_issues=(),
                aggregates=(
                    DeveloperPeriodMetrics(
                        granularity=Granularity.WEEK,
                        developer_email="engineer@example.com",
                        period_start=date(2026, 4, 6),
                        period_end=date(2026, 4, 12),
                        github_prs_merged=1,
                        github_commits_landed=1,
                        github_lines_added=12,
                        github_lines_deleted=3,
                        jira_issues_assigned=0,
                    ),
                ),
                github_repository_count=1,
                discovered_repository_count=1,
                excluded_repository_count=0,
                jira_project_count=1,
                matched_developer_count=1,
                unmatched_record_count=0,
                persisted_row_count=4,
            )
            store.replace_sync_snapshot(
                run_id="may-run",
                started_at=now,
                completed_at=now,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
                granularity=Granularity.WEEK,
                raw_pull_requests=(),
                raw_commits=(),
                raw_jira_issues=(),
                normalized_pull_requests=(
                    GithubPullRequestEvent(
                        repository="org/api",
                        pull_request_number=201,
                        author_email="engineer@example.com",
                        merged_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
                        lines_added=20,
                        lines_deleted=4,
                    ),
                ),
                normalized_commits=(
                    GithubCommitEvent(
                        repository="org/api",
                        commit_sha="may-commit",
                        author_email="engineer@example.com",
                        committed_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
                        lines_added=22,
                        lines_deleted=5,
                    ),
                ),
                normalized_deployments=(
                    GithubDeploymentEvent(
                        repository="org/api",
                        deployment_id=2001,
                        environment="production",
                        deployed_at=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
                        status="failure",
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
                persisted_row_count=3,
            )

            sync_start, sync_end = utc_day_bounds(date(2026, 4, 1), date(2026, 4, 30))
            with closing(
                connect_sqlite(
                    sqlite_path=sqlite_path,
                    initialize_schema=True,
                    create_parent=False,
                )
            ) as conn:
                prs = _load_normalized_prs(
                    conn,
                    sync_start=sync_start,
                    sync_end=sync_end,
                )
                commits = _load_normalized_commits(
                    conn,
                    sync_start=sync_start,
                    sync_end=sync_end,
                )
                deployments = _load_normalized_deployments(
                    conn,
                    sync_start=sync_start,
                    sync_end=sync_end,
                )

            self.assertEqual([pr.pull_request_number for pr in prs], [101])
            self.assertEqual([commit.commit_sha for commit in commits], ["april-commit"])
            self.assertEqual([deployment.deployment_id for deployment in deployments], [1001])


if __name__ == "__main__":
    unittest.main()
