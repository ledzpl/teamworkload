from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GithubPullRequestEvent:
    repository: str
    pull_request_number: int
    author_email: str
    merged_at: datetime
    lines_added: int
    lines_deleted: int
    created_at: datetime | None = None
    first_reviewed_at: datetime | None = None
    cycle_time_hours: float | None = None
    time_to_first_review_hours: float | None = None
    changed_line_count: int = 0


@dataclass(frozen=True, slots=True)
class GithubCommitEvent:
    repository: str
    commit_sha: str
    author_email: str
    committed_at: datetime
    lines_added: int
    lines_deleted: int


@dataclass(frozen=True, slots=True)
class GithubDeploymentEvent:
    repository: str
    deployment_id: int
    environment: str
    deployed_at: datetime
    status: str
    lead_time_hours: float | None = None


@dataclass(frozen=True, slots=True)
class JiraAssignedIssueEvent:
    project_key: str
    issue_key: str
    assignee_email: str
    updated_at: datetime
    status_name: str = ""
    status_bucket: str = "other"
