from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from workload_analytics.config import Granularity
from workload_analytics.models import (
    DeveloperPeriodMetrics,
    GithubCommitEvent,
    GithubDeploymentEvent,
    GithubPullRequestEvent,
    JiraAssignedIssueEvent,
    TeamPeriodDeliveryMetrics,
)
from workload_analytics.pipelines.periods import bucket_period, utc_day_bounds
from workload_analytics.storage.metric_rows import (
    developer_period_metric_from_row,
    developer_period_metric_select_columns,
    team_period_delivery_metric_from_row,
    team_period_delivery_metric_select_columns,
)
from workload_analytics.storage.sqlite_helpers import (
    connect_sqlite,
    resolve_jira_metric_column,
)


class SQLiteStore:
    def __init__(self, *, sqlite_path: str) -> None:
        self._sqlite_path = Path(sqlite_path)

    def initialize(self) -> None:
        with closing(self._connect()):
            pass

    def replace_sync_snapshot(
        self,
        *,
        run_id: str,
        started_at: datetime,
        completed_at: datetime,
        start_date: date,
        end_date: date,
        granularity: Granularity,
        raw_pull_requests: tuple[object, ...],
        raw_commits: tuple[object, ...],
        raw_jira_issues: tuple[object, ...],
        raw_deployments: tuple[object, ...] = (),
        normalized_pull_requests: tuple[GithubPullRequestEvent, ...],
        normalized_commits: tuple[GithubCommitEvent, ...],
        normalized_deployments: tuple[GithubDeploymentEvent, ...] = (),
        normalized_jira_issues: tuple[JiraAssignedIssueEvent, ...],
        aggregates: tuple[DeveloperPeriodMetrics, ...],
        delivery_metrics: tuple[TeamPeriodDeliveryMetrics, ...] = (),
        github_repository_count: int,
        discovered_repository_count: int,
        excluded_repository_count: int,
        jira_project_count: int,
        matched_developer_count: int,
        unmatched_record_count: int,
        persisted_row_count: int,
    ) -> None:
        with closing(self._connect()) as connection:
            self._delete_overlapping_rows(
                connection=connection,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
            )
            self._insert_raw_pull_requests(connection, run_id, raw_pull_requests)
            self._insert_raw_commits(connection, run_id, raw_commits)
            self._insert_raw_deployments(connection, run_id, raw_deployments)
            self._insert_raw_jira_issues(connection, run_id, raw_jira_issues)
            self._insert_normalized_pull_requests(
                connection,
                run_id,
                normalized_pull_requests,
            )
            self._insert_normalized_commits(connection, run_id, normalized_commits)
            self._insert_normalized_deployments(
                connection,
                run_id,
                normalized_deployments,
            )
            self._insert_normalized_jira_issues(
                connection,
                run_id,
                normalized_jira_issues,
            )
            self._insert_aggregates(connection, run_id, aggregates)
            self._insert_delivery_metrics(connection, run_id, delivery_metrics)
            connection.execute(
                """
                INSERT INTO sync_runs (
                    run_id,
                    started_at,
                    completed_at,
                    start_date,
                    end_date,
                    granularity,
                    github_repository_count,
                    discovered_repository_count,
                    excluded_repository_count,
                    jira_project_count,
                    matched_developer_count,
                    unmatched_record_count,
                    persisted_row_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    start_date.isoformat(),
                    end_date.isoformat(),
                    granularity.value,
                    github_repository_count,
                    discovered_repository_count,
                    excluded_repository_count,
                    jira_project_count,
                    matched_developer_count,
                    unmatched_record_count,
                    persisted_row_count,
                ),
            )
            connection.commit()

    def list_tables(self) -> tuple[str, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return tuple(row["name"] for row in rows)

    def table_row_count(self, table_name: str) -> int:
        with closing(self._connect()) as connection:
            table_row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = ? AND name NOT LIKE 'sqlite_%'
                """,
                (table_name,),
            ).fetchone()
            if table_row is None:
                raise ValueError(f"Unknown SQLite table {table_name!r}.")

            row = connection.execute(
                f'SELECT COUNT(*) AS row_count FROM "{table_name}"'
            ).fetchone()
        return int(row["row_count"])

    def fetch_developer_period_metrics(
        self,
        *,
        granularity: Granularity,
    ) -> tuple[DeveloperPeriodMetrics, ...]:
        with closing(self._connect()) as connection:
            jira_metric_column = resolve_jira_metric_column(connection)
            select_columns = developer_period_metric_select_columns(
                jira_metric_column=jira_metric_column,
                indent="                    ",
            )
            rows = connection.execute(
                f"""
                SELECT
{select_columns}
                FROM developer_period_metrics
                WHERE granularity = ?
                ORDER BY period_start, developer_email
                """,
                (granularity.value,),
            ).fetchall()

        return tuple(developer_period_metric_from_row(row) for row in rows)

    def fetch_team_period_delivery_metrics(
        self,
        *,
        granularity: Granularity,
    ) -> tuple[TeamPeriodDeliveryMetrics, ...]:
        with closing(self._connect()) as connection:
            select_columns = team_period_delivery_metric_select_columns(
                indent="                    ",
            )
            rows = connection.execute(
                f"""
                SELECT
{select_columns}
                FROM team_period_delivery_metrics
                WHERE granularity = ?
                ORDER BY period_start
                """,
                (granularity.value,),
            ).fetchall()

        return tuple(team_period_delivery_metric_from_row(row) for row in rows)

    def insert_jira_sync_data(
        self,
        *,
        run_id: str,
        granularity: Granularity,
        raw_jira_issues: tuple[object, ...],
        normalized_jira_issues: tuple[JiraAssignedIssueEvent, ...],
        aggregates: tuple[DeveloperPeriodMetrics, ...],
        delivery_metrics: tuple[TeamPeriodDeliveryMetrics, ...],
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM raw_jira_assigned_issues")
            connection.execute("DELETE FROM normalized_jira_assigned_issues")
            connection.execute(
                "DELETE FROM developer_period_metrics WHERE granularity = ?",
                (granularity.value,),
            )
            connection.execute(
                "DELETE FROM team_period_delivery_metrics WHERE granularity = ?",
                (granularity.value,),
            )
            self._insert_raw_jira_issues(connection, run_id, raw_jira_issues)
            self._insert_normalized_jira_issues(connection, run_id, normalized_jira_issues)
            self._insert_aggregates(connection, run_id, aggregates)
            self._insert_delivery_metrics(connection, run_id, delivery_metrics)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(
            sqlite_path=str(self._sqlite_path),
            initialize_schema=True,
            create_parent=True,
        )

    def _delete_overlapping_rows(
        self,
        *,
        connection: sqlite3.Connection,
        start_date: date,
        end_date: date,
        granularity: Granularity,
    ) -> None:
        sync_start, sync_end = utc_day_bounds(start_date, end_date)
        start_datetime = sync_start.isoformat()
        end_datetime = sync_end.isoformat()
        first_period_start = bucket_period(start_date, granularity).start.isoformat()
        last_period_start = bucket_period(end_date, granularity).start.isoformat()

        for table_name, column_name in (
            ("raw_github_pull_requests", "merged_at"),
            ("raw_github_commits", "committed_at"),
            ("raw_github_deployments", "created_at"),
            ("raw_jira_assigned_issues", "updated_at"),
            ("normalized_github_pull_requests", "merged_at"),
            ("normalized_github_commits", "committed_at"),
            ("normalized_github_deployments", "deployed_at"),
            ("normalized_jira_assigned_issues", "updated_at"),
        ):
            connection.execute(
                f'DELETE FROM "{table_name}" WHERE "{column_name}" BETWEEN ? AND ?',
                (start_datetime, end_datetime),
            )

        connection.execute(
            """
            DELETE FROM developer_period_metrics
            WHERE granularity = ?
              AND period_start BETWEEN ? AND ?
            """,
            (granularity.value, first_period_start, last_period_start),
        )
        connection.execute(
            """
            DELETE FROM team_period_delivery_metrics
            WHERE granularity = ?
              AND period_start BETWEEN ? AND ?
            """,
            (granularity.value, first_period_start, last_period_start),
        )

    def _insert_raw_pull_requests(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        pull_requests: tuple[object, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO raw_github_pull_requests (
                repository,
                pull_request_number,
                merged_at,
                payload_json,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.repository,
                    payload.pull_request_number,
                    payload.merged_at.isoformat(),
                    _to_json(payload),
                    run_id,
                )
                for payload in pull_requests
            ],
        )

    def _insert_raw_commits(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        commits: tuple[object, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO raw_github_commits (
                repository,
                commit_sha,
                committed_at,
                payload_json,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.repository,
                    payload.commit_sha,
                    payload.committed_at.isoformat(),
                    _to_json(payload),
                    run_id,
                )
                for payload in commits
            ],
        )

    def _insert_raw_deployments(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        deployments: tuple[object, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO raw_github_deployments (
                repository,
                deployment_id,
                created_at,
                payload_json,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.repository,
                    payload.deployment_id,
                    payload.created_at.isoformat(),
                    _to_json(payload),
                    run_id,
                )
                for payload in deployments
            ],
        )

    def _insert_raw_jira_issues(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        issues: tuple[object, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO raw_jira_assigned_issues (
                project_key,
                issue_key,
                updated_at,
                payload_json,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.project_key,
                    payload.issue_key,
                    payload.updated_at.isoformat(),
                    _to_json(payload),
                    run_id,
                )
                for payload in issues
            ],
        )

    def _insert_normalized_pull_requests(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        pull_requests: tuple[GithubPullRequestEvent, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO normalized_github_pull_requests (
                repository,
                pull_request_number,
                author_email,
                merged_at,
                lines_added,
                lines_deleted,
                created_at,
                first_reviewed_at,
                cycle_time_hours,
                time_to_first_review_hours,
                changed_line_count,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.repository,
                    payload.pull_request_number,
                    payload.author_email,
                    payload.merged_at.isoformat(),
                    payload.lines_added,
                    payload.lines_deleted,
                    _optional_datetime_isoformat(payload.created_at),
                    _optional_datetime_isoformat(payload.first_reviewed_at),
                    payload.cycle_time_hours,
                    payload.time_to_first_review_hours,
                    payload.changed_line_count,
                    run_id,
                )
                for payload in pull_requests
            ],
        )

    def _insert_normalized_commits(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        commits: tuple[GithubCommitEvent, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO normalized_github_commits (
                repository,
                commit_sha,
                author_email,
                committed_at,
                lines_added,
                lines_deleted,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.repository,
                    payload.commit_sha,
                    payload.author_email,
                    payload.committed_at.isoformat(),
                    payload.lines_added,
                    payload.lines_deleted,
                    run_id,
                )
                for payload in commits
            ],
        )

    def _insert_normalized_jira_issues(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        issues: tuple[JiraAssignedIssueEvent, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO normalized_jira_assigned_issues (
                project_key,
                issue_key,
                assignee_email,
                updated_at,
                status_name,
                status_bucket,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.project_key,
                    payload.issue_key,
                    payload.assignee_email,
                    payload.updated_at.isoformat(),
                    payload.status_name,
                    payload.status_bucket,
                    run_id,
                )
                for payload in issues
            ],
        )

    def _insert_normalized_deployments(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        deployments: tuple[GithubDeploymentEvent, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO normalized_github_deployments (
                repository,
                deployment_id,
                environment,
                deployed_at,
                status,
                lead_time_hours,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.repository,
                    payload.deployment_id,
                    payload.environment,
                    payload.deployed_at.isoformat(),
                    payload.status,
                    payload.lead_time_hours,
                    run_id,
                )
                for payload in deployments
            ],
        )

    def _insert_aggregates(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        aggregates: tuple[DeveloperPeriodMetrics, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO developer_period_metrics (
                granularity,
                developer_email,
                period_start,
                period_end,
                github_prs_merged,
                github_commits_landed,
                github_lines_added,
                github_lines_deleted,
                jira_issues_assigned,
                github_pr_cycle_time_hours,
                github_prs_with_cycle_time,
                github_pr_review_wait_hours,
                github_prs_with_review_wait,
                github_prs_stale,
                github_prs_small,
                github_prs_medium,
                github_prs_large,
                jira_todo_issues,
                jira_in_progress_issues,
                jira_review_issues,
                jira_done_issues,
                jira_other_issues,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.granularity.value,
                    payload.developer_email,
                    payload.period_start.isoformat(),
                    payload.period_end.isoformat(),
                    payload.github_prs_merged,
                    payload.github_commits_landed,
                    payload.github_lines_added,
                    payload.github_lines_deleted,
                    payload.jira_issues_assigned,
                    payload.github_pr_cycle_time_hours,
                    payload.github_prs_with_cycle_time,
                    payload.github_pr_review_wait_hours,
                    payload.github_prs_with_review_wait,
                    payload.github_prs_stale,
                    payload.github_prs_small,
                    payload.github_prs_medium,
                    payload.github_prs_large,
                    payload.jira_todo_issues,
                    payload.jira_in_progress_issues,
                    payload.jira_review_issues,
                    payload.jira_done_issues,
                    payload.jira_other_issues,
                    run_id,
                )
                for payload in aggregates
            ],
        )

    def _insert_delivery_metrics(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        delivery_metrics: tuple[TeamPeriodDeliveryMetrics, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO team_period_delivery_metrics (
                granularity,
                period_start,
                period_end,
                successful_deployments,
                failed_deployments,
                deployment_lead_time_hours,
                deployments_with_lead_time,
                synced_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    payload.granularity.value,
                    payload.period_start.isoformat(),
                    payload.period_end.isoformat(),
                    payload.successful_deployments,
                    payload.failed_deployments,
                    payload.deployment_lead_time_hours,
                    payload.deployments_with_lead_time,
                    run_id,
                )
                for payload in delivery_metrics
            ],
        )


def _optional_datetime_isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _to_json(value: object) -> str:
    return json.dumps(_serialize(value), sort_keys=True)


def _serialize(value: object) -> Any:
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value
