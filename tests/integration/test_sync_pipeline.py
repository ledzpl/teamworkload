from __future__ import annotations

from datetime import UTC, date, datetime
import tempfile
import unittest

from workload_analytics.clients import (
    GithubChangedFile,
    GithubCommitPayload,
    GithubDeploymentPayload,
    GithubPullRequestPayload,
    GithubRepositoryPayload,
    JiraAssignedIssuePayload,
)
from workload_analytics.config import Granularity, load_settings
from workload_analytics.pipelines.sync_pipeline import SyncProgressEvent, WorkloadSyncPipeline
from workload_analytics.storage import SQLiteStore


class FakeGithubClient:
    def __init__(self) -> None:
        self.discovered_organizations: list[str] = []
        self.pr_fetch_repositories: list[tuple[str, ...]] = []
        self.commit_fetch_repositories: list[tuple[str, ...]] = []
        self.deployment_fetch_repositories: list[tuple[str, ...]] = []
        self.pr_fetch_windows: list[tuple[datetime, datetime]] = []
        self.commit_fetch_windows: list[tuple[datetime, datetime]] = []
        self.deployment_fetch_windows: list[tuple[datetime, datetime]] = []

    def list_organization_repositories(self, *, organization):
        self.discovered_organizations.append(organization)
        return (
            GithubRepositoryPayload(
                full_name="org/api",
                archived=False,
                fork=False,
                private=True,
                visibility="private",
                pushed_at=datetime(2026, 4, 7, 9, 0, tzinfo=UTC),
            ),
            GithubRepositoryPayload(
                full_name="org/web",
                archived=False,
                fork=False,
                private=True,
                visibility="private",
                pushed_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
            ),
            GithubRepositoryPayload(
                full_name="org/archive",
                archived=True,
                fork=False,
                private=True,
                visibility="private",
                pushed_at=datetime(2026, 4, 7, 9, 0, tzinfo=UTC),
            ),
            GithubRepositoryPayload(
                full_name="org/forked",
                archived=False,
                fork=True,
                private=False,
                visibility="public",
                pushed_at=datetime(2026, 4, 7, 9, 0, tzinfo=UTC),
            ),
        )

    def fetch_merged_pull_requests(self, *, repositories, merged_from, merged_to):
        selected_repositories = set(repositories)
        self.pr_fetch_repositories.append(tuple(repositories))
        self.pr_fetch_windows.append((merged_from, merged_to))
        return tuple(
            pull_request
            for pull_request in (
                GithubPullRequestPayload(
                    repository="org/api",
                    pull_request_number=101,
                    author_login="engineer",
                    created_at=datetime(2026, 4, 7, 10, 0, tzinfo=UTC),
                    merged_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    first_reviewed_at=datetime(2026, 4, 7, 14, 0, tzinfo=UTC),
                    commit_author_emails=("engineer@example.com",),
                    files=(GithubChangedFile("src/app.py", 12, 2),),
                ),
                GithubPullRequestPayload(
                    repository="org/web",
                    pull_request_number=102,
                    author_login="missing",
                    merged_at=datetime(2026, 4, 9, 10, 0, tzinfo=UTC),
                    commit_author_emails=(),
                    files=(GithubChangedFile("src/page.tsx", 6, 1),),
                ),
                GithubPullRequestPayload(
                    repository="org/web",
                    pull_request_number=103,
                    author_login="outsider",
                    created_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
                    merged_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
                    commit_author_emails=("outsider@example.com",),
                    files=(GithubChangedFile("src/other.ts", 4, 1),),
                ),
            )
            if pull_request.repository in selected_repositories
        )

    def fetch_commits_landed(self, *, repositories, committed_from, committed_to):
        selected_repositories = set(repositories)
        self.commit_fetch_repositories.append(tuple(repositories))
        self.commit_fetch_windows.append((committed_from, committed_to))
        return tuple(
            commit
            for commit in (
                GithubCommitPayload(
                    repository="org/api",
                    commit_sha="abc123",
                    author_login="engineer",
                    author_email="Engineer@example.com",
                    committed_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                    parent_count=1,
                    files=(GithubChangedFile("src/service.py", 20, 5),),
                ),
                GithubCommitPayload(
                    repository="org/api",
                    commit_sha="merge123",
                    author_login="engineer",
                    author_email="engineer@example.com",
                    committed_at=datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
                    parent_count=2,
                    files=(GithubChangedFile("src/service.py", 10, 1),),
                ),
                GithubCommitPayload(
                    repository="org/web",
                    commit_sha="outsider123",
                    author_login="outsider",
                    author_email="outsider@example.com",
                    committed_at=datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                    parent_count=1,
                    files=(GithubChangedFile("src/outsider.py", 11, 2),),
                ),
            )
            if commit.repository in selected_repositories
        )

    def fetch_deployments(self, *, repositories, deployed_from, deployed_to):
        selected_repositories = set(repositories)
        self.deployment_fetch_repositories.append(tuple(repositories))
        self.deployment_fetch_windows.append((deployed_from, deployed_to))
        return tuple(
            deployment
            for deployment in (
                GithubDeploymentPayload(
                    repository="org/api",
                    deployment_id=9001,
                    commit_sha="abc123",
                    environment="production",
                    created_at=datetime(2026, 4, 8, 13, 0, tzinfo=UTC),
                    latest_status_state="success",
                    latest_status_at=datetime(2026, 4, 8, 13, 30, tzinfo=UTC),
                    commit_committed_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                ),
                GithubDeploymentPayload(
                    repository="org/web",
                    deployment_id=9002,
                    commit_sha="outsider123",
                    environment="production",
                    created_at=datetime(2026, 4, 9, 15, 0, tzinfo=UTC),
                    latest_status_state="failure",
                    latest_status_at=datetime(2026, 4, 9, 15, 10, tzinfo=UTC),
                    commit_committed_at=datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                ),
            )
            if deployment.repository in selected_repositories
        )


