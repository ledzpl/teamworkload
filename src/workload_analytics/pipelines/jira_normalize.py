from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from workload_analytics.clients.jira_client import JiraAssignedIssuePayload
from workload_analytics.models import JiraAssignedIssueEvent


@dataclass(frozen=True, slots=True)
class JiraSkippedIssue:
    issue_key: str
    project_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class JiraNormalizationResult:
    issues: tuple[JiraAssignedIssueEvent, ...]
    skipped_issues: tuple[JiraSkippedIssue, ...]


def normalize_assigned_issues(
    issues: Iterable[JiraAssignedIssuePayload],
) -> JiraNormalizationResult:
    normalized_issues: list[JiraAssignedIssueEvent] = []
    skipped_issues: list[JiraSkippedIssue] = []

    for issue in issues:
        if issue.assignee_email is None:
            skipped_issues.append(
                JiraSkippedIssue(
                    issue_key=issue.issue_key,
                    project_key=issue.project_key,
                    reason="missing_assignee_email",
                )
            )
            continue

        assignee_email = issue.assignee_email.strip().lower()
        normalized_issues.append(
            JiraAssignedIssueEvent(
                project_key=issue.project_key,
                issue_key=issue.issue_key,
                assignee_email=assignee_email,
                updated_at=issue.updated_at,
                status_name=issue.status_name.strip(),
                status_bucket=bucket_jira_status(issue.status_name),
            )
        )

    return JiraNormalizationResult(
        issues=tuple(normalized_issues),
        skipped_issues=tuple(skipped_issues),
    )


def bucket_jira_status(status_name: str) -> str:
    normalized_status = " ".join(status_name.strip().lower().replace("_", " ").split())
    if not normalized_status:
        return "other"
    if normalized_status in {
        "to do",
        "todo",
        "backlog",
        "open",
        "new",
        "ready",
        "selected for development",
    }:
        return "todo"
    if normalized_status in {
        "in progress",
        "in development",
        "development",
        "doing",
        "active",
        "implementing",
    }:
        return "in_progress"
    if normalized_status in {
        "review",
        "in review",
        "code review",
        "peer review",
        "qa",
        "testing",
        "ready for review",
    }:
        return "review"
    if normalized_status in {
        "done",
        "closed",
        "resolved",
        "complete",
        "completed",
        "released",
    }:
        return "done"
    return "other"
