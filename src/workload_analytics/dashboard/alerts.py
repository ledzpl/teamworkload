from __future__ import annotations

from dataclasses import dataclass

from workload_analytics.config import ThresholdConfig
from workload_analytics.dashboard.queries import (
    DashboardData,
    DashboardSummary,
    DeveloperComparisonRow,
)


@dataclass(frozen=True, slots=True)
class Alert:
    severity: str  # "info", "warning", "critical"
    category: str
    title_ko: str
    description_ko: str


def build_alerts(
    data: DashboardData,
    *,
    previous_summary: DashboardSummary | None = None,
    thresholds: ThresholdConfig | None = None,
) -> tuple[Alert, ...]:
    cfg = thresholds or ThresholdConfig()
    alerts: list[Alert] = []
    alerts.extend(_check_wip_concentration(data.comparison_rows, cfg))
    alerts.extend(_check_review_bottleneck(data.summary, cfg))
    alerts.extend(_check_stale_pr_accumulation(data.summary, cfg))
    alerts.extend(_check_large_pr_ratio(data.summary, cfg))
    alerts.extend(
        _check_inactivity(data.comparison_rows, previous_summary=previous_summary)
    )
    alerts.extend(_check_review_wait_outlier(data.comparison_rows, cfg))
    return tuple(alerts)


def _check_wip_concentration(
    rows: tuple[DeveloperComparisonRow, ...],
    cfg: ThresholdConfig,
) -> list[Alert]:
    if len(rows) < 2:
        return []
    wip_values = [
        (r.developer_email, r.jira_todo_issues + r.jira_in_progress_issues + r.jira_review_issues)
        for r in rows
    ]
    total_wip = sum(v for _, v in wip_values)
    if total_wip == 0:
        return []
    avg_wip = total_wip / len(wip_values)
    overloaded = [(email, wip) for email, wip in wip_values if wip > avg_wip * cfg.wip_concentration_factor]
    if not overloaded:
        return []
    names = ", ".join(e.split("@")[0] for e, _ in overloaded)
    return [
        Alert(
            severity="warning",
            category="workload_imbalance",
            title_ko="WIP 편중 감지",
            description_ko=(
                f"{names}의 진행 중 업무가 팀 평균({avg_wip:.0f}건)의 "
                f"{cfg.wip_concentration_factor:.0f}배를 초과합니다."
            ),
        )
    ]


def _check_review_bottleneck(
    summary: DashboardSummary,
    cfg: ThresholdConfig,
) -> list[Alert]:
    if summary.github_prs_with_review_wait == 0:
        return []
    avg_wait = summary.github_pr_review_wait_hours / summary.github_prs_with_review_wait
    if avg_wait <= cfg.review_wait_hours:
        return []
    return [
        Alert(
            severity="warning",
            category="review_bottleneck",
            title_ko="리뷰 병목 감지",
            description_ko=f"평균 첫 리뷰 대기 시간이 {avg_wait:.1f}시간으로 {cfg.review_wait_hours:.0f}시간을 초과합니다.",
        )
    ]


def _check_stale_pr_accumulation(
    summary: DashboardSummary,
    cfg: ThresholdConfig,
) -> list[Alert]:
    if summary.github_prs_stale <= cfg.stale_pr_count:
        return []
    return [
        Alert(
            severity="warning",
            category="stale_pr",
            title_ko="Stale PR 누적",
            description_ko=(
                f"장기 미머지 PR이 {summary.github_prs_stale}건 누적되어 있습니다. "
                "방치된 작업을 점검하세요."
            ),
        )
    ]


def _check_large_pr_ratio(
    summary: DashboardSummary,
    cfg: ThresholdConfig,
) -> list[Alert]:
    total_prs = summary.github_prs_small + summary.github_prs_medium + summary.github_prs_large
    if total_prs == 0:
        return []
    large_ratio = summary.github_prs_large / total_prs
    if large_ratio <= cfg.large_pr_ratio:
        return []
    return [
        Alert(
            severity="info",
            category="large_pr_ratio",
            title_ko="대형 PR 비율 높음",
            description_ko=(
                f"전체 PR 중 {large_ratio:.0%}가 {cfg.large_pr_lines}줄 이상의 대형 PR입니다. "
                "PR 쪼개기를 검토하세요."
            ),
        )
    ]


def _check_inactivity(
    rows: tuple[DeveloperComparisonRow, ...],
    *,
    previous_summary: DashboardSummary | None,
) -> list[Alert]:
    if previous_summary is None:
        return []
    inactive = [
        r.developer_email
        for r in rows
        if (r.github_prs_merged + r.github_commits_landed + r.jira_issues_assigned) == 0
    ]
    if not inactive or previous_summary.active_developers == 0:
        return []
    names = ", ".join(e.split("@")[0] for e in inactive)
    return [
        Alert(
            severity="info",
            category="inactivity",
            title_ko="비활성 개발자 감지",
            description_ko=(
                f"{names}의 현재 기간 활동이 0건입니다. "
                "휴가, 온보딩, 또는 데이터 연결 상태를 확인하세요."
            ),
        )
    ]


def _check_review_wait_outlier(
    rows: tuple[DeveloperComparisonRow, ...],
    cfg: ThresholdConfig,
) -> list[Alert]:
    """Flag developers whose average review wait is 2x the team average."""
    devs_with_data = [
        (r.developer_email, r.github_pr_review_wait_hours / r.github_prs_with_review_wait)
        for r in rows
        if r.github_prs_with_review_wait > 0
    ]
    if len(devs_with_data) < 2:
        return []
    team_avg = sum(avg for _, avg in devs_with_data) / len(devs_with_data)
    if team_avg == 0:
        return []
    outliers = [
        (email, avg)
        for email, avg in devs_with_data
        if avg > team_avg * 2 and avg > cfg.review_wait_caution_hours
    ]
    if not outliers:
        return []
    names = ", ".join(
        f"{e.split('@')[0]}({avg:.0f}h)" for e, avg in outliers
    )
    return [
        Alert(
            severity="info",
            category="review_wait_outlier",
            title_ko="리뷰 대기 이상치 감지",
            description_ko=(
                f"{names}의 평균 리뷰 대기 시간이 팀 평균({team_avg:.1f}h)의 2배를 초과합니다."
            ),
        )
    ]
