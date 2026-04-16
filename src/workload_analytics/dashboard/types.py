from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from workload_analytics.config import Granularity
from workload_analytics.dashboard.filters import DashboardFilterState
from workload_analytics.models import DeveloperPeriodMetrics


@dataclass(frozen=True, slots=True)
class SyncStatus:
    run_id: str
    completed_at: datetime
    start_date: date
    end_date: date
    granularity: Granularity
    github_repository_count: int
    discovered_repository_count: int
    excluded_repository_count: int
    jira_project_count: int
    matched_developer_count: int
    unmatched_record_count: int
    persisted_row_count: int


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    active_developers: int
    period_count: int
    github_prs_merged: int
    github_commits_landed: int
    github_lines_added: int
    github_lines_deleted: int
    jira_issues_assigned: int
    github_pr_cycle_time_hours: float = 0.0
    github_prs_with_cycle_time: int = 0
    github_pr_review_wait_hours: float = 0.0
    github_prs_with_review_wait: int = 0
    github_prs_stale: int = 0
    github_prs_small: int = 0
    github_prs_medium: int = 0
    github_prs_large: int = 0
    jira_todo_issues: int = 0
    jira_in_progress_issues: int = 0
    jira_review_issues: int = 0
    jira_done_issues: int = 0
    jira_other_issues: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    deployment_lead_time_hours: float = 0.0
    deployments_with_lead_time: int = 0


@dataclass(frozen=True, slots=True)
class TrendPoint:
    period_start: date
    period_end: date
    github_prs_merged: int
    github_commits_landed: int
    github_lines_added: int
    github_lines_deleted: int
    jira_issues_assigned: int
    github_pr_cycle_time_hours: float = 0.0
    github_prs_with_cycle_time: int = 0
    github_pr_review_wait_hours: float = 0.0
    github_prs_with_review_wait: int = 0
    github_prs_stale: int = 0
    jira_todo_issues: int = 0
    jira_in_progress_issues: int = 0
    jira_review_issues: int = 0
    jira_done_issues: int = 0
    jira_other_issues: int = 0


@dataclass(frozen=True, slots=True)
class DeveloperComparisonRow:
    developer_email: str
    github_prs_merged: int
    github_commits_landed: int
    github_lines_added: int
    github_lines_deleted: int
    jira_issues_assigned: int
    github_pr_cycle_time_hours: float = 0.0
    github_prs_with_cycle_time: int = 0
    github_pr_review_wait_hours: float = 0.0
    github_prs_with_review_wait: int = 0
    github_prs_stale: int = 0
    jira_todo_issues: int = 0
    jira_in_progress_issues: int = 0
    jira_review_issues: int = 0
    jira_done_issues: int = 0
    jira_other_issues: int = 0


@dataclass(frozen=True, slots=True)
class ProviderSplit:
    scope_label: str
    github_prs_merged: int
    github_commits_landed: int
    github_lines_added: int
    github_lines_deleted: int
    jira_issues_assigned: int


@dataclass(frozen=True, slots=True)
class DeliveryTrendPoint:
    period_start: date
    period_end: date
    successful_deployments: int
    failed_deployments: int
    deployment_lead_time_hours: float = 0.0
    deployments_with_lead_time: int = 0


@dataclass(frozen=True, slots=True)
class CommitHeatmapCell:
    day_of_week: int  # 0=Sun through 6=Sat, matching strftime %w
    hour: int
    commit_count: int
    day_total: int = 0


@dataclass(frozen=True, slots=True)
class DeveloperFocusRow:
    developer_email: str
    period_start: date
    period_end: date
    active_repo_count: int
    repo_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DashboardData:
    filters: DashboardFilterState
    developer_options: tuple[str, ...]
    filtered_metrics: tuple[DeveloperPeriodMetrics, ...]
    summary: DashboardSummary
    trend_points: tuple[TrendPoint, ...]
    delivery_trend_points: tuple[DeliveryTrendPoint, ...]
    comparison_rows: tuple[DeveloperComparisonRow, ...]
    provider_split: ProviderSplit
    latest_sync_status: SyncStatus | None


@dataclass(frozen=True, slots=True)
class PreviousPeriodResult:
    summary: DashboardSummary
    start_date: date
    end_date: date
