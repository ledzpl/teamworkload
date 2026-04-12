from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from html import escape
import os
import sys

from workload_analytics.config import Granularity, ThresholdConfig, load_threshold_config
from workload_analytics.config.team_scope import parse_csv_list, parse_team_members
from workload_analytics.dashboard.alerts import build_alerts
from workload_analytics.dashboard.charts import (
    build_commit_heatmap_figure,
    build_delivery_figure,
    build_developer_comparison_figure,
    build_developer_focus_figure,
    build_jira_throughput_figure,
    build_pr_flow_figure,
    build_provider_split_figure,
    build_review_efficiency_figure,
    build_team_trend_figure,
    build_trend_sparkline_figure,
    build_workload_balance_figure,
)
from workload_analytics.dashboard.health import build_health_indicators
from workload_analytics.dashboard.report import build_weekly_report
from workload_analytics.dashboard.export import (
    build_filtered_metrics_csv,
    build_filtered_metrics_excel,
    build_filtered_metrics_json,
)
from workload_analytics.dashboard.guides import (
    render_alerts_guide as _render_alerts_guide,
    render_health_guide as _render_health_guide,
    render_overview_guide as _render_overview_guide,
    render_signal_chart_guide as _render_signal_chart_guide,
)
from workload_analytics.dashboard.filters import (
    DashboardFilterState,
    normalize_developer_selection,
)
from workload_analytics.dashboard.queries import (
    apply_dashboard_search,
    default_filter_state,
    load_commit_heatmap,
    load_dashboard_data,
    load_developer_focus,
    load_previous_period_summary,
)
from workload_analytics.dashboard.styles import DASHBOARD_STYLES
from workload_analytics.dashboard.summary import build_summary_cards, build_trend_deltas


class DashboardArgumentError(ValueError):
    """Raised when dashboard CLI arguments are invalid."""


class DashboardConfigError(ValueError):
    """Raised when dashboard-specific environment configuration is invalid."""


@dataclass(frozen=True, slots=True)
class DashboardRuntimeSettings:
    sqlite_path: str
    team_members: tuple[str, ...]
    thresholds: ThresholdConfig = ThresholdConfig()


def main() -> None:
    st = _streamlit()
    _configure_page(st)

    try:
        settings = load_dashboard_runtime_settings()
        sqlite_path = resolve_dashboard_sqlite_path(
            argv=sys.argv,
            default_sqlite_path=settings.sqlite_path,
        )
    except (DashboardArgumentError, DashboardConfigError) as exc:
        st.error(str(exc))
        st.stop()

    try:
        filter_defaults = default_filter_state(sqlite_path)
    except Exception as exc:
        st.error(f"Failed to load dashboard state from SQLite {sqlite_path!r}: {exc}")
        st.stop()

    try:
        data = load_dashboard_data(
            sqlite_path=sqlite_path,
            filters=filter_defaults,
            team_members=settings.team_members,
        )
        developer_options = data.developer_options
    except Exception as exc:
        st.error(f"Failed to load dashboard state from SQLite {sqlite_path!r}: {exc}")
        st.stop()

    _render_hero(
        st=st,
        sqlite_path=sqlite_path,
        developer_count=len(developer_options),
        latest_sync_status=data.latest_sync_status,
    )
    filters, search_query = _render_filters(
        st=st,
        defaults=filter_defaults,
        developer_options=developer_options,
    )
    if filters != filter_defaults:
        try:
            data = load_dashboard_data(
                sqlite_path=sqlite_path,
                filters=filters,
                team_members=settings.team_members,
            )
        except Exception as exc:
            st.error(f"Failed to query filtered dashboard data from SQLite {sqlite_path!r}: {exc}")
            st.stop()

    data = apply_dashboard_search(data, query=search_query)
    csv_export = build_filtered_metrics_csv(data)

    previous_result = load_previous_period_summary(
        sqlite_path=sqlite_path,
        filters=filters,
    )

    thresholds = settings.thresholds

    _render_filter_feedback(st, data, search_query)
    _render_overview_section(st, data, previous_result=previous_result)
    _render_trend_deltas_section(st, data)
    _render_health_section(st, data, thresholds=thresholds)
    _render_alerts_section(st, data, previous_result=previous_result, thresholds=thresholds)
    _render_signal_section(st, data, csv_export, sqlite_path=sqlite_path, previous_result=previous_result)
    _render_reference_section(st, sqlite_path, filters, search_query)


