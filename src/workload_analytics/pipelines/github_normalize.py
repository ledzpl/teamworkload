from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from workload_analytics.clients.github_client import (
    GithubCommitPayload,
    GithubDeploymentPayload,
    GithubPullRequestPayload,
)
from workload_analytics.models import (
    GithubCommitEvent,
    GithubDeploymentEvent,
    GithubPullRequestEvent,
)
from workload_analytics.pipelines.metric_rules import (
    FileChange,
    should_exclude_commit,
    summarize_github_changes,
)


@dataclass(frozen=True, slots=True)
class GithubSkippedRecord:
    record_type: str
    repository: str
    record_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class GithubNormalizationResult:
    pull_requests: tuple[GithubPullRequestEvent, ...]
    commits: tuple[GithubCommitEvent, ...]
    skipped_records: tuple[GithubSkippedRecord, ...]


SUCCESSFUL_DEPLOYMENT_STATES = frozenset({"success"})
FAILED_DEPLOYMENT_STATES = frozenset({"failure", "error"})
_KNOWN_DEPLOYMENT_STATES = SUCCESSFUL_DEPLOYMENT_STATES | FAILED_DEPLOYMENT_STATES


def normalize_github_activity(
    *,
    pull_requests: Iterable[GithubPullRequestPayload],
    commits: Iterable[GithubCommitPayload],
) -> GithubNormalizationResult:
    normalized_pull_requests: list[GithubPullRequestEvent] = []
    normalized_commits: list[GithubCommitEvent] = []
    skipped_records: list[GithubSkippedRecord] = []

    for pull_request in pull_requests:
        normalized = _normalize_pull_request(pull_request)
        if isinstance(normalized, GithubSkippedRecord):
            skipped_records.append(normalized)
            continue
        normalized_pull_requests.append(normalized)

    for commit in commits:
        normalized = _normalize_commit(commit)
        if isinstance(normalized, GithubSkippedRecord):
            skipped_records.append(normalized)
            continue
        normalized_commits.append(normalized)

    return GithubNormalizationResult(
        pull_requests=tuple(normalized_pull_requests),
        commits=tuple(normalized_commits),
        skipped_records=tuple(skipped_records),
    )


def normalize_github_deployments(
    deployments: Iterable[GithubDeploymentPayload],
) -> tuple[GithubDeploymentEvent, ...]:
    normalized_deployments: list[GithubDeploymentEvent] = []

    for deployment in deployments:
        state = (deployment.latest_status_state or "").strip().lower()
        if state not in _KNOWN_DEPLOYMENT_STATES:
            continue

        deployed_at = deployment.latest_status_at or deployment.created_at
        lead_time_hours = (
            _hours_between(deployment.commit_committed_at, deployed_at)
            if state in SUCCESSFUL_DEPLOYMENT_STATES
            else None
        )
        normalized_deployments.append(
            GithubDeploymentEvent(
                repository=deployment.repository,
                deployment_id=deployment.deployment_id,
                environment=deployment.environment,
                deployed_at=deployed_at,
                status=state,
                lead_time_hours=lead_time_hours,
            )
        )

    return tuple(normalized_deployments)


def _normalize_pull_request(
    pull_request: GithubPullRequestPayload,
) -> GithubPullRequestEvent | GithubSkippedRecord:
    author_email = _select_pull_request_author_email(pull_request.commit_author_emails)
    if author_email is None:
        return GithubSkippedRecord(
            record_type="pull_request",
            repository=pull_request.repository,
            record_id=str(pull_request.pull_request_number),
            reason="missing_author_email",
        )

    summary = summarize_github_changes(
        _to_file_changes(pull_request.files),
        is_merge_commit=False,
    )
    if not summary.included_paths:
        return GithubSkippedRecord(
            record_type="pull_request",
            repository=pull_request.repository,
            record_id=str(pull_request.pull_request_number),
            reason="no_included_file_changes",
        )

    return GithubPullRequestEvent(
        repository=pull_request.repository,
        pull_request_number=pull_request.pull_request_number,
        author_email=author_email,
        merged_at=pull_request.merged_at,
        lines_added=summary.lines_added,
        lines_deleted=summary.lines_deleted,
        created_at=pull_request.created_at,
        first_reviewed_at=pull_request.first_reviewed_at,
        cycle_time_hours=_hours_between(pull_request.created_at, pull_request.merged_at),
        time_to_first_review_hours=_hours_between(
            pull_request.created_at,
            pull_request.first_reviewed_at,
        ),
        changed_line_count=summary.lines_added + summary.lines_deleted,
    )


def _normalize_commit(
    commit: GithubCommitPayload,
) -> GithubCommitEvent | GithubSkippedRecord:
    if commit.author_email is None:
        return GithubSkippedRecord(
            record_type="commit",
            repository=commit.repository,
            record_id=commit.commit_sha,
            reason="missing_author_email",
        )

    summary = summarize_github_changes(
        _to_file_changes(commit.files),
        is_merge_commit=should_exclude_commit(parent_count=commit.parent_count),
    )
    if not summary.included_paths:
        return GithubSkippedRecord(
            record_type="commit",
            repository=commit.repository,
            record_id=commit.commit_sha,
            reason="no_included_file_changes",
        )

    return GithubCommitEvent(
        repository=commit.repository,
        commit_sha=commit.commit_sha,
        author_email=commit.author_email.strip().lower(),
        committed_at=commit.committed_at,
        lines_added=summary.lines_added,
        lines_deleted=summary.lines_deleted,
    )


def _select_pull_request_author_email(commit_author_emails: Iterable[str]) -> str | None:
    normalized_emails = [
        email.strip().lower() for email in commit_author_emails if email.strip()
    ]
    if not normalized_emails:
        return None

    counts = Counter(normalized_emails)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0]


def _to_file_changes(files: Iterable[object]) -> tuple[FileChange, ...]:
    return tuple(
        FileChange(
            path=file_change.path,
            lines_added=file_change.additions,
            lines_deleted=file_change.deletions,
        )
        for file_change in files
    )


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / 3600, 2)
