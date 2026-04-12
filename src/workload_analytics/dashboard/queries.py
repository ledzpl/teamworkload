from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import sqlite3

from workload_analytics.config import Granularity
from workload_analytics.dashboard.filters import DashboardFilterState
from workload_analytics.models import DeveloperPeriodMetrics, TeamPeriodDeliveryMetrics
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


_METRIC_FIELDS: tuple[str, ...] = (
    "github_prs_merged",
    "github_commits_landed",
    "github_lines_added",
    "github_lines_deleted",
    "jira_issues_assigned",
    "github_pr_cycle_time_hours",
    "github_prs_with_cycle_time",
    "github_pr_review_wait_hours",
    "github_prs_with_review_wait",
    "github_prs_stale",
    "jira_todo_issues",
    "jira_in_progress_issues",
    "jira_review_issues",
    "jira_done_issues",
    "jira_other_issues",
)

_METRIC_DEFAULTS: dict[str, int | float] = {
    field: 0.0 if "hours" in field else 0
    for field in _METRIC_FIELDS
}


def _new_metric_bucket() -> dict[str, int | float]:
    return dict(_METRIC_DEFAULTS)


def _accumulate_metrics(
    bucket: dict[str, int | float],
    item: DeveloperPeriodMetrics,
) -> None:
    for field in _METRIC_FIELDS:
        bucket[field] += getattr(item, field)


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
    day_of_week: int  # 0=Sun … 6=Sat (strftime %w)
    hour: int         # 0–23
    commit_count: int


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


def load_previous_period_summary(
    *,
    sqlite_path: str,
    filters: DashboardFilterState,
) -> PreviousPeriodResult | None:
    """Load summary for the period immediately before the current filter range."""
    duration = (filters.end_date - filters.start_date).days + 1
    previous_end = filters.start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)

    previous_filters = DashboardFilterState(
        start_date=previous_start,
        end_date=previous_end,
        granularity=filters.granularity,
        developer_email=filters.developer_email,
    )
    metrics = _fetch_filtered_metrics(sqlite_path=sqlite_path, filters=previous_filters)
    if not metrics:
        return None

    delivery_metrics = _fetch_delivery_metrics(sqlite_path=sqlite_path, filters=previous_filters)
    trend_points = build_trend_points(metrics, filters=previous_filters)
    delivery_trend_points = build_delivery_trend_points(
        delivery_metrics, filters=previous_filters,
    )
    return PreviousPeriodResult(
        summary=build_dashboard_summary(
            metrics,
            trend_points=trend_points,
            delivery_trend_points=delivery_trend_points,
        ),
        start_date=previous_start,
        end_date=previous_end,
    )


def apply_dashboard_search(
    data: DashboardData,
    *,
    query: str,
) -> DashboardData:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return data

    filtered_metrics = tuple(
        item
        for item in data.filtered_metrics
        if _matches_search_query(item, normalized_query)
    )
    trend_points = build_trend_points(filtered_metrics, filters=data.filters)

    return DashboardData(
        filters=data.filters,
        developer_options=data.developer_options,
        filtered_metrics=filtered_metrics,
        summary=build_dashboard_summary(
            filtered_metrics,
            trend_points=trend_points,
            delivery_trend_points=data.delivery_trend_points,
        ),
        trend_points=trend_points,
        delivery_trend_points=data.delivery_trend_points,
        comparison_rows=build_comparison_rows(filtered_metrics),
        provider_split=build_provider_split(
            filtered_metrics,
            developer_email=data.filters.developer_email,
        ),
        latest_sync_status=data.latest_sync_status,
    )


def load_dashboard_data(
    *,
    sqlite_path: str,
    filters: DashboardFilterState,
    team_members: tuple[str, ...] = (),
) -> DashboardData:
    with closing(_connect(sqlite_path)) as connection:
        metrics = _fetch_filtered_metrics_with_conn(connection=connection, filters=filters)
        delivery_metrics = _fetch_delivery_metrics_with_conn(connection=connection, filters=filters)
        developer_options = _fetch_developer_options_with_conn(
            connection=connection,
            filters=filters,
            team_members=team_members,
        )
        latest_sync_status = _fetch_latest_sync_status_with_conn(connection=connection)

    trend_points = build_trend_points(metrics, filters=filters)
    delivery_trend_points = build_delivery_trend_points(
        delivery_metrics,
        filters=filters,
    )
    summary = build_dashboard_summary(
        metrics,
        trend_points=trend_points,
        delivery_trend_points=delivery_trend_points,
    )
    comparison_rows = build_comparison_rows(metrics)
    provider_split = build_provider_split(metrics, developer_email=filters.developer_email)

    return DashboardData(
        filters=filters,
        developer_options=developer_options,
        filtered_metrics=metrics,
        summary=summary,
        trend_points=trend_points,
        delivery_trend_points=delivery_trend_points,
        comparison_rows=comparison_rows,
        provider_split=provider_split,
        latest_sync_status=latest_sync_status,
    )