class AliasGithubClient(FakeGithubClient):
    def fetch_merged_pull_requests(self, *, repositories, merged_from, merged_to):
        selected_repositories = set(repositories)
        self.pr_fetch_repositories.append(tuple(repositories))
        del merged_from, merged_to
        return tuple(
            pull_request
            for pull_request in (
                GithubPullRequestPayload(
                    repository="org/api",
                    pull_request_number=201,
                    author_login="engineer",
                    merged_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    commit_author_emails=("engineer+github@example.com",),
                    files=(GithubChangedFile("src/app.py", 12, 2),),
                ),
            )
            if pull_request.repository in selected_repositories
        )

    def fetch_commits_landed(self, *, repositories, committed_from, committed_to):
        selected_repositories = set(repositories)
        self.commit_fetch_repositories.append(tuple(repositories))
        del committed_from, committed_to
        return tuple(
            commit
            for commit in (
                GithubCommitPayload(
                    repository="org/api",
                    commit_sha="alias123",
                    author_login="engineer",
                    author_email="engineer+github@example.com",
                    committed_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                    parent_count=1,
                    files=(GithubChangedFile("src/service.py", 20, 5),),
                ),
            )
            if commit.repository in selected_repositories
        )


class GithubNoreplyAliasClient(FakeGithubClient):
    def fetch_merged_pull_requests(self, *, repositories, merged_from, merged_to):
        selected_repositories = set(repositories)
        self.pr_fetch_repositories.append(tuple(repositories))
        del merged_from, merged_to
        return tuple(
            pull_request
            for pull_request in (
                GithubPullRequestPayload(
                    repository="org/api",
                    pull_request_number=301,
                    author_login="engineer-org",
                    merged_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    commit_author_emails=(
                        "123456+engineer_org@users.noreply.github.com",
                    ),
                    files=(GithubChangedFile("src/app.py", 12, 2),),
                ),
            )
            if pull_request.repository in selected_repositories
        )

    def fetch_commits_landed(self, *, repositories, committed_from, committed_to):
        selected_repositories = set(repositories)
        self.commit_fetch_repositories.append(tuple(repositories))
        del committed_from, committed_to
        return tuple(
            commit
            for commit in (
                GithubCommitPayload(
                    repository="org/api",
                    commit_sha="noreply123",
                    author_login="engineer-org",
                    author_email="123456+engineer_org@users.noreply.github.com",
                    committed_at=datetime(2026, 4, 8, 11, 0, tzinfo=UTC),
                    parent_count=1,
                    files=(GithubChangedFile("src/service.py", 20, 5),),
                ),
            )
            if commit.repository in selected_repositories
        )


