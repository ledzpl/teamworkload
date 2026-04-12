from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from uuid import uuid4

from workload_analytics.clients import GithubClient, JiraClient
from workload_analytics.config import AppSettings, Granularity
from workload_analytics.models import (
    DeveloperPeriodMetrics,
    GithubCommitEvent,
    GithubDeploymentEvent,
    GithubPullRequestEvent,
    JiraAssignedIssueEvent,
    TeamPeriodDeliveryMetrics,
)
from workload_analytics.pipelines.github_normalize import (
    normalize_github_activity,
    normalize_github_deployments,
)
from workload_analytics.pipelines.jira_normalize import normalize_assigned_issues
from workload_analytics.pipelines.periods import bucket_period, utc_day_bounds
from workload_analytics.storage import SQLiteStore


@dataclass(frozen=True, slots=True)
class SyncSummary:
    run_id: str
    started_at: datetime
    completed_at: datetime
    start_date: date
    end_date: date
    granularity: Granularity
    github_repository_count: int
    discovered_repository_count: int
    excluded_repository_count: int
    jira_project_count: int
    raw_pull_request_count: int
    raw_commit_count: int
    raw_deployment_count: int
    raw_jira_issue_count: int
    normalized_pull_request_count: int
    normalized_commit_count: int
    normalized_deployment_count: int
    normalized_jira_issue_count: int
    matched_developer_count: int
    unmatched_record_count: int
    aggregate_row_count: int
    delivery_metric_row_count: int
    persisted_row_count: int
    messages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SyncProgressEvent:
    stage: str
    state: str
    message: str