def _matches_search_query(
    metric: DeveloperPeriodMetrics,
    query: str,
) -> bool:
    searchable = " ".join(
        (
            metric.developer_email,
            metric.granularity.value,
            metric.period_start.isoformat(),
            metric.period_end.isoformat(),
            str(metric.github_prs_merged),
            str(metric.github_commits_landed),
            str(metric.github_lines_added),
            str(metric.github_lines_deleted),
            str(metric.jira_issues_assigned),
            str(metric.github_prs_stale),
            str(metric.jira_todo_issues),
            str(metric.jira_in_progress_issues),
            str(metric.jira_review_issues),
            str(metric.jira_done_issues),
            str(metric.jira_other_issues),
        )
    ).lower()
    return all(term in searchable for term in query.split())


def build_dashboard_summary(
    metrics: tuple[DeveloperPeriodMetrics, ...],
    *,
    trend_points: tuple[TrendPoint, ...],
    delivery_trend_points: tuple[DeliveryTrendPoint, ...] = (),
) -> DashboardSummary:
    return DashboardSummary(
        active_developers=len({item.developer_email for item in metrics}),
        period_count=len(trend_points),
        github_prs_merged=sum(item.github_prs_merged for item in metrics),
        github_commits_landed=sum(item.github_commits_landed for item in metrics),
        github_lines_added=sum(item.github_lines_added for item in metrics),
        github_lines_deleted=sum(item.github_lines_deleted for item in metrics),
        jira_issues_assigned=sum(item.jira_issues_assigned for item in metrics),
        github_pr_cycle_time_hours=sum(
            item.github_pr_cycle_time_hours for item in metrics
        ),
        github_prs_with_cycle_time=sum(
            item.github_prs_with_cycle_time for item in metrics
        ),
        github_pr_review_wait_hours=sum(
            item.github_pr_review_wait_hours for item in metrics
        ),
        github_prs_with_review_wait=sum(
            item.github_prs_with_review_wait for item in metrics
        ),
        github_prs_stale=sum(item.github_prs_stale for item in metrics),
        github_prs_small=sum(item.github_prs_small for item in metrics),
        github_prs_medium=sum(item.github_prs_medium for item in metrics),
        github_prs_large=sum(item.github_prs_large for item in metrics),
        jira_todo_issues=sum(item.jira_todo_issues for item in metrics),
        jira_in_progress_issues=sum(
            item.jira_in_progress_issues for item in metrics
        ),
        jira_review_issues=sum(item.jira_review_issues for item in metrics),
        jira_done_issues=sum(item.jira_done_issues for item in metrics),
        jira_other_issues=sum(item.jira_other_issues for item in metrics),
        successful_deployments=sum(
            item.successful_deployments for item in delivery_trend_points
        ),
        failed_deployments=sum(
            item.failed_deployments for item in delivery_trend_points
        ),
        deployment_lead_time_hours=sum(
            item.deployment_lead_time_hours for item in delivery_trend_points
        ),
        deployments_with_lead_time=sum(
            item.deployments_with_lead_time for item in delivery_trend_points
        ),
    )


def build_trend_points(
    metrics: tuple[DeveloperPeriodMetrics, ...],
    *,
    filters: DashboardFilterState,
) -> tuple[TrendPoint, ...]:
    buckets: dict[tuple[date, date], dict[str, int | float]] = defaultdict(
        _new_metric_bucket
    )

    for item in metrics:
        _accumulate_metrics(buckets[(item.period_start, item.period_end)], item)

    for period_start, period_end in _iter_period_windows(
        start_date=filters.start_date,
        end_date=filters.end_date,
        granularity=filters.granularity,
    ):
        buckets[(period_start, period_end)]

    return tuple(
        TrendPoint(
            period_start=period_start,
            period_end=period_end,
            **{field: values[field] for field in _METRIC_FIELDS},
        )
        for (period_start, period_end), values in sorted(buckets.items())
    )