class FakeJiraClient:
    def __init__(self) -> None:
        self.fetch_windows: list[tuple[datetime, datetime]] = []

    def fetch_assigned_issues(self, *, projects, updated_from, updated_to):
        del projects
        self.fetch_windows.append((updated_from, updated_to))
        return (
            JiraAssignedIssuePayload(
                project_key="ENG",
                issue_key="ENG-101",
                assignee_email="Engineer@example.com",
                assignee_display_name="Engineer One",
                updated_at=datetime(2026, 4, 9, 13, 0, tzinfo=UTC),
                status_name="In Progress",
            ),
            JiraAssignedIssuePayload(
                project_key="WEB",
                issue_key="WEB-102",
                assignee_email=None,
                assignee_display_name="Unknown",
                updated_at=datetime(2026, 4, 9, 14, 0, tzinfo=UTC),
                status_name="To Do",
            ),
            JiraAssignedIssuePayload(
                project_key="ENG",
                issue_key="ENG-103",
                assignee_email="outsider@example.com",
                assignee_display_name="Outside Contributor",
                updated_at=datetime(2026, 4, 10, 14, 0, tzinfo=UTC),
                status_name="Review",
            ),
        )


def _build_settings(
    sqlite_path: str,
    *,
    granularity: str = "week",
    lookback_days: str = "90",
    github_repositories: str = "org/api, org/web",
    github_organization: str = "",
    team_members: str = "",
):
    return load_settings(
        {
            "WORKLOAD_TEAM_NAME": "Platform",
            "WORKLOAD_GITHUB_REPOSITORIES": github_repositories,
            "WORKLOAD_GITHUB_ORGANIZATION": github_organization,
            "WORKLOAD_JIRA_PROJECTS": "ENG, WEB",
            "WORKLOAD_TEAM_MEMBERS": team_members,
            "WORKLOAD_LOOKBACK_DAYS": lookback_days,
            "WORKLOAD_DEFAULT_GRANULARITY": granularity,
            "WORKLOAD_ALLOWED_GRANULARITIES": "day,week,month",
            "GITHUB_TOKEN": "github-token",
            "JIRA_BASE_URL": "https://jira.example.com",
            "JIRA_USER_EMAIL": "jira@example.com",
            "JIRA_API_TOKEN": "jira-token",
            "WORKLOAD_SQLITE_PATH": sqlite_path,
        }
    )