def _configure_page(st) -> None:
    st.set_page_config(
        page_title="Team Workload Analytics",
        page_icon="WK",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_styles(st)
    _render_top_nav(st)


def _render_filter_feedback(st, data, search_query: str) -> None:
    if data.latest_sync_status and data.latest_sync_status.unmatched_record_count:
        st.warning(
            f"{data.latest_sync_status.unmatched_record_count} records from the latest sync could not be matched to a developer email."
        )
    if search_query.strip():
        _render_active_search(
            st=st,
            search_query=search_query,
            result_count=len(data.filtered_metrics),
        )
    if not data.filtered_metrics:
        message = (
            f"No metrics matched {search_query.strip()!r} within the current filters."
            if search_query.strip()
            else "No metrics matched the current filter. Adjust the date range or run a new sync."
        )
        st.info(message)


def _render_overview_section(st, data, *, previous_result=None) -> None:
    summary_cards = build_summary_cards(
        summary=data.summary,
        sync_status=data.latest_sync_status,
        previous_result=previous_result,
    )
    _render_section_heading(
        st=st,
        kicker="Overview",
        anchor="overview",
        title="현재 워크로드 스냅샷",
        description=(
            "현재 필터에 해당하는 팀 활동의 핵심 요약입니다. "
            "각 카드 아래 색상 뱃지는 직전 동일 기간 대비 증감을 나타냅니다."
        ),
    )
    with st.expander("카드 해석 가이드", expanded=False):
        _render_overview_guide(st)
    _render_summary(st=st, cards=summary_cards)


def _render_trend_deltas_section(st, data) -> None:
    deltas = build_trend_deltas(data.trend_points)
    if not deltas:
        return

    _render_section_heading(
        st=st,
        kicker="Trend",
        anchor="trend",
        title="기간별 변화 추세",
        description=(
            "전체 기간의 첫 기간 대비 마지막 기간의 변화율입니다. "
            "각 스파크라인은 기간별 절대값 추이를 나타냅니다."
        ),
    )
    row_size = 3
    for row_start in range(0, len(deltas), row_size):
        row_deltas = deltas[row_start : row_start + row_size]
        cols = st.columns(len(row_deltas), gap="small")
        for col, delta in zip(cols, row_deltas):
            with col:
                try:
                    st.plotly_chart(
                        build_trend_sparkline_figure(delta),
                        width="stretch",
                        config={"displaylogo": False, "displayModeBar": False, "responsive": True},
                    )
                except RuntimeError as exc:
                    st.error(str(exc))


def _render_health_section(st, data, *, thresholds: ThresholdConfig | None = None) -> None:
    indicators = build_health_indicators(data, thresholds=thresholds)
    _render_section_heading(
        st=st,
        kicker="Health",
        anchor="health",
        title="팀 건강 지표",
        description=(
            "5개 핵심 지표의 종합 상태입니다. "
            "단일 지표가 아닌 여러 지표의 패턴을 함께 읽어야 의미가 있습니다."
        ),
    )
    row_size = 3
    for row_start in range(0, len(indicators), row_size):
        row_indicators = indicators[row_start : row_start + row_size]
        col_count = len(row_indicators)
        health_columns = st.columns(col_count, gap="small")
        for col, ind in zip(health_columns, row_indicators):
            with col:
                st.markdown(
                    f"""
                    <div class="health-pill health-{escape(ind.status)}">
                      <span class="health-dot"></span>
                      <span class="health-label">{escape(ind.label_ko)}</span>
                      <span class="health-status">{escape(ind.status_ko)}</span>
                      <span class="health-desc">{escape(ind.description_ko)}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    with st.expander("건강 지표 해석 가이드", expanded=False):
        _render_health_guide(st)


def _render_alerts_section(st, data, *, previous_result=None, thresholds: ThresholdConfig | None = None) -> None:
    previous_summary = previous_result.summary if previous_result else None
    alerts = build_alerts(data, previous_summary=previous_summary, thresholds=thresholds)
    if not alerts:
        return

    _render_section_heading(
        st=st,
        kicker="Alerts",
        anchor="alerts",
        title="운영 경고",
        description=(
            "현재 필터 범위에서 자동 감지된 신호입니다. "
            "경고는 즉각 조치가 아니라 점검 포인트로 읽어야 합니다."
        ),
    )
    alert_columns = st.columns(min(len(alerts), 3), gap="small")
    severity_icons = {"warning": "&#9888;", "info": "&#8505;", "critical": "&#9888;"}
    for idx, alert in enumerate(alerts):
        with alert_columns[idx % len(alert_columns)]:
            icon = severity_icons.get(alert.severity, "")
            st.markdown(
                f"""
                <article class="alert-card alert-{escape(alert.severity)}">
                  <p class="alert-severity-tag alert-tag-{escape(alert.severity)}">{icon} {escape(alert.severity.upper())}</p>
                  <p class="alert-title">{escape(alert.title_ko)}</p>
                  <p class="alert-description">{escape(alert.description_ko)}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )
    with st.expander("경고 유형 해석 가이드", expanded=False):
        _render_alerts_guide(st)


def _render_signal_section(st, data, csv_export, *, sqlite_path: str, previous_result=None) -> None:
    _render_section_heading(
        st=st,
        kicker="Signals",
        title="트렌드 및 비교 뷰",
        description=(
            "팀 합산, 개발자별 비교, 제공자 분포 차트는 동일한 날짜 범위·개발자 선택·글로벌 검색에 동기화됩니다."
        ),
    )
    with st.expander("차트 해석 가이드", expanded=False):
        _render_signal_chart_guide(st)
        _render_signal_guide_items(st)
    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        _render_chart(
            st=st,
            figure_builder=lambda: build_team_trend_figure(data.trend_points),
        )
        _render_chart(
            st=st,
            figure_builder=lambda: build_pr_flow_figure(data.trend_points),
        )
        _render_chart(
            st=st,
            figure_builder=lambda: build_developer_comparison_figure(data.comparison_rows),
        )
        _render_chart(
            st=st,
            figure_builder=lambda: build_jira_throughput_figure(data.trend_points),
        )
    with chart_right:
        _render_chart(
            st=st,
            figure_builder=lambda: build_delivery_figure(data.delivery_trend_points),
        )
        _render_chart(
            st=st,
            figure_builder=lambda: build_review_efficiency_figure(data.comparison_rows),
        )
        _render_chart(
            st=st,
            figure_builder=lambda: build_workload_balance_figure(data.comparison_rows),
        )
        _render_chart(
            st=st,
            figure_builder=lambda: build_provider_split_figure(data.provider_split),
        )

    heatmap_col, focus_col = st.columns(2, gap="large")
    with heatmap_col:
        _render_chart(
            st=st,
            figure_builder=lambda: build_commit_heatmap_figure(
                load_commit_heatmap(
                    sqlite_path=sqlite_path,
                    start_date=data.filters.start_date,
                    end_date=data.filters.end_date,
                    developer_email=data.filters.developer_email,
                )
            ),
        )
    with focus_col:
        _render_chart(
            st=st,
            figure_builder=lambda: build_developer_focus_figure(
                load_developer_focus(
                    sqlite_path=sqlite_path,
                    granularity=data.filters.granularity,
                    start_date=data.filters.start_date,
                    end_date=data.filters.end_date,
                    developer_email=data.filters.developer_email,
                )
            ),
        )

    _render_data_section(st, data, csv_export, previous_result=previous_result)


def _render_data_section(st, data, csv_export, *, previous_result=None) -> None:
    _render_section_heading(
        st=st,
        kicker="Data",
        anchor="data",
        title="원시 데이터 및 내보내기",
        description=(
            "검색 결과와 필터가 적용된 개발자별 기간 지표입니다. "
            "CSV, JSON, Excel, 주간 리포트(Markdown)로 내보낼 수 있습니다."
        ),
    )
    st.dataframe(_metrics_rows(data.filtered_metrics), width="stretch")
    _render_export_buttons(st, data, csv_export, previous_result=previous_result)


def _render_reference_section(
    st,
    sqlite_path: str,
    filters: DashboardFilterState,
    search_query: str,
) -> None:
    _render_section_heading(
        st=st,
        kicker="Reference",
        title="정의 및 추적 정보",
        description=(
            "지표가 어떻게 조합되는지, 현재 필터 상태가 무엇인지 확인합니다."
        ),
    )
    with st.expander("지표 정의 및 기본 제외 규칙", expanded=False):
        st.markdown(
            """
            - **GitHub 구현 지표**: merged PR 수, landed commit 수, landed commit 기준 lines added/deleted를 집계합니다.
            - **PR 흐름**: merged PR의 `created`, `first reviewed`, `merged` 타임스탬프로 cycle time과 리뷰 대기 시간을 계산합니다.
            - **배포**: GitHub deployment의 최신 status 기반 성공/실패 및 팀 단위 배포 리드 타임을 추적합니다.
            - **Jira**: 선택한 기간 내 updated된 assigned issue 수를 집계합니다.
            - **Jira WIP 버킷**: 상태명을 `todo`, `in progress`, `review`, `done`, `other`로 매핑합니다.
            - **개발자 매칭**: GitHub과 Jira는 이메일 주소로 연결합니다.
            - **기본 제외**: merge 커밋, vendored 경로, 생성 파일, 빌드 산출물, lockfile을 자동 제외합니다.
            - 이 지표는 워크로드 신호로 읽어야 하며, 생산성 점수가 아닙니다.
            """
        )

    with st.expander("현재 필터 상태", expanded=False):
        st.json(
            {
                "sqlite_path": sqlite_path,
                "start_date": filters.start_date.isoformat(),
                "end_date": filters.end_date.isoformat(),
                "granularity": filters.granularity.value,
                "developer_email": filters.developer_email,
                "search_query": search_query.strip() or None,
            }
        )


def load_dashboard_runtime_settings() -> DashboardRuntimeSettings:
    raw_team_members = parse_csv_list(os.environ.get("WORKLOAD_TEAM_MEMBERS", ""))
    try:
        team_members = parse_team_members(raw_team_members)
    except ValueError as exc:
        raise DashboardConfigError(str(exc)) from exc

    return DashboardRuntimeSettings(
        sqlite_path=(
            os.environ.get("WORKLOAD_SQLITE_PATH", "var/workload_analytics.sqlite3").strip()
            or "var/workload_analytics.sqlite3"
        ),
        team_members=team_members,
        thresholds=load_threshold_config(),
    )


def resolve_dashboard_sqlite_path(
    *,
    argv: Sequence[str],
    default_sqlite_path: str,
) -> str:
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("--sqlite-path")

    try:
        args, _ = parser.parse_known_args(list(argv[1:]))
    except argparse.ArgumentError as exc:
        raise DashboardArgumentError(
            "Invalid dashboard arguments. Use --sqlite-path <sqlite-file> when overriding the default SQLite path."
        ) from exc

    sqlite_path = (args.sqlite_path or "").strip()
    return sqlite_path or default_sqlite_path


def _render_export_buttons(st, data, csv_export, *, previous_result=None) -> None:
    export_format = st.selectbox(
        "내보내기 형식",
        options=["CSV", "JSON", "Excel", "주간 리포트 (Markdown)"],
        index=0,
    )
    if export_format == "CSV":
        st.download_button(
            label="Download CSV",
            data=csv_export.content,
            file_name=csv_export.file_name,
            mime="text/csv",
            width="stretch",
        )
    elif export_format == "JSON":
        json_export = build_filtered_metrics_json(data)
        st.download_button(
            label="Download JSON",
            data=json_export.content,
            file_name=json_export.file_name,
            mime="application/json",
            width="stretch",
        )
    elif export_format == "Excel":
        try:
            excel_export = build_filtered_metrics_excel(data)
            st.download_button(
                label="Download Excel",
                data=excel_export.content,
                file_name=excel_export.file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        except RuntimeError as exc:
            st.error(str(exc))
    elif export_format.startswith("주간"):
        report = build_weekly_report(data, previous_summary=previous_result.summary if previous_result else None)
        st.download_button(
            label="Download 주간 리포트",
            data=report.content,
            file_name=report.file_name,
            mime="text/markdown",
            width="stretch",
        )


def _render_chart(*, st, figure_builder) -> None:
    try:
        st.plotly_chart(
            figure_builder(),
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
    except RuntimeError as exc:
        st.error(str(exc))


def _render_filters(
    *,
    st,
    defaults: DashboardFilterState,
    developer_options: tuple[str, ...],
) -> tuple[DashboardFilterState, str]:
    _render_section_heading(
        st=st,
        kicker="Search",
        title="필터 및 검색",
        description=(
            "글로벌 검색은 개발자 이메일, 날짜, 지표 값으로 전체 대시보드를 좁힙니다. "
            "구조화된 필터로 먼저 범위를 설정한 뒤 검색어로 세부 필터링합니다."
        ),
    )
    search_query = st.text_input(
        "글로벌 검색",
        value="",
        placeholder="개발자, 날짜, 지표 값 검색",
    )

    date_column, granularity_column, developer_column = st.columns((1.2, 0.8, 1), gap="large")
    with date_column:
        raw_range = st.date_input(
            "날짜 범위",
            value=(defaults.start_date, defaults.end_date),
            min_value=date(2020, 1, 1),
        )
        if isinstance(raw_range, tuple) and len(raw_range) == 2:
            start_date, end_date = raw_range
        else:
            start_date = defaults.start_date
            end_date = defaults.end_date

    with granularity_column:
        granularity_value = st.selectbox(
            "집계 단위",
            options=[item.value for item in Granularity],
            index=[item.value for item in Granularity].index(defaults.granularity.value),
        )
    with developer_column:
        developer_selection = st.selectbox(
            "개발자",
            options=["All team", *developer_options],
            index=0,
        )
    st.caption(
        "필터는 로컬 SQLite 스냅샷에만 적용됩니다. 기간 버킷은 선택한 날짜 범위와 겹치면 표시됩니다."
    )

    return DashboardFilterState(
        start_date=start_date,
        end_date=end_date,
        granularity=Granularity(granularity_value),
        developer_email=normalize_developer_selection(developer_selection),
    ), search_query


def _render_summary(*, st, cards) -> None:
    row_size = 3
    for row_start in range(0, len(cards), row_size):
        row_cards = cards[row_start : row_start + row_size]
        col_count = len(row_cards)
        columns = st.columns(col_count, gap="medium")
        for column, card in zip(columns, row_cards, strict=False):
            with column:
                delta_html = ""
                if card.delta is not None:
                    direction_class = f"delta-{card.delta_direction}" if card.delta_direction else ""
                    delta_html = f'<p class="summary-delta {direction_class}">{escape(card.delta)}</p>'
                st.markdown(
                    f"""
                    <article class="summary-card">
                      <p class="summary-label">{escape(card.label)}</p>
                      <h3>{escape(card.value)}</h3>
                      {delta_html}
                      <p class="summary-detail">{escape(card.detail)}</p>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )


def _render_top_nav(st) -> None:
    st.markdown(
        """
        <nav class="genesis-nav">
          <a class="genesis-logo" href="#overview">
            <span class="genesis-logo-mark">WA</span>
            <span class="genesis-logo-copy">
              <span class="genesis-logo-title">Workload Analytics</span>
              <span class="genesis-logo-subtitle">Editorial precision for engineering signal</span>
            </span>
          </a>
          <div class="genesis-links">
            <a href="#overview">Overview</a>
            <a href="#trend">Trend</a>
            <a href="#health">Health</a>
            <a href="#alerts">Alerts</a>
            <a href="#signals">Signals</a>
            <a href="#data">Data</a>
            <a href="#reference">Reference</a>
          </div>
          <div class="genesis-user">
            <span class="genesis-chip">Local snapshot</span>
            <span class="genesis-avatar" title="Analytics workspace">WA</span>
          </div>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def _render_signal_guide_items(st) -> None:
    guide_items = (
        (
            "Active Developers",
            "필터 기간에 GitHub 또는 Jira 활동이 집계된 고유 개발자 수입니다.",
            "팀 범위와 데이터 연결 상태를 확인하는 값입니다. 숫자가 낮다고 곧바로 생산성 저하를 뜻하지는 않습니다.",
        ),
        (
            "GitHub Signals",
            "merged PR, landed commit, lines added/deleted를 분리해서 봅니다.",
            "작업량의 크기와 방향을 보는 보조 신호입니다. 라인 수는 리팩터링, 삭제, 생성 파일 제외 규칙의 영향을 받습니다.",
        ),
        (
            "PR Flow",
            "PR 생성부터 merge까지의 cycle time, 첫 리뷰까지의 대기 시간, stale PR, PR 크기 bucket을 봅니다.",
            "리뷰 병목, PR 쪼개기, 오래 열린 PR을 찾는 신호입니다. 긴 cycle time은 복잡한 변경이나 외부 대기 때문일 수도 있습니다.",
        ),
        (
            "Jira WIP",
            "assigned issue를 todo, in progress, review, done, other 상태 bucket으로 나눕니다.",
            "진행 중인 일이 한 사람이나 특정 단계에 몰리는지 확인합니다. Jira 상태 이름 매핑이 넓게 잡혀 있어 팀 워크플로에 맞춰 해석해야 합니다.",
        ),
        (
            "Delivery",
            "GitHub deployment 최신 status 기준의 성공/실패 배포 수와 성공 배포 lead time을 봅니다.",
            "팀 단위 배포 흐름을 보는 DORA-lite 신호입니다. GitHub deployments를 만들지 않는 배포 방식이면 0으로 남을 수 있습니다.",
        ),
        (
            "Provider Split",
            "현재 필터 범위에서 GitHub 활동과 Jira assigned issue가 어느 쪽에 더 많이 잡혔는지 봅니다.",
            "구현 활동과 이슈 추적 활동의 균형을 보는 참고값입니다. 개인 순위나 성과 점수로 사용하지 않습니다.",
        ),
    )
    st.markdown("---")
    st.markdown("**지표별 상세 해석**")
    for label, definition, interpretation in guide_items:
        st.markdown(
            f"**{label}**\n\n"
            f"- **무엇을 재나** — {definition}\n"
            f"- **어떻게 읽나** — {interpretation}\n"
        )


def _render_hero(
    *,
    st,
    sqlite_path: str,
    developer_count: int,
    latest_sync_status,
) -> None:
    if latest_sync_status is None:
        sync_value = "No sync snapshot available"
        sync_copy = "Run a sync to populate the dashboard and unlock trend panels."
        scope_value = "Awaiting local data"
        scope_copy = "GitHub repositories and Jira projects appear after the first successful sync."
    else:
        sync_value = latest_sync_status.completed_at.strftime("%b %d, %Y %H:%M UTC")
        sync_copy = (
            f"{latest_sync_status.unmatched_record_count} unmatched records in the latest run."
        )
        scope_value = (
            f"{latest_sync_status.github_repository_count} repos / "
            f"{latest_sync_status.jira_project_count} Jira projects"
        )
        scope_copy = (
            f"{latest_sync_status.matched_developer_count} matched developers across the synced window."
        )

    st.markdown(
        f"""
        <section id="overview" class="hero-shell">
          <div>
            <p class="hero-kicker">Engineering Signal Board</p>
            <h1>Team workload analytics</h1>
            <p class="hero-copy">
              엔지니어링 워크로드 신호를 한 곳에서. 순위가 아닌 운영 맥락으로 읽습니다.
            </p>
            <div class="hero-actions">
              <span class="hero-note">GitHub + Jira &middot; 로컬 실행 &middot; <strong>{developer_count}</strong>명 추적 중</span>
            </div>
          </div>
          <div class="hero-metrics">
            <article class="hero-panel">
              <p class="hero-panel-label">Last Sync</p>
              <p class="hero-panel-value">{escape(sync_value)}</p>
              <p class="hero-panel-copy">{escape(sync_copy)}</p>
            </article>
            <article class="hero-panel">
              <p class="hero-panel-label">Scope</p>
              <p class="hero-panel-value">{escape(scope_value)}</p>
              <p class="hero-panel-copy">{escape(scope_copy)}</p>
            </article>
            <article class="hero-panel">
              <p class="hero-panel-label">Snapshot</p>
              <p class="hero-panel-value">{developer_count} developers</p>
              <p class="hero-panel-copy">Local SQLite</p>
              <code>{escape(sqlite_path)}</code>
            </article>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_section_heading(
    *,
    st,
    kicker: str,
    title: str,
    description: str,
    anchor: str | None = None,
) -> None:
    section_anchor = anchor or kicker.lower()
    kicker_class = f"kicker-{escape(section_anchor)}"
    st.markdown(
        f"""
        <section id="{escape(section_anchor)}" class="section-heading">
          <p class="section-kicker {kicker_class}">{escape(kicker)}</p>
          <h2>{escape(title)}</h2>
          <p>{escape(description)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_active_search(*, st, search_query: str, result_count: int) -> None:
    row_label = "row" if result_count == 1 else "rows"
    st.markdown(
        f"""
        <div class="active-search">
          <div class="active-search-copy">
            <span class="search-shortcut">Search</span>
            <span><strong>{escape(search_query.strip())}</strong> is active across the dashboard.</span>
          </div>
          <div class="active-search-copy">{result_count} metric {row_label} matched</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metrics_rows(metrics) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in metrics:
        row = asdict(item)
        row["granularity"] = item.granularity.value
        row["period_start"] = item.period_start.isoformat()
        row["period_end"] = item.period_end.isoformat()
        rows.append(row)
    return rows


def _inject_styles(st) -> None:
    st.markdown(DASHBOARD_STYLES, unsafe_allow_html=True)


def _streamlit():
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError("streamlit is required to run the dashboard app.") from exc
    return st


if __name__ == "__main__":
    main()
