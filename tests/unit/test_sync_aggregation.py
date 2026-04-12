from __future__ import annotations

from datetime import UTC, datetime
import unittest

from workload_analytics.config import Granularity
from workload_analytics.models import (
    GithubDeploymentEvent,
    GithubPullRequestEvent,
    JiraAssignedIssueEvent,
)
from workload_analytics.pipelines.sync_pipeline import (
    aggregate_developer_period_metrics,
    aggregate_team_period_delivery_metrics,
)


class SyncAggregationTest(unittest.TestCase):
    def test_aggregate_developer_period_metrics_rolls_up_pr_flow(self) -> None:
        metrics = aggregate_developer_period_metrics(
            granularity=Granularity.WEEK,
            pull_requests=(
                GithubPullRequestEvent(
                    repository="org/api",
                    pull_request_number=101,
                    author_email="engineer@example.com",
                    merged_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    lines_added=70,
                    lines_deleted=20,
                    created_at=datetime(2026, 4, 7, 10, 0, tzinfo=UTC),
                    first_reviewed_at=datetime(2026, 4, 7, 16, 0, tzinfo=UTC),
                    cycle_time_hours=24.0,
                    time_to_first_review_hours=6.0,
                    changed_line_count=90,
                ),
                GithubPullRequestEvent(
                    repository="org/api",
                    pull_request_number=102,
                    author_email="engineer@example.com",
                    merged_at=datetime(2026, 4, 9, 10, 0, tzinfo=UTC),
                    lines_added=300,
                    lines_deleted=220,
                    created_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
                    first_reviewed_at=None,
                    cycle_time_hours=192.0,
                    time_to_first_review_hours=None,
                    changed_line_count=520,
                ),
            ),
            commits=(),
            jira_issues=(),
        )

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].github_pr_cycle_time_hours, 216.0)
        self.assertEqual(metrics[0].github_prs_with_cycle_time, 2)
        self.assertEqual(metrics[0].github_pr_review_wait_hours, 6.0)
        self.assertEqual(metrics[0].github_prs_with_review_wait, 1)
        self.assertEqual(metrics[0].github_prs_stale, 1)
        self.assertEqual(metrics[0].github_prs_small, 1)
        self.assertEqual(metrics[0].github_prs_large, 1)

    def test_aggregate_team_period_delivery_metrics_rolls_up_deployments(self) -> None:
        metrics = aggregate_team_period_delivery_metrics(
            granularity=Granularity.WEEK,
            deployments=(
                GithubDeploymentEvent(
                    repository="org/api",
                    deployment_id=9001,
                    environment="production",
                    deployed_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    status="success",
                    lead_time_hours=2.5,
                ),
                GithubDeploymentEvent(
                    repository="org/api",
                    deployment_id=9002,
                    environment="production",
                    deployed_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                    status="failure",
                    lead_time_hours=None,
                ),
            ),
        )

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].successful_deployments, 1)
        self.assertEqual(metrics[0].failed_deployments, 1)
        self.assertEqual(metrics[0].deployment_lead_time_hours, 2.5)
        self.assertEqual(metrics[0].deployments_with_lead_time, 1)

    def test_aggregate_developer_period_metrics_rolls_up_jira_wip(self) -> None:
        metrics = aggregate_developer_period_metrics(
            granularity=Granularity.WEEK,
            pull_requests=(),
            commits=(),
            jira_issues=(
                JiraAssignedIssueEvent(
                    project_key="ENG",
                    issue_key="ENG-101",
                    assignee_email="engineer@example.com",
                    updated_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    status_name="To Do",
                    status_bucket="todo",
                ),
                JiraAssignedIssueEvent(
                    project_key="ENG",
                    issue_key="ENG-102",
                    assignee_email="engineer@example.com",
                    updated_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                    status_name="In Review",
                    status_bucket="review",
                ),
                JiraAssignedIssueEvent(
                    project_key="ENG",
                    issue_key="ENG-103",
                    assignee_email="engineer@example.com",
                    updated_at=datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
                    status_name="Custom",
                    status_bucket="unmapped",
                ),
            ),
        )

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].jira_issues_assigned, 3)
        self.assertEqual(metrics[0].jira_todo_issues, 1)
        self.assertEqual(metrics[0].jira_review_issues, 1)
        self.assertEqual(metrics[0].jira_other_issues, 1)


if __name__ == "__main__":
    unittest.main()
