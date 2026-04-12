from __future__ import annotations

import sqlite3


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS sync_runs (
        run_id TEXT PRIMARY KEY,
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        granularity TEXT NOT NULL,
        github_repository_count INTEGER NOT NULL,
        discovered_repository_count INTEGER NOT NULL DEFAULT 0,
        excluded_repository_count INTEGER NOT NULL DEFAULT 0,
        jira_project_count INTEGER NOT NULL,
        matched_developer_count INTEGER NOT NULL,
        unmatched_record_count INTEGER NOT NULL,
        persisted_row_count INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_github_pull_requests (
        repository TEXT NOT NULL,
        pull_request_number INTEGER NOT NULL,
        merged_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (repository, pull_request_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_github_commits (
        repository TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (repository, commit_sha)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_github_deployments (
        repository TEXT NOT NULL,
        deployment_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (repository, deployment_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_jira_assigned_issues (
        project_key TEXT NOT NULL,
        issue_key TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (project_key, issue_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS normalized_github_pull_requests (
        repository TEXT NOT NULL,
        pull_request_number INTEGER NOT NULL,
        author_email TEXT NOT NULL,
        merged_at TEXT NOT NULL,
        lines_added INTEGER NOT NULL,
        lines_deleted INTEGER NOT NULL,
        created_at TEXT,
        first_reviewed_at TEXT,
        cycle_time_hours REAL,
        time_to_first_review_hours REAL,
        changed_line_count INTEGER NOT NULL DEFAULT 0,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (repository, pull_request_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS normalized_github_commits (
        repository TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        author_email TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        lines_added INTEGER NOT NULL,
        lines_deleted INTEGER NOT NULL,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (repository, commit_sha)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS normalized_github_deployments (
        repository TEXT NOT NULL,
        deployment_id INTEGER NOT NULL,
        environment TEXT NOT NULL,
        deployed_at TEXT NOT NULL,
        status TEXT NOT NULL,
        lead_time_hours REAL,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (repository, deployment_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS normalized_jira_assigned_issues (
        project_key TEXT NOT NULL,
        issue_key TEXT NOT NULL,
        assignee_email TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        status_name TEXT NOT NULL DEFAULT '',
        status_bucket TEXT NOT NULL DEFAULT 'other',
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (project_key, issue_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS team_period_delivery_metrics (
        granularity TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        successful_deployments INTEGER NOT NULL DEFAULT 0,
        failed_deployments INTEGER NOT NULL DEFAULT 0,
        deployment_lead_time_hours REAL NOT NULL DEFAULT 0,
        deployments_with_lead_time INTEGER NOT NULL DEFAULT 0,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (granularity, period_start)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS developer_period_metrics (
        granularity TEXT NOT NULL,
        developer_email TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        github_prs_merged INTEGER NOT NULL,
        github_commits_landed INTEGER NOT NULL,
        github_lines_added INTEGER NOT NULL,
        github_lines_deleted INTEGER NOT NULL,
        jira_issues_assigned INTEGER NOT NULL DEFAULT 0,
        github_pr_cycle_time_hours REAL NOT NULL DEFAULT 0,
        github_prs_with_cycle_time INTEGER NOT NULL DEFAULT 0,
        github_pr_review_wait_hours REAL NOT NULL DEFAULT 0,
        github_prs_with_review_wait INTEGER NOT NULL DEFAULT 0,
        github_prs_stale INTEGER NOT NULL DEFAULT 0,
        github_prs_small INTEGER NOT NULL DEFAULT 0,
        github_prs_medium INTEGER NOT NULL DEFAULT 0,
        github_prs_large INTEGER NOT NULL DEFAULT 0,
        jira_todo_issues INTEGER NOT NULL DEFAULT 0,
        jira_in_progress_issues INTEGER NOT NULL DEFAULT 0,
        jira_review_issues INTEGER NOT NULL DEFAULT 0,
        jira_done_issues INTEGER NOT NULL DEFAULT 0,
        jira_other_issues INTEGER NOT NULL DEFAULT 0,
        synced_run_id TEXT NOT NULL,
        PRIMARY KEY (granularity, developer_email, period_start)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_github_prs_merged_at
    ON raw_github_pull_requests (merged_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_github_commits_committed_at
    ON raw_github_commits (committed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_github_deployments_created_at
    ON raw_github_deployments (created_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_jira_issues_updated_at
    ON raw_jira_assigned_issues (updated_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_metrics_lookup
    ON developer_period_metrics (granularity, period_start, developer_email)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_delivery_metrics_lookup
    ON team_period_delivery_metrics (granularity, period_start)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_normalized_github_commits_activity
    ON normalized_github_commits (committed_at, author_email)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_normalized_github_prs_activity
    ON normalized_github_pull_requests (merged_at, author_email)
    """,
)


def initialize_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    _ensure_sync_runs_columns(connection)
    _ensure_normalized_pull_request_columns(connection)
    _ensure_normalized_jira_issue_columns(connection)
    _ensure_developer_period_metrics_columns(connection)


def _ensure_sync_runs_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(sync_runs)").fetchall()
    }
    for column_name in (
        "discovered_repository_count",
        "excluded_repository_count",
    ):
        if column_name in columns:
            continue
        connection.execute(
            f"ALTER TABLE sync_runs ADD COLUMN {column_name} INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_developer_period_metrics_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(developer_period_metrics)"
        ).fetchall()
    }
    if not columns:
        return

    if "jira_issues_assigned" not in columns:
        connection.execute(
            """
            ALTER TABLE developer_period_metrics
            ADD COLUMN jira_issues_assigned INTEGER NOT NULL DEFAULT 0
            """
        )
        if "jira_issues_done" in columns:
            connection.execute(
                """
                UPDATE developer_period_metrics
                SET jira_issues_assigned = jira_issues_done
                """
            )

    metric_columns = {
        "github_pr_cycle_time_hours": "REAL NOT NULL DEFAULT 0",
        "github_prs_with_cycle_time": "INTEGER NOT NULL DEFAULT 0",
        "github_pr_review_wait_hours": "REAL NOT NULL DEFAULT 0",
        "github_prs_with_review_wait": "INTEGER NOT NULL DEFAULT 0",
        "github_prs_stale": "INTEGER NOT NULL DEFAULT 0",
        "github_prs_small": "INTEGER NOT NULL DEFAULT 0",
        "github_prs_medium": "INTEGER NOT NULL DEFAULT 0",
        "github_prs_large": "INTEGER NOT NULL DEFAULT 0",
        "jira_todo_issues": "INTEGER NOT NULL DEFAULT 0",
        "jira_in_progress_issues": "INTEGER NOT NULL DEFAULT 0",
        "jira_review_issues": "INTEGER NOT NULL DEFAULT 0",
        "jira_done_issues": "INTEGER NOT NULL DEFAULT 0",
        "jira_other_issues": "INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, column_type in metric_columns.items():
        if column_name in columns:
            continue
        connection.execute(
            f"ALTER TABLE developer_period_metrics ADD COLUMN {column_name} {column_type}"
        )


def _ensure_normalized_pull_request_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(normalized_github_pull_requests)"
        ).fetchall()
    }
    if not columns:
        return

    column_definitions = {
        "created_at": "TEXT",
        "first_reviewed_at": "TEXT",
        "cycle_time_hours": "REAL",
        "time_to_first_review_hours": "REAL",
        "changed_line_count": "INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, column_type in column_definitions.items():
        if column_name in columns:
            continue
        connection.execute(
            f"ALTER TABLE normalized_github_pull_requests ADD COLUMN {column_name} {column_type}"
        )


def _ensure_normalized_jira_issue_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(normalized_jira_assigned_issues)"
        ).fetchall()
    }
    if not columns:
        return

    column_definitions = {
        "status_name": "TEXT NOT NULL DEFAULT ''",
        "status_bucket": "TEXT NOT NULL DEFAULT 'other'",
    }
    for column_name, column_type in column_definitions.items():
        if column_name in columns:
            continue
        connection.execute(
            f"ALTER TABLE normalized_jira_assigned_issues ADD COLUMN {column_name} {column_type}"
        )
