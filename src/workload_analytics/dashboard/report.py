from __future__ import annotations

from dataclasses import dataclass

from workload_analytics.dashboard.alerts import build_alerts
from workload_analytics.dashboard.queries import (
    DashboardData,
    DashboardSummary,
)


@dataclass(frozen=True, slots=True)
class ExportedReport:
    file_name: str
    content: str


def build_weekly_report(
    data: DashboardData,
    *,
    previous_summary: DashboardSummary | None = None,
) -> ExportedReport:
    lines: list[str] = []
    _append_header(lines, data)
    _append_team_activity_summary(lines, data.summary, previous_summary)
    _append_alerts(lines, data, previous_summary)
    _append_developer_status(lines, data)
    _append_pr_flow(lines, data.summary)
    _append_jira_wip(lines, data.summary)
    _append_delivery(lines, data.summary)

    lines.append("---")
    lines.append("*이 리포트는 Team Workload Analytics 대시보드에서 자동 생성되었습니다.*")

    filters = data.filters
    return ExportedReport(
        file_name=(
            f"workload-report_{filters.start_date.isoformat()}_"
            f"{filters.end_date.isoformat()}.md"
        ),
        content="\n".join(lines),
    )


def _append_header(lines: list[str], data: DashboardData) -> None:
    filters = data.filters
    lines.append("# 팀 워크로드 주간 리포트")
    lines.append("")
    lines.append(
        f"**기간**: {filters.start_date} ~ {filters.end_date} "
        f"({filters.granularity.value})"
    )
    lines.append("")


def _append_team_activity_summary(
    lines: list[str],
    summary: DashboardSummary,
    previous_summary: DashboardSummary | None,
) -> None:
    lines.extend(
        (
            "## 팀 활동 요약",
            "",
            "| 지표 | 값 |",
            "|------|------|",
            f"| 활성 개발자 | {summary.active_developers}명 |",
            f"| 머지된 PR | {summary.github_prs_merged}건 |",
            f"| 랜딩된 커밋 | {summary.github_commits_landed}건 |",
            f"| 추가된 라인 | {summary.github_lines_added:,} |",
            f"| 삭제된 라인 | {summary.github_lines_deleted:,} |",
            f"| 할당된 이슈 | {summary.jira_issues_assigned}건 |",
        )
    )

    if previous_summary:
        _append_previous_period_changes(lines, summary, previous_summary)
    lines.append("")


def _append_previous_period_changes(
    lines: list[str],
    summary: DashboardSummary,
    previous_summary: DashboardSummary,
) -> None:
    lines.extend(("", "### 전기 대비 변화", ""))
    comparisons = (
        ("머지된 PR", summary.github_prs_merged, previous_summary.github_prs_merged),
        (
            "랜딩된 커밋",
            summary.github_commits_landed,
            previous_summary.github_commits_landed,
        ),
        (
            "할당된 이슈",
            summary.jira_issues_assigned,
            previous_summary.jira_issues_assigned,
        ),
    )
    for label, current, previous in comparisons:
        delta = current - previous
        if previous > 0:
            pct = delta / previous * 100
            sign = "+" if delta > 0 else ""
            lines.append(f"- {label}: {current} ({sign}{pct:.0f}%)")
        else:
            lines.append(f"- {label}: {current} (이전 기간 데이터 없음)")


def _append_alerts(
    lines: list[str],
    data: DashboardData,
    previous_summary: DashboardSummary | None,
) -> None:
    alerts = build_alerts(data, previous_summary=previous_summary)
    if not alerts:
        return

    lines.extend(("## 주요 신호", ""))
    severity_icons = {"warning": "⚠️", "info": "ℹ️", "critical": "🚨"}
    for alert in alerts:
        severity_icon = severity_icons.get(alert.severity, "")
        lines.append(f"- {severity_icon} **{alert.title_ko}**: {alert.description_ko}")
    lines.append("")


def _append_developer_status(lines: list[str], data: DashboardData) -> None:
    if not data.comparison_rows:
        return

    lines.extend(
        (
            "## 개발자별 현황",
            "",
            "| 개발자 | PR | 커밋 | 이슈 | WIP |",
            "|--------|-----|------|------|-----|",
        )
    )
    for row in data.comparison_rows:
        wip = row.jira_todo_issues + row.jira_in_progress_issues + row.jira_review_issues
        name = row.developer_email.split("@")[0]
        lines.append(
            f"| {name} | {row.github_prs_merged} | "
            f"{row.github_commits_landed} | {row.jira_issues_assigned} | {wip} |"
        )
    lines.append("")


def _append_pr_flow(lines: list[str], summary: DashboardSummary) -> None:
    lines.extend(("## PR 흐름 현황", ""))
    if summary.github_prs_with_cycle_time > 0:
        avg_cycle = summary.github_pr_cycle_time_hours / summary.github_prs_with_cycle_time
        lines.append(f"- 평균 cycle time: {avg_cycle:.1f}시간")
    if summary.github_prs_with_review_wait > 0:
        avg_wait = summary.github_pr_review_wait_hours / summary.github_prs_with_review_wait
        lines.append(f"- 평균 리뷰 대기: {avg_wait:.1f}시간")
    lines.append(f"- Stale PR: {summary.github_prs_stale}건")
    total_prs = (
        summary.github_prs_small
        + summary.github_prs_medium
        + summary.github_prs_large
    )
    if total_prs > 0:
        lines.append(
            f"- PR 크기 분포: S {summary.github_prs_small} / "
            f"M {summary.github_prs_medium} / L {summary.github_prs_large}"
        )
    lines.append("")


def _append_jira_wip(lines: list[str], summary: DashboardSummary) -> None:
    active_wip = (
        summary.jira_todo_issues
        + summary.jira_in_progress_issues
        + summary.jira_review_issues
    )
    lines.extend(
        (
            "## Jira WIP 현황",
            "",
            f"- 진행 중 업무 (WIP): {active_wip}건",
            f"  - Todo: {summary.jira_todo_issues}",
            f"  - In Progress: {summary.jira_in_progress_issues}",
            f"  - Review: {summary.jira_review_issues}",
            f"- Done: {summary.jira_done_issues}",
        )
    )
    if summary.jira_issues_assigned > 0:
        done_rate = summary.jira_done_issues / summary.jira_issues_assigned * 100
        lines.append(f"- 완료율 (Done / Assigned): {done_rate:.0f}%")
    lines.append("")


def _append_delivery(lines: list[str], summary: DashboardSummary) -> None:
    total_deploys = summary.successful_deployments + summary.failed_deployments
    if total_deploys == 0:
        return

    lines.extend(
        (
            "## 배포 현황",
            "",
            f"- 성공: {summary.successful_deployments}건",
            f"- 실패: {summary.failed_deployments}건",
        )
    )
    if summary.deployments_with_lead_time > 0:
        avg_lead = summary.deployment_lead_time_hours / summary.deployments_with_lead_time
        lines.append(f"- 평균 리드 타임: {avg_lead:.1f}시간")
    lines.append("")
