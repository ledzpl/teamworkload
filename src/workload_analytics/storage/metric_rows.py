from __future__ import annotations

from datetime import date

from workload_analytics.config import Granularity
from workload_analytics.models import DeveloperPeriodMetrics, TeamPeriodDeliveryMetrics


_DEVELOPER_PERIOD_METRIC_COLUMNS = (
    "granularity",
    "developer_email",
    "period_start",
    "period_end",
    "github_prs_merged",
    "github_commits_landed",
    "github_lines_added",
    "github_lines_deleted",
    "{jira_metric_column} AS jira_issues_assigned",
    "github_pr_cycle_time_hours",
    "github_prs_with_cycle_time",
    "github_pr_review_wait_hours",
    "github_prs_with_review_wait",
    "github_prs_stale",
    "github_prs_small",
    "github_prs_medium",
    "github_prs_large",
    "jira_todo_issues",
    "jira_in_progress_issues",
    "jira_review_issues",
    "jira_done_issues",
    "jira_other_issues",
)

_TEAM_PERIOD_DELIVERY_METRIC_COLUMNS = (
    "granularity",
    "period_start",
    "period_end",
    "successful_deployments",
    "failed_deployments",
    "deployment_lead_time_hours",
    "deployments_with_lead_time",
)


def developer_period_metric_select_columns(
    *,
    jira_metric_column: str,
    indent: str,
) -> str:
    return ",\n".join(
        f"{indent}{column.format(jira_metric_column=jira_metric_column)}"
        for column in _DEVELOPER_PERIOD_METRIC_COLUMNS
    )


def team_period_delivery_metric_select_columns(*, indent: str) -> str:
    return ",\n".join(
        f"{indent}{column}" for column in _TEAM_PERIOD_DELIVERY_METRIC_COLUMNS
    )


def developer_period_metric_from_row(row) -> DeveloperPeriodMetrics:
    return DeveloperPeriodMetrics(
        granularity=Granularity(row["granularity"]),
        developer_email=row["developer_email"],
        period_start=date.fromisoformat(row["period_start"]),
        period_end=date.fromisoformat(row["period_end"]),
        github_prs_merged=row["github_prs_merged"],
        github_commits_landed=row["github_commits_landed"],
        github_lines_added=row["github_lines_added"],
        github_lines_deleted=row["github_lines_deleted"],
        jira_issues_assigned=row["jira_issues_assigned"],
        github_pr_cycle_time_hours=row["github_pr_cycle_time_hours"],
        github_prs_with_cycle_time=row["github_prs_with_cycle_time"],
        github_pr_review_wait_hours=row["github_pr_review_wait_hours"],
        github_prs_with_review_wait=row["github_prs_with_review_wait"],
        github_prs_stale=row["github_prs_stale"],
        github_prs_small=row["github_prs_small"],
        github_prs_medium=row["github_prs_medium"],
        github_prs_large=row["github_prs_large"],
        jira_todo_issues=row["jira_todo_issues"],
        jira_in_progress_issues=row["jira_in_progress_issues"],
        jira_review_issues=row["jira_review_issues"],
        jira_done_issues=row["jira_done_issues"],
        jira_other_issues=row["jira_other_issues"],
    )


def team_period_delivery_metric_from_row(row) -> TeamPeriodDeliveryMetrics:
    return TeamPeriodDeliveryMetrics(
        granularity=Granularity(row["granularity"]),
        period_start=date.fromisoformat(row["period_start"]),
        period_end=date.fromisoformat(row["period_end"]),
        successful_deployments=row["successful_deployments"],
        failed_deployments=row["failed_deployments"],
        deployment_lead_time_hours=row["deployment_lead_time_hours"],
        deployments_with_lead_time=row["deployments_with_lead_time"],
    )
