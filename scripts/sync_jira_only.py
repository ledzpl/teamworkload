"""Jira-only sync: fetch Jira issues and merge into existing DB without touching GitHub data.

Usage:
    source .env && PYTHONPATH=src python3 scripts/sync_jira_only.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from workload_analytics.clients import JiraClient
from workload_analytics.config import Granularity, load_settings
from workload_analytics.models import (
    DeveloperPeriodMetrics,
    GithubCommitEvent,
    GithubDeploymentEvent,
    GithubPullRequestEvent,
    JiraAssignedIssueEvent,
)
from workload_analytics.pipelines.jira_normalize import normalize_assigned_issues
from workload_analytics.pipelines.periods import utc_day_bounds
from workload_analytics.pipelines.sync_pipeline import (
    aggregate_developer_period_metrics,
    aggregate_team_period_delivery_metrics,
    filter_normalized_activity_to_team_members,
)
from workload_analytics.storage import SQLiteStore
from workload_analytics.storage.sqlite_helpers import connect_sqlite


_VERIFY_TABLES = (
    "raw_jira_assigned_issues",
    "normalized_jira_assigned_issues",
    "developer_period_metrics",
)


@dataclass(frozen=True, slots=True)
class SyncContext:
    start_date: date
    end_date: date
    granularity: Granularity


def _load_normalized_prs(conn: sqlite3.Connection) -> tuple[GithubPullRequestEvent, ...]:
    rows = conn.execute(
        "SELECT * FROM normalized_github_pull_requests ORDER BY merged_at"
    ).fetchall()
    return tuple(
        GithubPullRequestEvent(
            repository=row["repository"],
            pull_request_number=row["pull_request_number"],
            author_email=row["author_email"],
            merged_at=datetime.fromisoformat(row["merged_at"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            first_reviewed_at=datetime.fromisoformat(row["first_reviewed_at"]) if row["first_reviewed_at"] else None,
            lines_added=row["lines_added"],
            lines_deleted=row["lines_deleted"],
            changed_line_count=row["changed_line_count"],
            cycle_time_hours=row["cycle_time_hours"],
            time_to_first_review_hours=row["time_to_first_review_hours"],
        )
        for row in rows
    )


def _load_normalized_commits(conn: sqlite3.Connection) -> tuple[GithubCommitEvent, ...]:
    rows = conn.execute(
        "SELECT * FROM normalized_github_commits ORDER BY committed_at"
    ).fetchall()
    return tuple(
        GithubCommitEvent(
            repository=row["repository"],
            commit_sha=row["commit_sha"],
            author_email=row["author_email"],
            committed_at=datetime.fromisoformat(row["committed_at"]),
            lines_added=row["lines_added"],
            lines_deleted=row["lines_deleted"],
        )
        for row in rows
    )


def _load_normalized_deployments(conn: sqlite3.Connection) -> tuple[GithubDeploymentEvent, ...]:
    rows = conn.execute(
        "SELECT * FROM normalized_github_deployments ORDER BY deployed_at"
    ).fetchall()
    return tuple(
        GithubDeploymentEvent(
            repository=row["repository"],
            deployment_id=row["deployment_id"],
            environment=row["environment"],
            deployed_at=datetime.fromisoformat(row["deployed_at"]),
            status=row["status"],
            lead_time_hours=row["lead_time_hours"],
        )
        for row in rows
    )


def _load_sync_context(conn: sqlite3.Connection) -> SyncContext | None:
    latest_run = conn.execute(
        """
        SELECT granularity
        FROM sync_runs
        ORDER BY completed_at DESC
        LIMIT 1
        """
    ).fetchone()
    if latest_run is None:
        return None

    granularity = Granularity(latest_run["granularity"])
    range_row = conn.execute(
        """
        SELECT MIN(start_date) AS min_d, MAX(end_date) AS max_d
        FROM sync_runs
        WHERE granularity = ?
        """,
        (granularity.value,),
    ).fetchone()
    if not range_row or not range_row["min_d"]:
        return None

    return SyncContext(
        start_date=date.fromisoformat(range_row["min_d"]),
        end_date=date.fromisoformat(range_row["max_d"]),
        granularity=granularity,
    )


def main() -> int:
    settings = load_settings()
    jira_client = JiraClient(
        base_url=settings.jira.base_url,
        user_email=settings.jira.user_email,
        api_token=settings.jira.api_token,
    )
    store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
    sqlite_path = str(settings.storage.sqlite_path)

    # Use a single connection for all read operations
    with closing(connect_sqlite(sqlite_path=sqlite_path, initialize_schema=True, create_parent=False)) as conn:
        # Rebuild the latest dashboard granularity across its full synced range.
        sync_context = _load_sync_context(conn)
        if sync_context is None:
            print("No existing sync runs found in DB.", file=sys.stderr)
            return 1
        start_date = sync_context.start_date
        end_date = sync_context.end_date
        granularity = sync_context.granularity

        print(
            f"[jira-sync] Date range: {start_date} ~ {end_date} "
            f"({granularity.value})"
        )
        sync_start, sync_end = utc_day_bounds(start_date, end_date)

        # Load existing GitHub normalized data from DB
        print("[jira-sync] Loading existing GitHub data from DB...")
        existing_prs = _load_normalized_prs(conn)
        existing_commits = _load_normalized_commits(conn)
        existing_deployments = _load_normalized_deployments(conn)
        print(
            f"[jira-sync] Loaded {len(existing_prs)} PRs, "
            f"{len(existing_commits)} commits, "
            f"{len(existing_deployments)} deployments"
        )

    # 1. Fetch and normalize Jira issues
    print("[jira-sync] Fetching Jira issues...")
    raw_jira_issues = jira_client.fetch_assigned_issues(
        projects=settings.team_scope.jira_projects,
        updated_from=sync_start,
        updated_to=sync_end,
    )
    print(f"[jira-sync] Fetched {len(raw_jira_issues)} raw Jira issues")

    normalized_jira = normalize_assigned_issues(raw_jira_issues)
    normalized_jira_issues = normalized_jira.issues
    print(
        f"[jira-sync] Normalized {len(normalized_jira_issues)} issues, "
        f"skipped {len(normalized_jira.skipped_issues)}"
    )

    # Filter to team members
    if settings.team_scope.team_members:
        existing_prs, existing_commits, normalized_jira_issues = (
            filter_normalized_activity_to_team_members(
                team_members=settings.team_scope.team_members,
                pull_requests=existing_prs,
                commits=existing_commits,
                jira_issues=normalized_jira_issues,
            )
        )
        print(
            f"[jira-sync] After team filter: {len(existing_prs)} PRs, "
            f"{len(existing_commits)} commits, {len(normalized_jira_issues)} issues"
        )

    # 2. Re-aggregate with Jira data included
    print("[jira-sync] Aggregating metrics...")
    aggregates = aggregate_developer_period_metrics(
        granularity=granularity,
        pull_requests=existing_prs,
        commits=existing_commits,
        jira_issues=normalized_jira_issues,
    )
    delivery_metrics = aggregate_team_period_delivery_metrics(
        granularity=granularity,
        deployments=existing_deployments,
    )
    print(f"[jira-sync] Aggregated {len(aggregates)} developer-period rows")

    # 3. Persist using public API
    print("[jira-sync] Persisting to SQLite...")
    run_id = str(uuid4())
    store.insert_jira_sync_data(
        run_id=run_id,
        granularity=granularity,
        raw_jira_issues=raw_jira_issues,
        normalized_jira_issues=normalized_jira_issues,
        aggregates=aggregates,
        delivery_metrics=delivery_metrics,
    )

    # 4. Verify
    with closing(connect_sqlite(sqlite_path=sqlite_path, initialize_schema=False, create_parent=False)) as conn:
        for table in _VERIFY_TABLES:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            print(f"[jira-sync] {table}: {count} rows")

        jira_total = conn.execute(
            "SELECT SUM(jira_issues_assigned) FROM developer_period_metrics"
        ).fetchone()[0]
        print(f"[jira-sync] Total jira_issues_assigned in aggregates: {jira_total or 0}")

    print("[jira-sync] Done!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
