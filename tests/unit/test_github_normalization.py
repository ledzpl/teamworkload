from __future__ import annotations

from datetime import UTC, datetime
import unittest

from workload_analytics.clients.github_client import (
    GithubChangedFile,
    GithubCommitPayload,
    GithubDeploymentPayload,
    GithubPullRequestPayload,
)
from workload_analytics.pipelines.github_normalize import (
    normalize_github_activity,
    normalize_github_deployments,
)


class GithubNormalizationTest(unittest.TestCase):
    def test_normalize_github_activity_creates_email_keyed_events(self) -> None:
        result = normalize_github_activity(
            pull_requests=[
                GithubPullRequestPayload(
                    repository="org/api",
                    pull_request_number=101,
                    author_login="api-dev",
                    created_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
                    merged_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
                    first_reviewed_at=datetime(2026, 4, 2, 15, 0, tzinfo=UTC),
                    commit_author_emails=(
                        "Lead.Engineer@example.com",
                        "lead.engineer@example.com",
                        "pair@example.com",
                    ),
                    files=(
                        GithubChangedFile("src/app.py", 12, 2),
                        GithubChangedFile("package-lock.json", 100, 50),
                    ),
                )
            ],
            commits=[
                GithubCommitPayload(
                    repository="org/api",
                    commit_sha="abc123",
                    author_login="api-dev",
                    author_email="Lead.Engineer@example.com",
                    committed_at=datetime(2026, 4, 5, 12, 30, tzinfo=UTC),
                    parent_count=1,
                    files=(
                        GithubChangedFile("src/service.py", 8, 1),
                        GithubChangedFile("vendor/jquery.js", 50, 0),
                    ),
                )
            ],
        )

        self.assertEqual(len(result.pull_requests), 1)
        self.assertEqual(result.pull_requests[0].author_email, "lead.engineer@example.com")
        self.assertEqual(result.pull_requests[0].lines_added, 12)
        self.assertEqual(result.pull_requests[0].lines_deleted, 2)
        self.assertEqual(result.pull_requests[0].created_at, datetime(2026, 4, 2, 9, 0, tzinfo=UTC))
        self.assertEqual(result.pull_requests[0].first_reviewed_at, datetime(2026, 4, 2, 15, 0, tzinfo=UTC))
        self.assertEqual(result.pull_requests[0].cycle_time_hours, 25.0)
        self.assertEqual(result.pull_requests[0].time_to_first_review_hours, 6.0)
        self.assertEqual(result.pull_requests[0].changed_line_count, 14)

        self.assertEqual(len(result.commits), 1)
        self.assertEqual(result.commits[0].author_email, "lead.engineer@example.com")
        self.assertEqual(result.commits[0].lines_added, 8)
        self.assertEqual(result.commits[0].lines_deleted, 1)
        self.assertEqual(result.skipped_records, ())

    def test_normalize_github_activity_skips_merge_commits_and_missing_emails(self) -> None:
        result = normalize_github_activity(
            pull_requests=[
                GithubPullRequestPayload(
                    repository="org/api",
                    pull_request_number=102,
                    author_login="unknown",
                    merged_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
                    commit_author_emails=(),
                    files=(GithubChangedFile("src/app.py", 5, 1),),
                )
            ],
            commits=[
                GithubCommitPayload(
                    repository="org/api",
                    commit_sha="merge123",
                    author_login="api-dev",
                    author_email="api.dev@example.com",
                    committed_at=datetime(2026, 4, 7, 9, 0, tzinfo=UTC),
                    parent_count=2,
                    files=(GithubChangedFile("src/app.py", 9, 3),),
                )
            ],
        )

        self.assertEqual(result.pull_requests, ())
        self.assertEqual(result.commits, ())
        self.assertEqual(
            tuple((item.record_type, item.record_id, item.reason) for item in result.skipped_records),
            (
                ("pull_request", "102", "missing_author_email"),
                ("commit", "merge123", "no_included_file_changes"),
            ),
        )

    def test_normalize_github_deployments_keeps_delivery_statuses(self) -> None:
        deployments = normalize_github_deployments(
            (
                GithubDeploymentPayload(
                    repository="org/api",
                    deployment_id=9001,
                    commit_sha="abc123",
                    environment="production",
                    created_at=datetime(2026, 4, 12, 8, 0, tzinfo=UTC),
                    latest_status_state="success",
                    latest_status_at=datetime(2026, 4, 12, 8, 30, tzinfo=UTC),
                    commit_committed_at=datetime(2026, 4, 12, 6, 0, tzinfo=UTC),
                ),
                GithubDeploymentPayload(
                    repository="org/api",
                    deployment_id=9002,
                    commit_sha="def456",
                    environment="production",
                    created_at=datetime(2026, 4, 13, 8, 0, tzinfo=UTC),
                    latest_status_state="failure",
                    latest_status_at=datetime(2026, 4, 13, 8, 10, tzinfo=UTC),
                    commit_committed_at=datetime(2026, 4, 13, 7, 0, tzinfo=UTC),
                ),
                GithubDeploymentPayload(
                    repository="org/api",
                    deployment_id=9003,
                    commit_sha="ghi789",
                    environment="staging",
                    created_at=datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
                    latest_status_state="in_progress",
                    latest_status_at=datetime(2026, 4, 14, 8, 5, tzinfo=UTC),
                    commit_committed_at=datetime(2026, 4, 14, 7, 0, tzinfo=UTC),
                ),
            )
        )

        self.assertEqual(len(deployments), 2)
        self.assertEqual(deployments[0].status, "success")
        self.assertEqual(deployments[0].deployed_at, datetime(2026, 4, 12, 8, 30, tzinfo=UTC))
        self.assertEqual(deployments[0].lead_time_hours, 2.5)
        self.assertEqual(deployments[1].status, "failure")
        self.assertIsNone(deployments[1].lead_time_hours)


if __name__ == "__main__":
    unittest.main()