class SyncPipelineIntegrationTest(unittest.TestCase):
    def test_pipeline_fetches_normalizes_aggregates_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(f"{temp_dir}/workload.sqlite3")
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            github_client = FakeGithubClient()
            jira_client = FakeJiraClient()
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=github_client,
                jira_client=jira_client,
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(summary.github_repository_count, 2)
            self.assertEqual(summary.discovered_repository_count, 2)
            self.assertEqual(summary.excluded_repository_count, 0)
            self.assertEqual(summary.jira_project_count, 2)
            self.assertEqual(summary.raw_pull_request_count, 3)
            self.assertEqual(summary.raw_commit_count, 3)
            self.assertEqual(summary.raw_deployment_count, 2)
            self.assertEqual(summary.raw_jira_issue_count, 3)
            self.assertEqual(summary.normalized_pull_request_count, 2)
            self.assertEqual(summary.normalized_commit_count, 2)
            self.assertEqual(summary.normalized_deployment_count, 2)
            self.assertEqual(summary.normalized_jira_issue_count, 2)
            self.assertEqual(summary.delivery_metric_row_count, 1)
            self.assertEqual(summary.persisted_row_count, 22)
            self.assertEqual(summary.unmatched_record_count, 3)
            self.assertEqual(summary.aggregate_row_count, 2)
            self.assertEqual(summary.matched_developer_count, 2)
            self.assertEqual(
                summary.messages,
                (
                    "3 records were skipped because they could not be matched to a developer email.",
                ),
            )
            self.assertEqual(github_client.discovered_organizations, [])
            self.assertEqual(github_client.pr_fetch_repositories, [("org/api", "org/web")])
            self.assertEqual(
                github_client.commit_fetch_repositories,
                [("org/api", "org/web")],
            )
            self.assertEqual(
                github_client.deployment_fetch_repositories,
                [("org/api", "org/web")],
            )
            expected_sync_window = (
                datetime(2026, 4, 1, 0, 0, tzinfo=UTC),
                datetime(2026, 4, 30, 23, 59, 59, 999999, tzinfo=UTC),
            )
            self.assertEqual(github_client.pr_fetch_windows, [expected_sync_window])
            self.assertEqual(github_client.commit_fetch_windows, [expected_sync_window])
            self.assertEqual(github_client.deployment_fetch_windows, [expected_sync_window])
            self.assertEqual(jira_client.fetch_windows, [expected_sync_window])

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual(len(metrics), 2)
            self.assertEqual(metrics[0].developer_email, "engineer@example.com")
            self.assertEqual(metrics[0].github_prs_merged, 1)
            self.assertEqual(metrics[0].github_pr_cycle_time_hours, 24.0)
            self.assertEqual(metrics[0].github_pr_review_wait_hours, 4.0)
            self.assertEqual(metrics[0].github_prs_small, 1)
            self.assertEqual(metrics[0].github_commits_landed, 1)
            self.assertEqual(metrics[0].github_lines_added, 20)
            self.assertEqual(metrics[0].github_lines_deleted, 5)
            self.assertEqual(metrics[0].jira_issues_assigned, 1)
            self.assertEqual(metrics[0].jira_in_progress_issues, 1)
            self.assertEqual(metrics[1].developer_email, "outsider@example.com")
            self.assertEqual(metrics[1].github_prs_merged, 1)
            self.assertEqual(metrics[1].github_prs_stale, 1)
            self.assertEqual(metrics[1].github_commits_landed, 1)
            self.assertEqual(metrics[1].jira_issues_assigned, 1)
            self.assertEqual(metrics[1].jira_review_issues, 1)
            self.assertEqual(store.table_row_count("raw_github_pull_requests"), 3)
            self.assertEqual(store.table_row_count("raw_github_commits"), 3)
            self.assertEqual(store.table_row_count("raw_github_deployments"), 2)
            self.assertEqual(store.table_row_count("raw_jira_assigned_issues"), 3)
            delivery_metrics = store.fetch_team_period_delivery_metrics(
                granularity=Granularity.WEEK
            )
            self.assertEqual(delivery_metrics[0].successful_deployments, 1)
            self.assertEqual(delivery_metrics[0].failed_deployments, 1)
            self.assertEqual(delivery_metrics[0].deployment_lead_time_hours, 2.5)

    def test_pipeline_discovers_org_repositories_and_filters_to_team_members(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(
                f"{temp_dir}/workload.sqlite3",
                github_repositories="",
                github_organization="org",
                team_members="engineer@example.com",
            )
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            github_client = FakeGithubClient()
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=github_client,
                jira_client=FakeJiraClient(),
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(summary.github_repository_count, 1)
            self.assertEqual(summary.discovered_repository_count, 4)
            self.assertEqual(summary.excluded_repository_count, 3)
            self.assertEqual(summary.normalized_pull_request_count, 1)
            self.assertEqual(summary.normalized_commit_count, 1)
            self.assertEqual(summary.normalized_jira_issue_count, 1)
            self.assertEqual(summary.aggregate_row_count, 1)
            self.assertEqual(github_client.discovered_organizations, ["org"])
            self.assertEqual(github_client.pr_fetch_repositories, [("org/api",)])
            self.assertEqual(
                github_client.commit_fetch_repositories,
                [("org/api",)],
            )

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual(len(metrics), 1)
            self.assertEqual(metrics[0].developer_email, "engineer@example.com")
            self.assertEqual(metrics[0].jira_issues_assigned, 1)

    def test_pipeline_filters_explicit_repository_scope_when_team_members_are_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(
                f"{temp_dir}/workload.sqlite3",
                team_members="engineer@example.com",
            )
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=FakeGithubClient(),
                jira_client=FakeJiraClient(),
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(summary.normalized_pull_request_count, 1)
            self.assertEqual(summary.normalized_commit_count, 1)
            self.assertEqual(summary.normalized_jira_issue_count, 1)
            self.assertEqual(summary.aggregate_row_count, 1)

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual([metric.developer_email for metric in metrics], ["engineer@example.com"])

    def test_pipeline_canonicalizes_plus_address_aliases_to_team_members(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(
                f"{temp_dir}/workload.sqlite3",
                team_members="engineer@example.com",
            )
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=AliasGithubClient(),
                jira_client=FakeJiraClient(),
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(summary.normalized_pull_request_count, 1)
            self.assertEqual(summary.normalized_commit_count, 1)
            self.assertEqual(summary.aggregate_row_count, 1)

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual(len(metrics), 1)
            self.assertEqual(metrics[0].developer_email, "engineer@example.com")
            self.assertEqual(metrics[0].github_prs_merged, 1)
            self.assertEqual(metrics[0].github_commits_landed, 1)
            self.assertEqual(metrics[0].github_lines_added, 20)
            self.assertEqual(metrics[0].github_lines_deleted, 5)

    def test_pipeline_canonicalizes_github_noreply_aliases_to_team_members(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(
                f"{temp_dir}/workload.sqlite3",
                team_members="engineer@example.com",
            )
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=GithubNoreplyAliasClient(),
                jira_client=FakeJiraClient(),
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(summary.normalized_pull_request_count, 1)
            self.assertEqual(summary.normalized_commit_count, 1)
            self.assertEqual(summary.aggregate_row_count, 1)

            metrics = store.fetch_developer_period_metrics(granularity=Granularity.WEEK)
            self.assertEqual(len(metrics), 1)
            self.assertEqual(metrics[0].developer_email, "engineer@example.com")
            self.assertEqual(metrics[0].github_prs_merged, 1)
            self.assertEqual(metrics[0].github_commits_landed, 1)
            self.assertEqual(metrics[0].github_lines_added, 20)
            self.assertEqual(metrics[0].github_lines_deleted, 5)

    def test_pipeline_handles_twelve_month_backfill_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(
                f"{temp_dir}/workload.sqlite3",
                granularity="month",
                lookback_days="365",
            )
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=FakeGithubClient(),
                jira_client=FakeJiraClient(),
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2025, 5, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.MONTH,
            )

            self.assertEqual(summary.granularity, Granularity.MONTH)
            metrics = store.fetch_developer_period_metrics(granularity=Granularity.MONTH)
            self.assertEqual(len(metrics), 2)
            self.assertEqual(metrics[0].period_start, date(2026, 4, 1))
            self.assertEqual(metrics[0].period_end, date(2026, 4, 30))

    def test_pipeline_emits_stage_progress_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(f"{temp_dir}/workload.sqlite3")
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            progress_events: list[SyncProgressEvent] = []
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=FakeGithubClient(),
                jira_client=FakeJiraClient(),
                store=store,
                progress_reporter=progress_events.append,
            )

            pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(
                [(event.stage, event.state) for event in progress_events],
                [
                    ("github_repositories", "started"),
                    ("github_repositories", "completed"),
                    ("github_pull_requests", "started"),
                    ("github_pull_requests", "completed"),
                    ("github_commits", "started"),
                    ("github_commits", "completed"),
                    ("github_normalization", "started"),
                    ("github_normalization", "completed"),
                    ("github_deployments", "started"),
                    ("github_deployments", "completed"),
                    ("jira_assigned_issues", "started"),
                    ("jira_assigned_issues", "completed"),
                    ("jira_normalization", "started"),
                    ("jira_normalization", "completed"),
                    ("aggregate_metrics", "started"),
                    ("aggregate_metrics", "completed"),
                    ("aggregate_delivery_metrics", "started"),
                    ("aggregate_delivery_metrics", "completed"),
                    ("sqlite_persist", "started"),
                    ("sqlite_persist", "completed"),
                ],
            )
            self.assertIn("2 repositories in scope", progress_events[1].message)
            self.assertIn("Fetched 3 merged pull requests", progress_events[3].message)
            self.assertIn("Aggregated 2 developer-period rows", progress_events[15].message)


if __name__ == "__main__":
    unittest.main()