def build_delivery_trend_points(
    delivery_metrics: tuple[TeamPeriodDeliveryMetrics, ...],
    *,
    filters: DashboardFilterState,
) -> tuple[DeliveryTrendPoint, ...]:
    buckets: dict[tuple[date, date], dict[str, int | float]] = defaultdict(
        lambda: {
            "successful_deployments": 0,
            "failed_deployments": 0,
            "deployment_lead_time_hours": 0.0,
            "deployments_with_lead_time": 0,
        }
    )

    for item in delivery_metrics:
        bucket = buckets[(item.period_start, item.period_end)]
        bucket["successful_deployments"] += item.successful_deployments
        bucket["failed_deployments"] += item.failed_deployments
        bucket["deployment_lead_time_hours"] += item.deployment_lead_time_hours
        bucket["deployments_with_lead_time"] += item.deployments_with_lead_time

    for period_start, period_end in _iter_period_windows(
        start_date=filters.start_date,
        end_date=filters.end_date,
        granularity=filters.granularity,
    ):
        buckets[(period_start, period_end)]

    return tuple(
        DeliveryTrendPoint(
            period_start=period_start,
            period_end=period_end,
            successful_deployments=values["successful_deployments"],
            failed_deployments=values["failed_deployments"],
            deployment_lead_time_hours=values["deployment_lead_time_hours"],
            deployments_with_lead_time=values["deployments_with_lead_time"],
        )
        for (period_start, period_end), values in sorted(buckets.items())
    )


def build_comparison_rows(
    metrics: tuple[DeveloperPeriodMetrics, ...],
) -> tuple[DeveloperComparisonRow, ...]:
    buckets: dict[str, dict[str, int | float]] = defaultdict(_new_metric_bucket)

    for item in metrics:
        _accumulate_metrics(buckets[item.developer_email], item)

    return tuple(
        DeveloperComparisonRow(
            developer_email=developer_email,
            **{field: values[field] for field in _METRIC_FIELDS},
        )
        for developer_email, values in sorted(buckets.items())
    )


def build_provider_split(
    metrics: tuple[DeveloperPeriodMetrics, ...],
    *,
    developer_email: str | None,
) -> ProviderSplit:
    summary = build_dashboard_summary(metrics, trend_points=())
    return ProviderSplit(
        scope_label=developer_email or "Team total",
        github_prs_merged=summary.github_prs_merged,
        github_commits_landed=summary.github_commits_landed,
        github_lines_added=summary.github_lines_added,
        github_lines_deleted=summary.github_lines_deleted,
        jira_issues_assigned=summary.jira_issues_assigned,
    )


def default_filter_state(sqlite_path: str) -> DashboardFilterState:
    latest_sync_status = _fetch_latest_sync_status(sqlite_path=sqlite_path)
    if latest_sync_status is None:
        today = date.today()
        return DashboardFilterState(
            start_date=today,
            end_date=today,
            granularity=Granularity.WEEK,
            developer_email=None,
        )

    return DashboardFilterState(
        start_date=latest_sync_status.start_date,
        end_date=latest_sync_status.end_date,
        granularity=latest_sync_status.granularity,
        developer_email=None,
    )


def _fetch_filtered_metrics(
    *,
    sqlite_path: str,
    filters: DashboardFilterState,
) -> tuple[DeveloperPeriodMetrics, ...]:
    with closing(_connect(sqlite_path)) as connection:
        return _fetch_filtered_metrics_with_conn(connection=connection, filters=filters)


def _fetch_filtered_metrics_with_conn(
    *,
    connection: sqlite3.Connection,
    filters: DashboardFilterState,
) -> tuple[DeveloperPeriodMetrics, ...]:
    params: list[object] = [
        filters.granularity.value,
        filters.start_date.isoformat(),
        filters.end_date.isoformat(),
    ]
    developer_clause = ""
    if filters.developer_email is not None:
        developer_clause = "AND developer_email = ?"
        params.append(filters.developer_email)

    jira_metric_column = resolve_jira_metric_column(connection)
    select_columns = developer_period_metric_select_columns(
        jira_metric_column=jira_metric_column,
        indent="            ",
    )
    rows = connection.execute(
        f"""
        SELECT
{select_columns}
        FROM developer_period_metrics
        WHERE granularity = ?
          AND period_end >= ?
          AND period_start <= ?
          {developer_clause}
        ORDER BY period_start, developer_email
        """,
        params,
    ).fetchall()

    return tuple(developer_period_metric_from_row(row) for row in rows)


