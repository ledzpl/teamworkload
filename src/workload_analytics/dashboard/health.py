from __future__ import annotations

import math
from dataclasses import dataclass

from workload_analytics.config import ThresholdConfig
from workload_analytics.dashboard.queries import (
    DashboardData,
    DashboardSummary,
    DeveloperComparisonRow,
    TrendPoint,
)


@dataclass(frozen=True, slots=True)
class HealthIndicator:
    label_ko: str
    status: str  # "good", "caution", "warning", "no_data"
    status_ko: str
    description_ko: str


def build_health_indicators(
    data: DashboardData,
    *,
    thresholds: ThresholdConfig | None = None,
) -> tuple[HealthIndicator, ...]:
    cfg = thresholds or ThresholdConfig()
    return (
        _workload_distribution(data.comparison_rows, cfg),
        _review_flow(data.summary, cfg),
        _wip_trend(data.trend_points, cfg),
        _deployment_stability(data.summary, cfg),
        _jira_throughput(data.trend_points),
    )


def _workload_distribution(
    rows: tuple[DeveloperComparisonRow, ...],
    cfg: ThresholdConfig,
) -> HealthIndicator:
    label = "업무 분배도"
    if len(rows) < 2:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="비교할 개발자가 2명 미만입니다.",
        )

    values = [
        r.github_prs_merged + r.github_commits_landed
        for r in rows
    ]
    mean = sum(values) / len(values)
    if mean == 0:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="활동 데이터가 없습니다.",
        )

    variance = sum((v - mean) ** 2 for v in values) / len(values)
    cv = math.sqrt(variance) / mean

    if cv < cfg.workload_cv_good:
        return HealthIndicator(
            label_ko=label, status="good", status_ko="양호",
            description_ko=f"변동계수 {cv:.2f} — 업무가 고르게 분배되어 있습니다.",
        )
    if cv < cfg.workload_cv_caution:
        return HealthIndicator(
            label_ko=label, status="caution", status_ko="주의",
            description_ko=f"변동계수 {cv:.2f} — 일부 개발자에게 업무가 편중될 수 있습니다.",
        )
    return HealthIndicator(
        label_ko=label, status="warning", status_ko="경고",
        description_ko=f"변동계수 {cv:.2f} — 업무 편중이 심합니다.",
    )


def _review_flow(
    summary: DashboardSummary,
    cfg: ThresholdConfig,
) -> HealthIndicator:
    label = "리뷰 흐름"
    if summary.github_prs_with_review_wait == 0:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="리뷰 대기 데이터가 없습니다.",
        )

    avg_wait = summary.github_pr_review_wait_hours / summary.github_prs_with_review_wait

    if avg_wait < cfg.review_wait_caution_hours:
        return HealthIndicator(
            label_ko=label, status="good", status_ko="양호",
            description_ko=f"평균 리뷰 대기 {avg_wait:.1f}시간 — 리뷰가 원활합니다.",
        )
    if avg_wait < cfg.review_wait_warning_hours:
        return HealthIndicator(
            label_ko=label, status="caution", status_ko="주의",
            description_ko=f"평균 리뷰 대기 {avg_wait:.1f}시간 — 리뷰 속도를 점검하세요.",
        )
    return HealthIndicator(
        label_ko=label, status="warning", status_ko="경고",
        description_ko=f"평균 리뷰 대기 {avg_wait:.1f}시간 — 리뷰 병목이 심각합니다.",
    )


def _wip_trend(
    trend_points: tuple[TrendPoint, ...],
    cfg: ThresholdConfig,
) -> HealthIndicator:
    label = "WIP 추세"
    if len(trend_points) < 3:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="추세를 판단하려면 최소 3개 기간이 필요합니다.",
        )

    recent = trend_points[-3:]
    wip_values = [
        p.jira_todo_issues + p.jira_in_progress_issues + p.jira_review_issues
        for p in recent
    ]

    if wip_values[0] == 0:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="WIP 데이터가 없습니다.",
        )

    change_rate = (wip_values[-1] - wip_values[0]) / max(wip_values[0], 1)

    if change_rate <= 0:
        return HealthIndicator(
            label_ko=label, status="good", status_ko="양호",
            description_ko="진행 중 업무가 감소 또는 안정적입니다.",
        )
    if change_rate < cfg.wip_trend_caution_rate:
        return HealthIndicator(
            label_ko=label, status="caution", status_ko="주의",
            description_ko=f"진행 중 업무가 {change_rate:.0%} 증가하고 있습니다.",
        )
    return HealthIndicator(
        label_ko=label, status="warning", status_ko="경고",
        description_ko=f"진행 중 업무가 {change_rate:.0%} 급증하고 있습니다.",
    )


def _deployment_stability(
    summary: DashboardSummary,
    cfg: ThresholdConfig,
) -> HealthIndicator:
    label = "배포 안정성"
    total = summary.successful_deployments + summary.failed_deployments
    if total == 0:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="배포 데이터가 없습니다.",
        )

    success_rate = summary.successful_deployments / total

    if success_rate > cfg.deployment_success_good:
        return HealthIndicator(
            label_ko=label, status="good", status_ko="양호",
            description_ko=f"배포 성공률 {success_rate:.0%} — 안정적입니다.",
        )
    if success_rate > cfg.deployment_success_caution:
        return HealthIndicator(
            label_ko=label, status="caution", status_ko="주의",
            description_ko=f"배포 성공률 {success_rate:.0%} — CI/CD 파이프라인을 점검하세요.",
        )
    return HealthIndicator(
        label_ko=label, status="warning", status_ko="경고",
        description_ko=f"배포 성공률 {success_rate:.0%} — 배포 안정성이 심각하게 낮습니다.",
    )


def _jira_throughput(
    trend_points: tuple[TrendPoint, ...],
) -> HealthIndicator:
    """Assess whether the team is closing issues faster than opening them."""
    label = "처리 흐름"
    if len(trend_points) < 2:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="처리량 추세를 판단하려면 최소 2개 기간이 필요합니다.",
        )

    recent = trend_points[-3:] if len(trend_points) >= 3 else trend_points
    total_assigned = sum(p.jira_issues_assigned for p in recent)
    total_done = sum(p.jira_done_issues for p in recent)

    if total_assigned == 0:
        return HealthIndicator(
            label_ko=label, status="no_data", status_ko="데이터 부족",
            description_ko="Jira 이슈 데이터가 없습니다.",
        )

    done_rate = total_done / total_assigned

    if done_rate >= 0.8:
        return HealthIndicator(
            label_ko=label, status="good", status_ko="양호",
            description_ko=f"완료율 {done_rate:.0%} — 이슈를 안정적으로 처리하고 있습니다.",
        )
    if done_rate >= 0.5:
        return HealthIndicator(
            label_ko=label, status="caution", status_ko="주의",
            description_ko=f"완료율 {done_rate:.0%} — 미완료 이슈가 쌓일 수 있습니다.",
        )
    return HealthIndicator(
        label_ko=label, status="warning", status_ko="경고",
        description_ko=f"완료율 {done_rate:.0%} — 할당 대비 완료가 크게 부족합니다.",
    )
