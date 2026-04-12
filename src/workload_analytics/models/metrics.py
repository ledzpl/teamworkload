from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from workload_analytics.config import Granularity


@dataclass(frozen=True, slots=True)
class DeveloperIdentity:
    primary_email: str
    display_name: str
    github_logins: tuple[str, ...] = ()
    jira_account_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeveloperPeriodMetrics:
    granularity: Granularity
    developer_email: str
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
    github_prs_small: int = 0
    github_prs_medium: int = 0
    github_prs_large: int = 0
    jira_todo_issues: int = 0
    jira_in_progress_issues: int = 0
    jira_review_issues: int = 0
    jira_done_issues: int = 0
    jira_other_issues: int = 0


@dataclass(frozen=True, slots=True)
class TeamPeriodDeliveryMetrics:
    granularity: Granularity
    period_start: date
    period_end: date
    successful_deployments: int = 0
    failed_deployments: int = 0
    deployment_lead_time_hours: float = 0.0
    deployments_with_lead_time: int = 0
