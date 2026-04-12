from __future__ import annotations

from datetime import date, datetime
import unittest

from workload_analytics.config import Granularity
from workload_analytics.models import (
    DeveloperIdentity,
    DeveloperPeriodMetrics,
    GithubCommitEvent,
    GithubPullRequestEvent,
    JiraAssignedIssueEvent,
)


class MetricModelsTest(unittest.TestCase):
    def test_source_events_capture_provider_specific_fields(self) -> None:
        merged_at = datetime(2026, 4, 1, 9, 30)
        committed_at = datetime(2026, 4, 2, 10, 45)
        updated_at = datetime(2026, 4, 3, 17, 15)

        pull_request = GithubPullRequestEvent(
            repository="org/api",
            pull_request_number=42,
            author_email="engineer@example.com",
            merged_at=merged_at,
            lines_added=120,
            lines_deleted=35,
        )
        commit = GithubCommitEvent(
            repository="org/api",
            commit_sha="abc123",
            author_email="engineer@example.com",
            committed_at=committed_at,
            lines_added=20,
            lines_deleted=5,
        )
        issue = JiraAssignedIssueEvent(
            project_key="ENG",
            issue_key="ENG-101",
            assignee_email="engineer@example.com",
            updated_at=updated_at,
        )

        self.assertEqual(pull_request.pull_request_number, 42)
        self.assertEqual(pull_request.merged_at, merged_at)
        self.assertEqual(commit.commit_sha, "abc123")
        self.assertEqual(commit.committed_at, committed_at)
        self.assertEqual(issue.issue_key, "ENG-101")
        self.assertEqual(issue.updated_at, updated_at)

    def test_developer_identity_is_keyed_by_email(self) -> None:
        identity = DeveloperIdentity(
            primary_email="engineer@example.com",
            display_name="Lead Engineer",
            github_logins=("lead-engineer",),
            jira_account_ids=("5f123",),
        )

        self.assertEqual(identity.primary_email, "engineer@example.com")
        self.assertEqual(identity.github_logins, ("lead-engineer",))
        self.assertEqual(identity.jira_account_ids, ("5f123",))

    def test_period_metrics_keep_each_signal_separate(self) -> None:
        metrics = DeveloperPeriodMetrics(
            granularity=Granularity.MONTH,
            developer_email="engineer@example.com",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            github_prs_merged=6,
            github_commits_landed=18,
            github_lines_added=540,
            github_lines_deleted=210,
            jira_issues_assigned=12,
        )

        self.assertEqual(metrics.granularity, Granularity.MONTH)
        self.assertEqual(metrics.github_prs_merged, 6)
        self.assertEqual(metrics.github_commits_landed, 18)
        self.assertEqual(metrics.github_lines_added, 540)
        self.assertEqual(metrics.github_lines_deleted, 210)
        self.assertEqual(metrics.jira_issues_assigned, 12)


if __name__ == "__main__":
    unittest.main()