def _fetch_delivery_metrics(
    *,
    sqlite_path: str,
    filters: DashboardFilterState,
) -> tuple[TeamPeriodDeliveryMetrics, ...]:
    with closing(_connect(sqlite_path)) as connection:
        return _fetch_delivery_metrics_with_conn(connection=connection, filters=filters)


def _fetch_delivery_metrics_with_conn(
    *,
    connection: sqlite3.Connection,
    filters: DashboardFilterState,
) -> tuple[TeamPeriodDeliveryMetrics, ...]:
    select_columns = team_period_delivery_metric_select_columns(indent="            ")
    rows = connection.execute(
        f"""
        SELECT
{select_columns}
        FROM team_period_delivery_metrics
        WHERE granularity = ?
          AND period_end >= ?
          AND period_start <= ?
        ORDER BY period_start
        """,
        (
            filters.granularity.value,
            filters.start_date.isoformat(),
            filters.end_date.isoformat(),
        ),
    ).fetchall()

    return tuple(team_period_delivery_metric_from_row(row) for row in rows)


def _fetch_developer_options(
    *,
    sqlite_path: str,
    filters: DashboardFilterState,
    team_members: tuple[str, ...],
) -> tuple[str, ...]:
    with closing(_connect(sqlite_path)) as connection:
        return _fetch_developer_options_with_conn(
            connection=connection, filters=filters, team_members=team_members,
        )


