from __future__ import annotations

from datetime import UTC, datetime
import unittest

from workload_analytics.clients.jira_client import JiraAssignedIssuePayload
from workload_analytics.pipelines.jira_normalize import normalize_assigned_issues


class JiraNormalizationTest(unittest.TestCase):
    def test_normalize_assigned_issues_keeps_email_keyed_events(self) -> None:
        result = normalize_assigned_issues(
            [
                JiraAssignedIssuePayload(
                    project_key="ENG",
                    issue_key="ENG-101",
                    assignee_email="Lead.Engineer@example.com",
                    assignee_display_name="Lead Engineer",
                    updated_at=datetime(2026, 4, 5, 10, 0, tzinfo=UTC),
                    status_name="In Progress",
                )
            ]
        )

        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].assignee_email, "lead.engineer@example.com")
        self.assertEqual(result.issues[0].issue_key, "ENG-101")
        self.assertEqual(result.issues[0].status_name, "In Progress")
        self.assertEqual(result.issues[0].status_bucket, "in_progress")
        self.assertEqual(result.skipped_issues, ())

    def test_normalize_assigned_issues_surfaces_missing_emails(self) -> None:
        result = normalize_assigned_issues(
            [
                JiraAssignedIssuePayload(
                    project_key="ENG",
                    issue_key="ENG-102",
                    assignee_email=None,
                    assignee_display_name="Unknown",
                    updated_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
                    status_name="To Do",
                )
            ]
        )

        self.assertEqual(result.issues, ())
        self.assertEqual(
            tuple((item.issue_key, item.reason) for item in result.skipped_issues),
            (("ENG-102", "missing_assignee_email"),),
        )


if __name__ == "__main__":
    unittest.main()