class SyncExecutionError(RuntimeError):
    def __init__(self, *, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class ResolvedGithubScope:
    repositories: tuple[str, ...]
    discovered_repository_count: int
    excluded_repository_count: int


class WorkloadSyncPipeline:
    def __init__(
        self,
        *,
        settings: AppSettings,
        github_client: GithubClient,
        jira_client: JiraClient,
        store: SQLiteStore,
        progress_reporter: Callable[[SyncProgressEvent], None] | None = None,
    ) -> None:
        self._settings = settings
        self._github_client = github_client
        self._jira_client = jira_client
        self._store = store
        self._progress_reporter = progress_reporter

    def run(
        self,
        *,
        start_date: date,
        end_date: date,
        granularity: Granularity,
    ) -> SyncSummary:
        started_at = datetime.now(tz=UTC)
        sync_start, sync_end = utc_day_bounds(start_date, end_date)
        github_scope = self._run_stage(
            "github_repositories",
            lambda: self._resolve_github_scope(sync_start=sync_start),
            started_message="Resolving GitHub repository scope",
            completed_message_builder=self._format_github_scope_message,
        )
        (
            raw_pull_requests,
            raw_commits,
            normalized_pull_requests,
            normalized_commits,
            normalized_github,
        ) = self._fetch_and_normalize_github_activity(
            repositories=github_scope.repositories,
            sync_start=sync_start,
            sync_end=sync_end,
        )
        raw_deployments, normalized_deployments = (
            self._fetch_and_normalize_github_deployments(
                repositories=github_scope.repositories,
                sync_start=sync_start,
                sync_end=sync_end,
            )
        )
        raw_jira_issues, normalized_jira, normalized_jira_issues = (
            self._fetch_and_normalize_jira_activity(
                sync_start=sync_start,
                sync_end=sync_end,
            )
        )
        (
            normalized_pull_requests,
            normalized_commits,
            normalized_jira_issues,
        ) = self._apply_team_scope_filter(
            pull_requests=normalized_pull_requests,
            commits=normalized_commits,
            jira_issues=normalized_jira_issues,
        )

        aggregates = self._run_stage(
            "aggregate_metrics",
            lambda: aggregate_developer_period_metrics(
                granularity=granularity,
                pull_requests=normalized_pull_requests,
                commits=normalized_commits,
                jira_issues=normalized_jira_issues,
            ),
            started_message="Aggregating developer workload metrics",
            completed_message_builder=lambda rows: (
                f"Aggregated {len(rows)} developer-period rows"
            ),
        )
        delivery_metrics = self._run_stage(
            "aggregate_delivery_metrics",
            lambda: aggregate_team_period_delivery_metrics(
                granularity=granularity,
                deployments=normalized_deployments,
            ),
            started_message="Aggregating team delivery metrics",
            completed_message_builder=lambda rows: (
                f"Aggregated {len(rows)} team delivery rows"
            ),
        )

        completed_at = datetime.now(tz=UTC)
        summary = self._build_summary(
            github_scope=github_scope,
            started_at=started_at,
            completed_at=completed_at,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            raw_pull_requests=raw_pull_requests,
            raw_commits=raw_commits,
            raw_deployments=raw_deployments,
            raw_jira_issues=raw_jira_issues,
            normalized_pull_requests=normalized_pull_requests,
            normalized_commits=normalized_commits,
            normalized_deployments=normalized_deployments,
            normalized_jira_issues=normalized_jira_issues,
            normalized_github_skipped_count=len(normalized_github.skipped_records),
            normalized_jira_skipped_count=len(normalized_jira.skipped_issues),
            aggregates=aggregates,
            delivery_metrics=delivery_metrics,
        )
        self._persist_sync_snapshot(
            summary=summary,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            raw_pull_requests=raw_pull_requests,
            raw_commits=raw_commits,
            raw_deployments=raw_deployments,
            raw_jira_issues=raw_jira_issues,
            normalized_pull_requests=normalized_pull_requests,
            normalized_commits=normalized_commits,
            normalized_deployments=normalized_deployments,
            normalized_jira_issues=normalized_jira_issues,
            aggregates=aggregates,
            delivery_metrics=delivery_metrics,
        )

        return summary

    def _fetch_and_normalize_github_activity(
        self,
        *,
        repositories: tuple[str, ...],
        sync_start: datetime,
        sync_end: datetime,
    ):
        raw_pull_requests = self._run_stage(
            "github_pull_requests",
            lambda: self._github_client.fetch_merged_pull_requests(
                repositories=repositories,
                merged_from=sync_start,
                merged_to=sync_end,
            ),
            started_message="Fetching GitHub pull requests",
            completed_message_builder=lambda items: (
                f"Fetched {len(items)} merged pull requests"
            ),
        )
        raw_commits = self._run_stage(
            "github_commits",
            lambda: self._github_client.fetch_commits_landed(
                repositories=repositories,
                committed_from=sync_start,
                committed_to=sync_end,
            ),
            started_message="Fetching GitHub landed commits",
            completed_message_builder=lambda items: (
                f"Fetched {len(items)} landed commits"
            ),
        )
        normalized_github = self._run_stage(
            "github_normalization",
            lambda: normalize_github_activity(
                pull_requests=raw_pull_requests,
                commits=raw_commits,
            ),
            started_message="Normalizing GitHub activity",
            completed_message_builder=lambda result: (
                "Normalized "
                f"{len(result.pull_requests)} pull requests, "
                f"{len(result.commits)} commits, "
                f"skipped {len(result.skipped_records)} GitHub records"
            ),
        )
        return (
            raw_pull_requests,
            raw_commits,
            normalized_github.pull_requests,
            normalized_github.commits,
            normalized_github,
        )

    def _fetch_and_normalize_github_deployments(
        self,
        *,
        repositories: tuple[str, ...],
        sync_start: datetime,
        sync_end: datetime,
    ):
        raw_deployments = self._run_stage(
            "github_deployments",
            lambda: self._github_client.fetch_deployments(
                repositories=repositories,
                deployed_from=sync_start,
                deployed_to=sync_end,
            ),
            started_message="Fetching GitHub deployments",
            completed_message_builder=lambda items: (
                f"Fetched {len(items)} GitHub deployments"
            ),
        )
        normalized_deployments = normalize_github_deployments(raw_deployments)
        return raw_deployments, normalized_deployments

    def _fetch_and_normalize_jira_activity(
        self,
        *,
        sync_start: datetime,
        sync_end: datetime,
    ):
        raw_jira_issues = self._run_stage(
            "jira_assigned_issues",
            lambda: self._jira_client.fetch_assigned_issues(
                projects=self._settings.team_scope.jira_projects,
                updated_from=sync_start,
                updated_to=sync_end,
            ),
            started_message="Fetching assigned Jira issues",
            completed_message_builder=lambda items: (
                f"Fetched {len(items)} assigned Jira issues"
            ),
        )
        normalized_jira = self._run_stage(
            "jira_normalization",
            lambda: normalize_assigned_issues(raw_jira_issues),
            started_message="Normalizing Jira issues",
            completed_message_builder=lambda result: (
                f"Normalized {len(result.issues)} Jira issues, "
                f"skipped {len(result.skipped_issues)} Jira issues"
            ),
        )
        return raw_jira_issues, normalized_jira, normalized_jira.issues

    def _apply_team_scope_filter(
        self,
        *,
        pull_requests: tuple[GithubPullRequestEvent, ...],
        commits: tuple[GithubCommitEvent, ...],
        jira_issues: tuple[JiraAssignedIssueEvent, ...],
    ) -> tuple[
        tuple[GithubPullRequestEvent, ...],
        tuple[GithubCommitEvent, ...],
        tuple[JiraAssignedIssueEvent, ...],
    ]:
        if not self._settings.team_scope.team_members:
            return pull_requests, commits, jira_issues

        return self._run_stage(
            "team_scope_filter",
            lambda: self._filter_normalized_activity_to_team_members(
                pull_requests=pull_requests,
                commits=commits,
                jira_issues=jira_issues,
            ),
            started_message="Filtering normalized activity to configured team members",
            completed_message_builder=lambda filtered: (
                f"Retained {len(filtered[0])} pull requests, "
                f"{len(filtered[1])} commits, "
                f"{len(filtered[2])} Jira issues for configured team members"
            ),
        )

    def _build_summary(
        self,
        *,
        github_scope: ResolvedGithubScope,
        started_at: datetime,
        completed_at: datetime,
        start_date: date,
        end_date: date,
        granularity: Granularity,
        raw_pull_requests: tuple[object, ...],
        raw_commits: tuple[object, ...],
        raw_deployments: tuple[object, ...],
        raw_jira_issues: tuple[object, ...],
        normalized_pull_requests: tuple[GithubPullRequestEvent, ...],
        normalized_commits: tuple[GithubCommitEvent, ...],
        normalized_deployments: tuple[GithubDeploymentEvent, ...],
        normalized_jira_issues: tuple[JiraAssignedIssueEvent, ...],
        normalized_github_skipped_count: int,
        normalized_jira_skipped_count: int,
        aggregates: tuple[DeveloperPeriodMetrics, ...],
        delivery_metrics: tuple[TeamPeriodDeliveryMetrics, ...],
    ) -> SyncSummary:
        unmatched_record_count = (
            normalized_github_skipped_count + normalized_jira_skipped_count
        )
        persisted_row_count = (
            len(raw_pull_requests)
            + len(raw_commits)
            + len(raw_deployments)
            + len(raw_jira_issues)
            + len(normalized_pull_requests)
            + len(normalized_commits)
            + len(normalized_deployments)
            + len(normalized_jira_issues)
            + len(aggregates)
            + len(delivery_metrics)
        )
        return SyncSummary(
            run_id=str(uuid4()),
            started_at=started_at,
            completed_at=completed_at,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            github_repository_count=len(github_scope.repositories),
            discovered_repository_count=github_scope.discovered_repository_count,
            excluded_repository_count=github_scope.excluded_repository_count,
            jira_project_count=len(self._settings.team_scope.jira_projects),
            raw_pull_request_count=len(raw_pull_requests),
            raw_commit_count=len(raw_commits),
            raw_deployment_count=len(raw_deployments),
            raw_jira_issue_count=len(raw_jira_issues),
            normalized_pull_request_count=len(normalized_pull_requests),
            normalized_commit_count=len(normalized_commits),
            normalized_deployment_count=len(normalized_deployments),
            normalized_jira_issue_count=len(normalized_jira_issues),
            matched_developer_count=len({item.developer_email for item in aggregates}),
            unmatched_record_count=unmatched_record_count,
            aggregate_row_count=len(aggregates),
            delivery_metric_row_count=len(delivery_metrics),
            persisted_row_count=persisted_row_count,
            messages=build_sync_messages(
                unmatched_record_count=unmatched_record_count,
                aggregate_row_count=len(aggregates),
            ),
        )

    def _persist_sync_snapshot(
        self,
        *,
        summary: SyncSummary,
        start_date: date,
        end_date: date,
        granularity: Granularity,
        raw_pull_requests: tuple[object, ...],
        raw_commits: tuple[object, ...],
        raw_deployments: tuple[object, ...],
        raw_jira_issues: tuple[object, ...],
        normalized_pull_requests: tuple[GithubPullRequestEvent, ...],
        normalized_commits: tuple[GithubCommitEvent, ...],
        normalized_deployments: tuple[GithubDeploymentEvent, ...],
        normalized_jira_issues: tuple[JiraAssignedIssueEvent, ...],
        aggregates: tuple[DeveloperPeriodMetrics, ...],
        delivery_metrics: tuple[TeamPeriodDeliveryMetrics, ...],
    ) -> None:
        self._run_stage(
            "sqlite_persist",
            lambda: self._store.replace_sync_snapshot(
                run_id=summary.run_id,
                started_at=summary.started_at,
                completed_at=summary.completed_at,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                raw_pull_requests=raw_pull_requests,
                raw_commits=raw_commits,
                raw_deployments=raw_deployments,
                raw_jira_issues=raw_jira_issues,
                normalized_pull_requests=normalized_pull_requests,
                normalized_commits=normalized_commits,
                normalized_deployments=normalized_deployments,
                normalized_jira_issues=normalized_jira_issues,
                aggregates=aggregates,
                delivery_metrics=delivery_metrics,
                github_repository_count=summary.github_repository_count,
                discovered_repository_count=summary.discovered_repository_count,
                excluded_repository_count=summary.excluded_repository_count,
                jira_project_count=summary.jira_project_count,
                matched_developer_count=summary.matched_developer_count,
                unmatched_record_count=summary.unmatched_record_count,
                persisted_row_count=summary.persisted_row_count,
            ),
            started_message="Persisting SQLite snapshot",
            completed_message_builder=lambda _: "Persisted SQLite snapshot",
        )

    def _run_stage(
        self,
        stage: str,
        action,
        *,
        started_message: str,
        completed_message_builder: Callable[[object], str],
    ):
        self._emit_progress(
            SyncProgressEvent(
                stage=stage,
                state="started",
                message=started_message,
            )
        )
        try:
            result = action()
        except SyncExecutionError:
            raise
        except Exception as exc:
            self._emit_progress(
                SyncProgressEvent(
                    stage=stage,
                    state="failed",
                    message=f"{started_message} failed: {exc}",
                )
            )
            raise SyncExecutionError(stage=stage, message=str(exc)) from exc
        self._emit_progress(
            SyncProgressEvent(
                stage=stage,
                state="completed",
                message=completed_message_builder(result),
            )
        )
        return result

    def _emit_progress(self, event: SyncProgressEvent) -> None:
        if self._progress_reporter is not None:
            self._progress_reporter(event)

    def _resolve_github_scope(self, *, sync_start: datetime) -> ResolvedGithubScope:
        organization = self._settings.team_scope.github_organization
        if organization is None:
            repositories = self._settings.team_scope.github_repositories
            return ResolvedGithubScope(
                repositories=repositories,
                discovered_repository_count=len(repositories),
                excluded_repository_count=0,
            )

        discovered_repositories = self._github_client.list_organization_repositories(
            organization=organization
        )
        included_repositories = tuple(
            repository.full_name
            for repository in discovered_repositories
            if (
                not repository.archived
                and not repository.fork
                and (repository.pushed_at is None or repository.pushed_at >= sync_start)
            )
        )
        return ResolvedGithubScope(
            repositories=included_repositories,
            discovered_repository_count=len(discovered_repositories),
            excluded_repository_count=(
                len(discovered_repositories) - len(included_repositories)
            ),
        )

    def _format_github_scope_message(self, scope: ResolvedGithubScope) -> str:
        if scope.excluded_repository_count > 0:
            return (
                f"{len(scope.repositories)} repositories in scope "
                f"({scope.discovered_repository_count} discovered, "
                f"{scope.excluded_repository_count} excluded)"
            )
        return f"{len(scope.repositories)} repositories in scope"

    def _filter_normalized_activity_to_team_members(
        self,
        *,
        pull_requests: Iterable[GithubPullRequestEvent],
        commits: Iterable[GithubCommitEvent],
        jira_issues: Iterable[JiraAssignedIssueEvent],
    ) -> tuple[
        tuple[GithubPullRequestEvent, ...],
        tuple[GithubCommitEvent, ...],
        tuple[JiraAssignedIssueEvent, ...],
    ]:
        return filter_normalized_activity_to_team_members(
            team_members=self._settings.team_scope.team_members,
            pull_requests=pull_requests,
            commits=commits,
            jira_issues=jira_issues,
        )


def aggregate_developer_period_metrics(
    *,
    granularity: Granularity,
    pull_requests: Iterable[GithubPullRequestEvent],
    commits: Iterable[GithubCommitEvent],
    jira_issues: Iterable[JiraAssignedIssueEvent],
) -> tuple[DeveloperPeriodMetrics, ...]:
    aggregates: dict[tuple[date, str], dict[str, int | float | date]] = {}

    for pull_request in pull_requests:
        window = bucket_period(pull_request.merged_at, granularity)
        bucket = _ensure_bucket(aggregates, window.start, window.end, pull_request.author_email)
        bucket["github_prs_merged"] += 1
        if pull_request.cycle_time_hours is not None:
            bucket["github_pr_cycle_time_hours"] += pull_request.cycle_time_hours
            bucket["github_prs_with_cycle_time"] += 1
            if pull_request.cycle_time_hours >= 168:
                bucket["github_prs_stale"] += 1
        if pull_request.time_to_first_review_hours is not None:
            bucket["github_pr_review_wait_hours"] += pull_request.time_to_first_review_hours
            bucket["github_prs_with_review_wait"] += 1
        if pull_request.changed_line_count <= 100:
            bucket["github_prs_small"] += 1
        elif pull_request.changed_line_count <= 500:
            bucket["github_prs_medium"] += 1
        else:
            bucket["github_prs_large"] += 1

    # Overall line totals come from landed commits only so PR counts and line totals
    # can coexist without double-counting the same code change.
    for commit in commits:
        window = bucket_period(commit.committed_at, granularity)
        bucket = _ensure_bucket(aggregates, window.start, window.end, commit.author_email)
        bucket["github_commits_landed"] += 1
        bucket["github_lines_added"] += commit.lines_added
        bucket["github_lines_deleted"] += commit.lines_deleted

    for issue in jira_issues:
        window = bucket_period(issue.updated_at, granularity)
        bucket = _ensure_bucket(aggregates, window.start, window.end, issue.assignee_email)
        bucket["jira_issues_assigned"] += 1
        bucket[f"jira_{_jira_bucket_metric_fragment(issue.status_bucket)}_issues"] += 1

    results = [
        DeveloperPeriodMetrics(
            granularity=granularity,
            developer_email=developer_email,
            period_start=values["period_start"],
            period_end=values["period_end"],
            github_prs_merged=values["github_prs_merged"],
            github_commits_landed=values["github_commits_landed"],
            github_lines_added=values["github_lines_added"],
            github_lines_deleted=values["github_lines_deleted"],
            jira_issues_assigned=values["jira_issues_assigned"],
            github_pr_cycle_time_hours=values["github_pr_cycle_time_hours"],
            github_prs_with_cycle_time=values["github_prs_with_cycle_time"],
            github_pr_review_wait_hours=values["github_pr_review_wait_hours"],
            github_prs_with_review_wait=values["github_prs_with_review_wait"],
            github_prs_stale=values["github_prs_stale"],
            github_prs_small=values["github_prs_small"],
            github_prs_medium=values["github_prs_medium"],
            github_prs_large=values["github_prs_large"],
            jira_todo_issues=values["jira_todo_issues"],
            jira_in_progress_issues=values["jira_in_progress_issues"],
            jira_review_issues=values["jira_review_issues"],
            jira_done_issues=values["jira_done_issues"],
            jira_other_issues=values["jira_other_issues"],
        )
        for (_, developer_email), values in sorted(
            aggregates.items(),
            key=lambda item: (item[1]["period_start"], item[0][1]),
        )
    ]
    return tuple(results)


def aggregate_team_period_delivery_metrics(
    *,
    granularity: Granularity,
    deployments: Iterable[GithubDeploymentEvent],
) -> tuple[TeamPeriodDeliveryMetrics, ...]:
    aggregates: dict[date, dict[str, int | float | date]] = {}

    for deployment in deployments:
        window = bucket_period(deployment.deployed_at, granularity)
        bucket = _ensure_delivery_bucket(aggregates, window.start, window.end)
        if deployment.status == "success":
            bucket["successful_deployments"] += 1
            if deployment.lead_time_hours is not None:
                bucket["deployment_lead_time_hours"] += deployment.lead_time_hours
                bucket["deployments_with_lead_time"] += 1
        elif deployment.status in {"failure", "error"}:
            bucket["failed_deployments"] += 1

    return tuple(
        TeamPeriodDeliveryMetrics(
            granularity=granularity,
            period_start=values["period_start"],
            period_end=values["period_end"],
            successful_deployments=values["successful_deployments"],
            failed_deployments=values["failed_deployments"],
            deployment_lead_time_hours=values["deployment_lead_time_hours"],
            deployments_with_lead_time=values["deployments_with_lead_time"],
        )
        for _, values in sorted(
            aggregates.items(),
            key=lambda item: item[0],
        )
    )


def _ensure_bucket(
    aggregates: dict[tuple[date, str], dict[str, int | float | date]],
    period_start: date,
    period_end: date,
    developer_email: str,
) -> dict[str, int | float | date]:
    key = (period_start, developer_email)
    if key not in aggregates:
        aggregates[key] = {
            "period_start": period_start,
            "period_end": period_end,
            "github_prs_merged": 0,
            "github_commits_landed": 0,
            "github_lines_added": 0,
            "github_lines_deleted": 0,
            "jira_issues_assigned": 0,
            "github_pr_cycle_time_hours": 0.0,
            "github_prs_with_cycle_time": 0,
            "github_pr_review_wait_hours": 0.0,
            "github_prs_with_review_wait": 0,
            "github_prs_stale": 0,
            "github_prs_small": 0,
            "github_prs_medium": 0,
            "github_prs_large": 0,
            "jira_todo_issues": 0,
            "jira_in_progress_issues": 0,
            "jira_review_issues": 0,
            "jira_done_issues": 0,
            "jira_other_issues": 0,
        }
    return aggregates[key]


def _jira_bucket_metric_fragment(status_bucket: str) -> str:
    if status_bucket in {"todo", "in_progress", "review", "done"}:
        return status_bucket
    return "other"


def _ensure_delivery_bucket(
    aggregates: dict[date, dict[str, int | float | date]],
    period_start: date,
    period_end: date,
) -> dict[str, int | float | date]:
    if period_start not in aggregates:
        aggregates[period_start] = {
            "period_start": period_start,
            "period_end": period_end,
            "successful_deployments": 0,
            "failed_deployments": 0,
            "deployment_lead_time_hours": 0.0,
            "deployments_with_lead_time": 0,
        }
    return aggregates[period_start]


def build_sync_messages(
    *,
    unmatched_record_count: int,
    aggregate_row_count: int,
) -> tuple[str, ...]:
    messages: list[str] = []
    if aggregate_row_count == 0:
        messages.append("No workload records matched the selected date range.")
    if unmatched_record_count > 0:
        messages.append(
            f"{unmatched_record_count} records were skipped because they could not be matched to a developer email."
        )
    return tuple(messages)


def filter_normalized_activity_to_team_members(
    *,
    team_members: Iterable[str],
    pull_requests: Iterable[GithubPullRequestEvent],
    commits: Iterable[GithubCommitEvent],
    jira_issues: Iterable[JiraAssignedIssueEvent],
) -> tuple[
    tuple[GithubPullRequestEvent, ...],
    tuple[GithubCommitEvent, ...],
    tuple[JiraAssignedIssueEvent, ...],
]:
    allowed_emails = {email.strip().lower() for email in team_members if email.strip()}
    if not allowed_emails:
        return tuple(pull_requests), tuple(commits), tuple(jira_issues)

    noreply_index = _build_noreply_local_part_index(allowed_emails)
    filtered_pull_requests = _filter_and_remap_emails(
        pull_requests,
        email_getter=lambda pr: pr.author_email,
        replacer=lambda pr, email: replace(pr, author_email=email),
        allowed_emails=allowed_emails,
        noreply_index=noreply_index,
    )
    filtered_commits = _filter_and_remap_emails(
        commits,
        email_getter=lambda c: c.author_email,
        replacer=lambda c, email: replace(c, author_email=email),
        allowed_emails=allowed_emails,
        noreply_index=noreply_index,
    )
    filtered_jira_issues = _filter_and_remap_emails(
        jira_issues,
        email_getter=lambda i: i.assignee_email,
        replacer=lambda i, email: replace(i, assignee_email=email),
        allowed_emails=allowed_emails,
        noreply_index=noreply_index,
    )

    return (
        tuple(filtered_pull_requests),
        tuple(filtered_commits),
        tuple(filtered_jira_issues),
    )


def _filter_and_remap_emails(
    items: Iterable[object],
    *,
    email_getter: Callable[[object], str],
    replacer: Callable[[object, str], object],
    allowed_emails: set[str],
    noreply_index: dict[str, list[str]],
) -> list[object]:
    result: list[object] = []
    for item in items:
        original_email = email_getter(item)
        canonical = _canonicalize_team_member_email(
            original_email,
            allowed_emails=allowed_emails,
            noreply_index=noreply_index,
        )
        if canonical is None:
            continue
        result.append(
            item if canonical == original_email else replacer(item, canonical)
        )
    return result


def _build_noreply_local_part_index(
    allowed_emails: set[str],
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for email in allowed_emails:
        local_part, _, _ = email.partition("@")
        index.setdefault(local_part, []).append(email)
    return index


def _canonicalize_team_member_email(
    email: str,
    *,
    allowed_emails: set[str],
    noreply_index: dict[str, list[str]],
) -> str | None:
    normalized_email = email.strip().lower()
    if normalized_email in allowed_emails:
        return normalized_email

    local_part, separator, domain = normalized_email.partition("@")
    if separator != "@":
        return None

    base_local_part = local_part.split("+", 1)[0]
    if not base_local_part or base_local_part == local_part:
        if domain == "users.noreply.github.com":
            return _match_team_member_from_github_noreply_login(
                local_part,
                noreply_index=noreply_index,
            )
        return None

    canonical_email = f"{base_local_part}@{domain}"
    if canonical_email in allowed_emails:
        return canonical_email
    if domain == "users.noreply.github.com":
        return _match_team_member_from_github_noreply_login(
            local_part,
            noreply_index=noreply_index,
        )
    return None


def _match_team_member_from_github_noreply_login(
    local_part: str,
    *,
    noreply_index: dict[str, list[str]],
) -> str | None:
    _, _, login = local_part.partition("+")
    normalized_login = (login or local_part).strip()
    if not normalized_login:
        return None

    for candidate in _candidate_team_member_local_parts(normalized_login):
        matching_emails = noreply_index.get(candidate, ())
        if len(matching_emails) == 1:
            return matching_emails[0]
    return None


def _candidate_team_member_local_parts(login: str) -> tuple[str, ...]:
    candidates: list[str] = []
    for candidate in (
        login,
        login.split("_", 1)[0],
        login.split("-", 1)[0],
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return tuple(candidates)