def _fetch_developer_options_with_conn(
    *,
    connection: sqlite3.Connection,
    filters: DashboardFilterState,
    team_members: tuple[str, ...],
) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT DISTINCT developer_email
        FROM developer_period_metrics
        WHERE granularity = ?
          AND period_end >= ?
          AND period_start <= ?
        ORDER BY developer_email
        """,
        (
            filters.granularity.value,
            filters.start_date.isoformat(),
            filters.end_date.isoformat(),
        ),
    ).fetchall()

    developer_emails = {row["developer_email"] for row in rows}
    developer_emails.update(team_members)
    return tuple(sorted(developer_emails))


def _fetch_latest_sync_status(*, sqlite_path: str) -> SyncStatus | None:
    with closing(_connect(sqlite_path)) as connection:
        return _fetch_latest_sync_status_with_conn(connection=connection)


def _fetch_latest_sync_status_with_conn(
    *,
    connection: sqlite3.Connection,
) -> SyncStatus | None:
    available_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sync_runs)").fetchall()
    }
    discovered_column = (
        "discovered_repository_count"
        if "discovered_repository_count" in available_columns
        else "github_repository_count"
    )
    excluded_column = (
        "excluded_repository_count"
        if "excluded_repository_count" in available_columns
        else "0"
    )
    row = connection.execute(
        f"""
        SELECT
            run_id,
            completed_at,
            start_date,
            end_date,
            granularity,
            github_repository_count,
            {discovered_column} AS discovered_repository_count,
            {excluded_column} AS excluded_repository_count,
            jira_project_count,
            matched_developer_count,
            unmatched_record_count,
            persisted_row_count
        FROM sync_runs
        ORDER BY completed_at DESC
        LIMIT 1
        """
    ).fetchone()

    if row is None:
        return None

    return SyncStatus(
        run_id=row["run_id"],
        completed_at=datetime.fromisoformat(row["completed_at"]),
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]),
        granularity=Granularity(row["granularity"]),
        github_repository_count=row["github_repository_count"],
        discovered_repository_count=row["discovered_repository_count"],
        excluded_repository_count=row["excluded_repository_count"],
        jira_project_count=row["jira_project_count"],
        matched_developer_count=row["matched_developer_count"],
        unmatched_record_count=row["unmatched_record_count"],
        persisted_row_count=row["persisted_row_count"],
    )


def _iter_period_windows(
    *,
    start_date: date,
    end_date: date,
    granularity: Granularity,
) -> tuple[tuple[date, date], ...]:
    if start_date > end_date:
        return ()

    current = bucket_period(start_date, granularity).start
    last = bucket_period(end_date, granularity).start
    windows: list[tuple[date, date]] = []

    while current <= last:
        window = bucket_period(current, granularity)
        windows.append((window.start, window.end))
        current = _advance_period_start(current, granularity)

    return tuple(windows)


def _advance_period_start(current: date, granularity: Granularity) -> date:
    if granularity is Granularity.DAY:
        return current + timedelta(days=1)
    if granularity is Granularity.WEEK:
        return current + timedelta(days=7)
    if granularity is Granularity.MONTH:
        if current.month == 12:
            return current.replace(year=current.year + 1, month=1, day=1)
        return current.replace(month=current.month + 1, day=1)
    raise ValueError(f"Unsupported granularity: {granularity!r}")


def load_commit_heatmap(
    *,
    sqlite_path: str,
    start_date: date,
    end_date: date,
    developer_email: str | None = None,
) -> tuple[CommitHeatmapCell, ...]:
    """Return commit counts grouped by day-of-week and hour-of-day."""
    with closing(_connect(sqlite_path)) as connection:
        return _build_commit_heatmap_with_conn(
            connection=connection,
            start_date=start_date,
            end_date=end_date,
            developer_email=developer_email,
        )


def _build_commit_heatmap_with_conn(
    *,
    connection: sqlite3.Connection,
    start_date: date,
    end_date: date,
    developer_email: str | None,
) -> tuple[CommitHeatmapCell, ...]:
    start_datetime, end_datetime = _datetime_filter_bounds(start_date, end_date)
    params: list[object] = [start_datetime, end_datetime]
    dev_clause = ""
    if developer_email is not None:
        dev_clause = "AND author_email = ?"
        params.append(developer_email)

    rows = connection.execute(
        f"""
        SELECT
            CAST(strftime('%w', datetime(committed_at, '+9 hours')) AS INTEGER) AS dow,
            CAST(strftime('%H', datetime(committed_at, '+9 hours')) AS INTEGER) AS hour,
            COUNT(*) AS cnt
        FROM normalized_github_commits
        WHERE committed_at BETWEEN ? AND ?
          {dev_clause}
        GROUP BY dow, hour
        ORDER BY dow, hour
        """,
        params,
    ).fetchall()

    return tuple(
        CommitHeatmapCell(
            day_of_week=row["dow"],
            hour=row["hour"],
            commit_count=row["cnt"],
        )
        for row in rows
    )


def load_developer_focus(
    *,
    sqlite_path: str,
    granularity: Granularity,
    start_date: date,
    end_date: date,
    developer_email: str | None = None,
) -> tuple[DeveloperFocusRow, ...]:
    """Return active repo count per developer per period."""
    with closing(_connect(sqlite_path)) as connection:
        return _build_developer_focus_with_conn(
            connection=connection,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            developer_email=developer_email,
        )


def _build_developer_focus_with_conn(
    *,
    connection: sqlite3.Connection,
    granularity: Granularity,
    start_date: date,
    end_date: date,
    developer_email: str | None,
) -> tuple[DeveloperFocusRow, ...]:
    dev_clause = ""
    start_datetime, end_datetime = _datetime_filter_bounds(start_date, end_date)
    base_params: list[object] = [start_datetime, end_datetime]
    if developer_email is not None:
        dev_clause = "AND author_email = ?"
        base_params.append(developer_email)

    # Both halves of UNION ALL need the same params
    all_params = base_params + base_params

    rows = connection.execute(
        f"""
        SELECT author_email, repository, date(committed_at) AS activity_date
        FROM normalized_github_commits
        WHERE committed_at BETWEEN ? AND ?
          {dev_clause}
        UNION ALL
        SELECT author_email, repository, date(merged_at) AS activity_date
        FROM normalized_github_pull_requests
        WHERE merged_at BETWEEN ? AND ?
          {dev_clause}
        """,
        all_params,
    ).fetchall()

    # Bucket by developer + period
    buckets: dict[tuple[str, date, date], set[str]] = defaultdict(set)
    for row in rows:
        activity_date = date.fromisoformat(row["activity_date"])
        period = bucket_period(activity_date, granularity)
        buckets[(row["author_email"], period.start, period.end)].add(row["repository"])

    return tuple(
        DeveloperFocusRow(
            developer_email=email,
            period_start=p_start,
            period_end=p_end,
            active_repo_count=len(repos),
            repo_names=tuple(sorted(repos)),
        )
        for (email, p_start, p_end), repos in sorted(buckets.items())
    )


def _datetime_filter_bounds(start_date: date, end_date: date) -> tuple[str, str]:
    start_datetime, end_datetime = utc_day_bounds(start_date, end_date)
    return start_datetime.isoformat(), end_datetime.isoformat()


def _connect(sqlite_path: str) -> sqlite3.Connection:
    return connect_sqlite(
        sqlite_path=sqlite_path,
        initialize_schema=True,
        create_parent=False,
    )
