from __future__ import annotations

from pathlib import Path
import sqlite3

from .schema import initialize_sqlite_schema


def connect_sqlite(
    *,
    sqlite_path: str,
    initialize_schema: bool,
    create_parent: bool,
) -> sqlite3.Connection:
    path = Path(sqlite_path)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    if initialize_schema:
        initialize_sqlite_schema(connection)
        connection.commit()

    return connection


def resolve_jira_metric_column(connection: sqlite3.Connection) -> str:
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(developer_period_metrics)"
        ).fetchall()
    }
    if "jira_issues_assigned" in columns:
        return "jira_issues_assigned"
    return "jira_issues_done"
