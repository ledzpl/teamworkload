from __future__ import annotations

from dataclasses import dataclass

from workload_analytics.dashboard.queries import DashboardSummary, PreviousPeriodResult, SyncStatus, TrendPoint


@dataclass(frozen=True, slots=True)
class TrendDelta:
    label: str
    values: tuple[int | float, ...]
    period_labels: tuple[str, ...]
    direction: str  # "up", "down", "flat"
    change_pct: float | None


@dataclass(frozen=True, slots=True)
class SummaryCard:
    label: str
    value: str
    detail: str
    delta: str | None = None
    delta_direction: str | None = None


def build_summary_cards(
    *,
    summary: DashboardSummary,
    sync_status: SyncStatus | None,
    previous_result: PreviousPeriodResult | None = None,
) -> tuple[SummaryCard, ...]:
    if sync_status is None:
        sync_value = "No sync run available"
        sync_detail = "Run a sync first"
    else:
        sync_value = (
            f"{sync_status.github_repository_count} repos in scope, "
            f"{sync_status.jira_project_count} Jira projects"
        )
        if sync_status.excluded_repository_count > 0:
            sync_detail = (
                f"{sync_status.discovered_repository_count} repos discovered, "
                f"{sync_status.excluded_repository_count} excluded, "
                f"{sync_status.unmatched_record_count} unmatched records"
            )
        else:
            sync_detail = f"{sync_status.unmatched_record_count} unmatched records"

    average_cycle_hours = _format_average(
        summary.github_pr_cycle_time_hours,
        summary.github_prs_with_cycle_time,
    )
    average_review_wait_hours = _format_average(
        summary.github_pr_review_wait_hours,
        summary.github_prs_with_review_wait,
    )
    active_wip = (
        summary.jira_todo_issues
        + summary.jira_in_progress_issues
        + summary.jira_review_issues
    )
    average_deployment_lead_hours = _format_average(
        summary.deployment_lead_time_hours,
        summary.deployments_with_lead_time,
    )

    prev = previous_result.summary if previous_result else None
    period_label = (
        f"{previous_result.start_date.strftime('%m/%d')}~{previous_result.end_date.strftime('%m/%d')}"
        if previous_result else None
    )
    prev_active_wip = (
        (prev.jira_todo_issues + prev.jira_in_progress_issues + prev.jira_review_issues)
        if prev else None
    )

    developers_delta = _compute_delta(summary.active_developers, prev.active_developers if prev else None, period_label=period_label)
    prs_delta = _compute_delta(summary.github_prs_merged, prev.github_prs_merged if prev else None, period_label=period_label)
    wip_delta = _compute_delta(active_wip, prev_active_wip, invert=True, period_label=period_label)
    deployments_delta = _compute_delta(
        summary.successful_deployments,
        prev.successful_deployments if prev else None,
        period_label=period_label,
    )

    return (
        SummaryCard(
            label="Active Developers",
            value=str(summary.active_developers),
            detail=f"{summary.period_count} periods in view",
            delta=developers_delta[0],
            delta_direction=developers_delta[1],
        ),
        SummaryCard(
            label="GitHub Signals",
            value=f"{summary.github_prs_merged} PRs / {summary.github_commits_landed} commits",
            detail=f"{summary.github_lines_added} added, {summary.github_lines_deleted} deleted",
            delta=prs_delta[0],
            delta_direction=prs_delta[1],
        ),
        SummaryCard(
            label="PR Flow",
            value=f"{average_cycle_hours}h cycle",
            detail=(
                f"{average_review_wait_hours}h review wait, "
                f"{summary.github_prs_stale} stale PRs"
            ),
        ),
        SummaryCard(
            label="Jira WIP",
            value=str(active_wip),
            detail=(
                f"{summary.jira_in_progress_issues} in progress, "
                f"{summary.jira_review_issues} in review"
            ),
            delta=wip_delta[0],
            delta_direction=wip_delta[1],
        ),
        SummaryCard(
            label="Delivery",
            value=(
                f"{summary.successful_deployments} success / "
                f"{summary.failed_deployments} failed"
            ),
            detail=f"{average_deployment_lead_hours}h avg deployment lead",
            delta=deployments_delta[0],
            delta_direction=deployments_delta[1],
        ),
        SummaryCard(
            label="Sync Scope",
            value=sync_value,
            detail=sync_detail,
        ),
    )


def _compute_delta(
    current: int | float,
    previous: int | float | None,
    *,
    invert: bool = False,
    period_label: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (delta_text, direction) for a metric comparison.

    ``invert=True`` flips the direction — useful for metrics where a decrease
    is positive (e.g. WIP going down is good).
    """
    if previous is None:
        return None, None

    label = f"({period_label})" if period_label else ""
    diff = current - previous
    if diff == 0:
        return f"변동 없음 {label}".strip(), "flat"

    if previous == 0:
        return f"NEW {label}".strip(), "up" if not invert else "down"

    pct = diff / abs(previous) * 100
    sign = "+" if diff > 0 else ""
    text = f"{sign}{pct:.0f}% {label}".strip()

    if invert:
        direction = "up" if diff < 0 else "down"
    else:
        direction = "up" if diff > 0 else "down"

    return text, direction


def build_trend_deltas(
    trend_points: tuple[TrendPoint, ...],
) -> tuple[TrendDelta, ...]:
    """Compute period-over-period change rates for key metrics."""
    if len(trend_points) < 2:
        return ()

    period_labels = tuple(
        _format_trend_period(p.period_start, p.period_end)
        for p in trend_points
    )

    metrics = (
        ("머지된 PR", "github_prs_merged"),
        ("랜딩된 커밋", "github_commits_landed"),
        ("할당된 이슈", "jira_issues_assigned"),
        ("완료된 이슈", "jira_done_issues"),
        ("Stale PR", "github_prs_stale"),
    )

    deltas: list[TrendDelta] = []
    for label, attr in metrics:
        values = tuple(getattr(p, attr) for p in trend_points)
        first_val = values[0]
        last_val = values[-1]

        if first_val == 0 and last_val == 0:
            direction = "flat"
            change_pct = None
        elif first_val == 0:
            direction = "up"
            change_pct = None
        else:
            change_pct = (last_val - first_val) / first_val * 100
            if change_pct > 0:
                direction = "up"
            elif change_pct < 0:
                direction = "down"
            else:
                direction = "flat"

        deltas.append(TrendDelta(
            label=label,
            values=values,
            period_labels=period_labels,
            direction=direction,
            change_pct=change_pct,
        ))

    return tuple(deltas)


def _format_trend_period(period_start, period_end) -> str:
    if period_start == period_end:
        return period_start.strftime("%m/%d")
    return f"{period_start.strftime('%m/%d')}~{period_end.strftime('%m/%d')}"


def _format_average(total: float, count: int) -> str:
    if count == 0:
        return "0.0"
    return f"{total / count:.1f}"
