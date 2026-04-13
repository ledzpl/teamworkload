from __future__ import annotations

from collections import defaultdict
from datetime import date

from workload_analytics.dashboard.queries import (
    CommitHeatmapCell,
    DeliveryTrendPoint,
    DeveloperComparisonRow,
    DeveloperFocusRow,
    ProviderSplit,
    TrendPoint,
)
from workload_analytics.dashboard.summary import TrendDelta


_DEFAULT_MA_WINDOW = 4


PALETTE = {
    "ink": "#1d1d1f",
    "slate": "#86868b",
    "panel": "#ffffff",
    "panel_edge": "rgba(0,0,0,0.06)",
    "grid": "#f2f2f7",
    "indigo": "#5856D6",
    "warning": "#ff9f0a",
    "success": "#34c759",
    "danger": "#ff3b30",
    "cyan": "#32ade6",
    "review": "#af52de",
    "muted_fill": "#d1d1d6",
}


def build_team_trend_figure(
    trend_points: tuple[TrendPoint, ...],
):
    go = _plotly_go()
    figure = go.Figure()

    if not trend_points:
        return _empty_figure(
            title="Team workload trend",
            description="Run a sync and broaden the date range to see period trends.",
        )

    labels = [
        _format_period_label(item.period_start, item.period_end)
        for item in trend_points
    ]
    period_notes = [
        "No synced activity in this period."
        if _is_zero_period(item)
        else "Synced workload activity captured."
        for item in trend_points
    ]
    figure.add_trace(
        go.Bar(
            name="Lines Added",
            x=labels,
            y=[item.github_lines_added for item in trend_points],
            marker_color=PALETTE["warning"],
            opacity=0.82,
            customdata=period_notes,
            hovertemplate="%{x}<br>Lines added: %{y}<br>%{customdata}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Merged PRs",
            x=labels,
            y=[item.github_prs_merged for item in trend_points],
            mode="lines+markers",
            marker={"size": 6, "color": PALETTE["indigo"]},
            line={"width": 2.5, "color": PALETTE["indigo"]},
            yaxis="y2",
            customdata=period_notes,
            hovertemplate="%{x}<br>Merged PRs: %{y}<br>%{customdata}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Assigned Issues",
            x=labels,
            y=[item.jira_issues_assigned for item in trend_points],
            mode="lines+markers",
            marker={"size": 6, "color": PALETTE["success"]},
            line={"width": 2.5, "color": PALETTE["success"]},
            yaxis="y2",
            customdata=period_notes,
            hovertemplate="%{x}<br>Assigned issues: %{y}<br>%{customdata}<extra></extra>",
        )
    )
    lines_values = [item.github_lines_added for item in trend_points]
    ma_values = _moving_average(lines_values)
    figure.add_trace(
        go.Scatter(
            name=f"Lines Added ({_DEFAULT_MA_WINDOW}기간 이동평균)",
            x=labels,
            y=ma_values,
            mode="lines",
            line={"width": 2, "color": _hex_to_rgba(PALETTE["warning"], 0.55), "dash": "dash"},
            hovertemplate="%{x}<br>MA: %{y:,.0f}<extra></extra>",
        )
    )

    figure.update_layout(
        **_base_layout(
            title="Team workload trend",
            top_margin=98,
            bottom_margin=44,
        ),
        barmode="group",
        yaxis={"title": "Lines changed", "rangemode": "tozero"},
        yaxis2={
            "title": "Count",
            "overlaying": "y",
            "side": "right",
            "rangemode": "tozero",
        },
        xaxis={"tickfont": {"size": 11}, "automargin": True},
    )
    return _apply_theme(figure)


def build_developer_comparison_figure(
    comparison_rows: tuple[DeveloperComparisonRow, ...],
):
    go = _plotly_go()
    figure = go.Figure()

    if not comparison_rows:
        return _empty_figure(
            title="Developer comparison",
            description="No developer metrics match the current filter.",
        )

    full_labels = [row.developer_email for row in comparison_rows]
    labels = [_truncate_axis_label(label, max_length=28) for label in full_labels]
    figure.add_trace(
        go.Bar(
            name="Merged PRs",
            y=labels,
            x=[row.github_prs_merged for row in comparison_rows],
            orientation="h",
            marker_color=PALETTE["indigo"],
            customdata=full_labels,
            hovertemplate="%{customdata}<br>Merged PRs: %{x}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Landed Commits",
            y=labels,
            x=[row.github_commits_landed for row in comparison_rows],
            orientation="h",
            marker_color=PALETTE["warning"],
            customdata=full_labels,
            hovertemplate="%{customdata}<br>Landed commits: %{x}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Assigned Issues",
            y=labels,
            x=[row.jira_issues_assigned for row in comparison_rows],
            orientation="h",
            marker_color=PALETTE["success"],
            customdata=full_labels,
            hovertemplate="%{customdata}<br>Assigned issues: %{x}<extra></extra>",
        )
    )
    figure.update_layout(
        **_base_layout(
            title="Per-developer comparison",
            left_margin=_comparison_margin(full_labels),
            top_margin=98,
            bottom_margin=26,
        ),
        barmode="group",
        xaxis={"title": "Count", "rangemode": "tozero"},
        yaxis={"automargin": True},
    )
    return _apply_theme(figure)


def build_pr_flow_figure(trend_points: tuple[TrendPoint, ...]):
    go = _plotly_go()
    figure = go.Figure()

    if not trend_points:
        return _empty_figure(
            title="PR flow",
            description="No PR flow metrics match the current filter.",
        )

    labels = [
        _format_period_label(item.period_start, item.period_end)
        for item in trend_points
    ]
    figure.add_trace(
        go.Bar(
            name="Stale PRs",
            x=labels,
            y=[item.github_prs_stale for item in trend_points],
            marker_color=PALETTE["danger"],
            opacity=0.82,
            hovertemplate="%{x}<br>Stale PRs: %{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Avg Cycle Hours",
            x=labels,
            y=[
                _average(item.github_pr_cycle_time_hours, item.github_prs_with_cycle_time)
                for item in trend_points
            ],
            mode="lines+markers",
            marker={"size": 6, "color": PALETTE["indigo"]},
            line={"width": 2.5, "color": PALETTE["indigo"]},
            yaxis="y2",
            hovertemplate="%{x}<br>Avg cycle: %{y:.1f}h<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Avg Review Wait Hours",
            x=labels,
            y=[
                _average(
                    item.github_pr_review_wait_hours,
                    item.github_prs_with_review_wait,
                )
                for item in trend_points
            ],
            mode="lines+markers",
            marker={"size": 6, "color": PALETTE["cyan"]},
            line={"width": 2.5, "color": PALETTE["cyan"]},
            yaxis="y2",
            hovertemplate="%{x}<br>Avg review wait: %{y:.1f}h<extra></extra>",
        )
    )
    cycle_values = [
        _average(item.github_pr_cycle_time_hours, item.github_prs_with_cycle_time)
        for item in trend_points
    ]
    ma_cycle = _moving_average(cycle_values)
    figure.add_trace(
        go.Scatter(
            name=f"Cycle ({_DEFAULT_MA_WINDOW}기간 이동평균)",
            x=labels,
            y=ma_cycle,
            mode="lines",
            line={"width": 2, "color": _hex_to_rgba(PALETTE["indigo"], 0.55), "dash": "dash"},
            yaxis="y2",
            hovertemplate="%{x}<br>MA cycle: %{y:.1f}h<extra></extra>",
        )
    )

    figure.update_layout(
        **_base_layout(
            title="PR flow",
            top_margin=98,
            bottom_margin=44,
        ),
        yaxis={"title": "PR count", "rangemode": "tozero"},
        yaxis2={
            "title": "Hours",
            "overlaying": "y",
            "side": "right",
            "rangemode": "tozero",
        },
        xaxis={"tickfont": {"size": 11}, "automargin": True},
    )
    return _apply_theme(figure)


def build_workload_balance_figure(
    comparison_rows: tuple[DeveloperComparisonRow, ...],
):
    go = _plotly_go()
    figure = go.Figure()

    if not comparison_rows:
        return _empty_figure(
            title="Jira WIP balance",
            description="No Jira WIP metrics match the current filter.",
        )

    full_labels = [row.developer_email for row in comparison_rows]
    labels = [_truncate_axis_label(label, max_length=28) for label in full_labels]
    buckets = (
        ("Todo", "jira_todo_issues", "muted_fill"),
        ("In Progress", "jira_in_progress_issues", "warning"),
        ("Review", "jira_review_issues", "review"),
        ("Done", "jira_done_issues", "success"),
        ("Other", "jira_other_issues", "slate"),
    )
    for name, attribute, color_key in buckets:
        figure.add_trace(
            go.Bar(
                name=name,
                y=labels,
                x=[getattr(row, attribute) for row in comparison_rows],
                orientation="h",
                marker_color=PALETTE[color_key],
                customdata=full_labels,
                hovertemplate=f"%{{customdata}}<br>{name}: %{{x}}<extra></extra>",
            )
        )
    figure.update_layout(
        **_base_layout(
            title="Jira WIP balance",
            left_margin=_comparison_margin(full_labels),
            top_margin=98,
            bottom_margin=26,
        ),
        barmode="stack",
        xaxis={"title": "Assigned issues", "rangemode": "tozero"},
        yaxis={"automargin": True},
    )
    return _apply_theme(figure)


def build_delivery_figure(delivery_trend_points: tuple[DeliveryTrendPoint, ...]):
    go = _plotly_go()
    figure = go.Figure()

    if not delivery_trend_points:
        return _empty_figure(
            title="DORA-lite delivery",
            description="No deployment metrics match the current filter.",
        )

    labels = [
        _format_period_label(item.period_start, item.period_end)
        for item in delivery_trend_points
    ]
    figure.add_trace(
        go.Bar(
            name="Successful Deployments",
            x=labels,
            y=[item.successful_deployments for item in delivery_trend_points],
            marker_color=PALETTE["success"],
            hovertemplate="%{x}<br>Successful deployments: %{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Failed Deployments",
            x=labels,
            y=[item.failed_deployments for item in delivery_trend_points],
            marker_color=PALETTE["danger"],
            hovertemplate="%{x}<br>Failed deployments: %{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Avg Lead Hours",
            x=labels,
            y=[
                _average(
                    item.deployment_lead_time_hours,
                    item.deployments_with_lead_time,
                )
                for item in delivery_trend_points
            ],
            mode="lines+markers",
            marker={"size": 6, "color": PALETTE["cyan"]},
            line={"width": 2.5, "color": PALETTE["cyan"]},
            yaxis="y2",
            hovertemplate="%{x}<br>Avg lead time: %{y:.1f}h<extra></extra>",
        )
    )
    figure.update_layout(
        **_base_layout(
            title="DORA-lite delivery",
            top_margin=98,
            bottom_margin=44,
        ),
        barmode="group",
        yaxis={"title": "Deployments", "rangemode": "tozero"},
        yaxis2={
            "title": "Hours",
            "overlaying": "y",
            "side": "right",
            "rangemode": "tozero",
        },
        xaxis={"tickfont": {"size": 11}, "automargin": True},
    )
    return _apply_theme(figure)


def build_provider_split_figure(provider_split: ProviderSplit):
    go = _plotly_go()
    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=["Merged PRs", "Landed Commits", "Assigned Issues"],
            y=[
                provider_split.github_prs_merged,
                provider_split.github_commits_landed,
                provider_split.jira_issues_assigned,
            ],
            marker_color=[PALETTE["indigo"], PALETTE["warning"], PALETTE["success"]],
            text=[
                str(provider_split.github_prs_merged),
                str(provider_split.github_commits_landed),
                str(provider_split.jira_issues_assigned),
            ],
            textposition="outside",
            cliponaxis=False,
        )
    )
    figure.update_layout(
        **_base_layout(
            title="GitHub and Jira split",
            top_margin=116,
            bottom_margin=28,
        ),
        yaxis={"title": "Count", "rangemode": "tozero"},
        xaxis={"tickfont": {"size": 12}},
        annotations=[
            {
                "text": f"Scope: {provider_split.scope_label}",
                "xref": "paper",
                "yref": "paper",
                "x": 0.0,
                "y": 1.18,
                "showarrow": False,
                "font": {"color": PALETTE["slate"], "size": 12},
            },
            {
                "text": (
                    f"Lines added: {provider_split.github_lines_added} | "
                    f"Lines deleted: {provider_split.github_lines_deleted}"
                ),
                "xref": "paper",
                "yref": "paper",
                "x": 0.0,
                "y": 1.1,
                "showarrow": False,
                "font": {"color": PALETTE["slate"], "size": 12},
            },
        ],
    )
    return _apply_theme(figure)


def build_review_efficiency_figure(
    comparison_rows: tuple[DeveloperComparisonRow, ...],
):
    go = _plotly_go()
    figure = go.Figure()

    rows_with_data = [
        r for r in comparison_rows if r.github_prs_with_review_wait > 0
    ]
    if not rows_with_data:
        return _empty_figure(
            title="Per-developer review wait",
            description="No review wait data available for the current filter.",
        )

    full_labels = [r.developer_email for r in rows_with_data]
    labels = [_truncate_axis_label(label, max_length=28) for label in full_labels]
    avg_waits = [
        r.github_pr_review_wait_hours / r.github_prs_with_review_wait
        for r in rows_with_data
    ]
    team_avg = sum(avg_waits) / len(avg_waits) if avg_waits else 0

    colors = [
        PALETTE["danger"] if w > team_avg * 2
        else PALETTE["warning"] if w > team_avg
        else PALETTE["success"]
        for w in avg_waits
    ]

    figure.add_trace(
        go.Bar(
            y=labels,
            x=avg_waits,
            orientation="h",
            marker_color=colors,
            customdata=list(zip(full_labels, [r.github_prs_with_review_wait for r in rows_with_data])),
            hovertemplate="%{customdata[0]}<br>Avg wait: %{x:.1f}h<br>PRs: %{customdata[1]}<extra></extra>",
        )
    )

    if team_avg > 0:
        figure.add_vline(
            x=team_avg,
            line_dash="dash",
            line_color=PALETTE["slate"],
            annotation_text=f"Team avg {team_avg:.1f}h",
            annotation_position="top",
        )

    figure.update_layout(
        **_base_layout(
            title="Per-developer review wait",
            left_margin=_comparison_margin(full_labels),
            top_margin=98,
            bottom_margin=26,
        ),
        xaxis={"title": "Avg review wait (hours)", "rangemode": "tozero"},
        yaxis={"automargin": True},
        showlegend=False,
    )
    return _apply_theme(figure)


def build_jira_throughput_figure(trend_points: tuple[TrendPoint, ...]):
    go = _plotly_go()
    figure = go.Figure()

    if not trend_points:
        return _empty_figure(
            title="Jira throughput",
            description="No Jira data available for the current filter.",
        )

    labels = [
        _format_period_label(item.period_start, item.period_end)
        for item in trend_points
    ]
    assigned = [item.jira_issues_assigned for item in trend_points]
    done = [item.jira_done_issues for item in trend_points]
    open_issues = [a - d for a, d in zip(assigned, done)]

    figure.add_trace(
        go.Bar(
            name="Done",
            x=labels,
            y=done,
            marker_color=PALETTE["success"],
            hovertemplate="%{x}<br>Done: %{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Open (assigned - done)",
            x=labels,
            y=[max(0, o) for o in open_issues],
            marker_color=PALETTE["warning"],
            hovertemplate="%{x}<br>Open: %{y}<extra></extra>",
        )
    )

    done_rates = [
        (d / a * 100) if a > 0 else 0
        for a, d in zip(assigned, done)
    ]
    figure.add_trace(
        go.Scatter(
            name="Done Rate %",
            x=labels,
            y=done_rates,
            mode="lines+markers",
            marker={"size": 6, "color": PALETTE["indigo"]},
            line={"width": 2.5, "color": PALETTE["indigo"]},
            yaxis="y2",
            hovertemplate="%{x}<br>Done rate: %{y:.0f}%<extra></extra>",
        )
    )

    ma_done_rates = _moving_average(done_rates)
    figure.add_trace(
        go.Scatter(
            name=f"Done Rate ({_DEFAULT_MA_WINDOW}기간 이동평균)",
            x=labels,
            y=ma_done_rates,
            mode="lines",
            line={"width": 2, "color": _hex_to_rgba(PALETTE["indigo"], 0.55), "dash": "dash"},
            yaxis="y2",
            hovertemplate="%{x}<br>MA done rate: %{y:.0f}%<extra></extra>",
        )
    )

    figure.update_layout(
        **_base_layout(
            title="Jira throughput",
            top_margin=98,
            bottom_margin=44,
        ),
        barmode="stack",
        yaxis={"title": "Issues", "rangemode": "tozero"},
        yaxis2={
            "title": "Done rate %",
            "overlaying": "y",
            "side": "right",
            "rangemode": "tozero",
            "range": [0, 110],
        },
        xaxis={"tickfont": {"size": 11}, "automargin": True},
    )
    return _apply_theme(figure)


def build_trend_sparkline_figure(delta: TrendDelta):
    """Build a compact sparkline chart for a single trend metric."""
    go = _plotly_go()
    figure = go.Figure()

    if not delta.values:
        return _empty_figure(
            title=delta.label,
            description="No trend data available.",
        )

    is_stale = "Stale" in delta.label
    if delta.direction == "flat":
        color = PALETTE["slate"]
    elif (delta.direction == "up") ^ is_stale:
        color = PALETTE["success"]
    else:
        color = PALETTE["danger"]

    labels = list(delta.period_labels)

    fill_color = _hex_to_rgba(color, 0.1)

    figure.add_trace(
        go.Scatter(
            x=labels,
            y=list(delta.values),
            mode="lines+markers",
            line={"width": 2.5, "color": color},
            marker={"size": 5.5, "color": color},
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="%{x}<br>%{y}<extra></extra>",
        )
    )

    if delta.change_pct is not None:
        sign = "+" if delta.change_pct > 0 else ""
        subtitle = f"{sign}{delta.change_pct:.0f}%"
    elif delta.direction == "up":
        subtitle = "NEW"
    else:
        subtitle = "변동 없음"

    figure.update_layout(
        title={
            "text": f"{delta.label}<br><span style='font-size:14px;font-weight:600;color:{PALETTE['slate']}'>{subtitle}</span>",
            "x": 0.0,
            "xanchor": "left",
            "font": {"size": 14},
        },
        margin={"l": 10, "r": 10, "t": 60, "b": 28},
        paper_bgcolor=PALETTE["panel"],
        plot_bgcolor=PALETTE["panel"],
        height=180,
        showlegend=False,
        xaxis={
            "showticklabels": True,
            "tickfont": {"size": 9.5, "color": PALETTE["slate"]},
            "showgrid": False,
            "zeroline": False,
            "nticks": 6,
        },
        yaxis={
            "showticklabels": False,
            "showgrid": False,
            "zeroline": False,
            "rangemode": "tozero",
        },
    )
    return _apply_theme(figure)


_DAY_LABELS_KO = ("일", "월", "화", "수", "목", "금", "토")


def build_commit_heatmap_figure(
    cells: tuple[CommitHeatmapCell, ...],
):
    go = _plotly_go()
    figure = go.Figure()

    if not cells:
        return _empty_figure(
            title="커밋 시간대 히트맵 (KST)",
            description="커밋 데이터가 없습니다. 동기화 후 다시 확인하세요.",
        )

    # Build 7×24 matrix (rows=days, cols=hours)
    # Reorder to Mon..Sun (strftime %w: 0=Sun)
    reorder = [1, 2, 3, 4, 5, 6, 0]  # Mon=1 .. Sun=0
    day_names = [_DAY_LABELS_KO[d] for d in reorder]

    matrix = [[0] * 24 for _ in range(7)]
    for cell in cells:
        row_idx = reorder.index(cell.day_of_week)
        matrix[row_idx][cell.hour] = cell.commit_count

    day_totals = [sum(row) for row in matrix]
    day_labels = [
        f"{day_name} 합계 {day_total}"
        for day_name, day_total in zip(day_names, day_totals, strict=True)
    ]

    hover_text = [
        [
            f"{day_names[r]} {c}시: {matrix[r][c]}건<br>요일 합계: {day_totals[r]}건"
            for c in range(24)
        ]
        for r in range(7)
    ]

    figure.add_trace(
        go.Heatmap(
            z=matrix,
            x=list(range(24)),
            y=day_labels,
            colorscale=[
                [0.0, PALETTE["grid"]],
                [0.5, PALETTE["indigo"]],
                [1.0, "#3634a3"],
            ],
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
            colorbar={"title": "건수", "thickness": 14, "len": 0.6, "tickfont": {"size": 10}},
        )
    )

    figure.update_layout(
        **_base_layout(
            title="커밋 시간대 히트맵 (KST)",
            top_margin=80,
            bottom_margin=36,
        ),
        xaxis={
            "title": "시간 (KST, 0–23)",
            "dtick": 1,
            "tickfont": {"size": 10},
        },
        yaxis={
            "autorange": "reversed",
            "tickfont": {"size": 11},
        },
        showlegend=False,
    )
    return _apply_theme(figure)


def build_developer_focus_figure(
    rows: tuple[DeveloperFocusRow, ...],
):
    go = _plotly_go()
    figure = go.Figure()

    if not rows:
        return _empty_figure(
            title="개발자 포커스 타임",
            description="활동 데이터가 없습니다. 동기화 후 다시 확인하세요.",
        )

    # Aggregate: average active_repo_count per developer
    totals: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        totals[row.developer_email].append(row.active_repo_count)

    developers = sorted(totals.keys())
    avg_repos = [sum(totals[d]) / len(totals[d]) for d in developers]
    max_repos = [max(totals[d]) for d in developers]

    full_labels = developers
    labels = [_truncate_axis_label(d, max_length=28) for d in developers]

    figure.add_trace(
        go.Bar(
            name="평균 활성 repo 수",
            y=labels,
            x=avg_repos,
            orientation="h",
            marker_color=PALETTE["indigo"],
            customdata=list(zip(full_labels, max_repos)),
            hovertemplate="%{customdata[0]}<br>평균: %{x:.1f} repos<br>최대: %{customdata[1]}<extra></extra>",
        )
    )

    team_avg = sum(avg_repos) / len(avg_repos) if avg_repos else 0
    if team_avg > 0:
        figure.add_vline(
            x=team_avg,
            line_dash="dash",
            line_color=PALETTE["slate"],
            annotation_text=f"팀 평균 {team_avg:.1f}",
            annotation_position="top",
        )

    figure.update_layout(
        **_base_layout(
            title="개발자 포커스 타임",
            left_margin=_comparison_margin(full_labels),
            top_margin=98,
            bottom_margin=26,
        ),
        xaxis={"title": "평균 활성 repo 수", "rangemode": "tozero"},
        yaxis={"automargin": True},
        showlegend=False,
    )
    return _apply_theme(figure)


def _moving_average(
    values: list[float],
    window: int = _DEFAULT_MA_WINDOW,
) -> list[float | None]:
    """Return a simple moving average series; positions before *window* are ``None``."""
    if window < 1:
        return [None] * len(values)
    result: list[float | None] = []
    for idx in range(len(values)):
        if idx < window - 1:
            result.append(None)
        else:
            result.append(sum(values[idx - window + 1 : idx + 1]) / window)
    return result


def _empty_figure(*, title: str, description: str):
    go = _plotly_go()
    figure = go.Figure()
    figure.update_layout(
        **_base_layout(title=title, top_margin=92, bottom_margin=28),
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": "&#8212;",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.58,
                "showarrow": False,
                "font": {"size": 32, "color": PALETTE["grid"]},
            },
            {
                "text": description,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.38,
                "showarrow": False,
                "font": {"size": 13, "color": PALETTE["slate"]},
            },
        ],
    )
    return _apply_theme(figure)


def _apply_theme(figure):
    figure.update_layout(
        font={
            "family": "DM Sans, -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
            "color": PALETTE["ink"],
            "size": 12.5,
        },
        title={
            "font": {
                "size": 17,
                "color": PALETTE["ink"],
                "family": "General Sans, DM Sans, -apple-system, system-ui, sans-serif",
            }
        },
    )
    figure.update_xaxes(
        gridcolor=PALETTE["grid"],
        linecolor="rgba(0,0,0,0)",
        tickfont={"color": PALETTE["slate"], "size": 11},
        title_font={"color": PALETTE["slate"], "size": 11.5},
        zerolinecolor=PALETTE["grid"],
        automargin=True,
    )
    figure.update_yaxes(
        gridcolor=PALETTE["grid"],
        linecolor="rgba(0,0,0,0)",
        tickfont={"color": PALETTE["slate"], "size": 11},
        title_font={"color": PALETTE["slate"], "size": 11.5},
        zerolinecolor=PALETTE["grid"],
        automargin=True,
    )
    return figure


def _base_layout(
    *,
    title: str,
    top_margin: int,
    bottom_margin: int,
    left_margin: int = 20,
    right_margin: int = 20,
) -> dict[str, object]:
    return {
        "title": {"text": title, "x": 0.0, "xanchor": "left"},
        "margin": {"l": left_margin, "r": right_margin, "t": top_margin, "b": bottom_margin},
        "paper_bgcolor": PALETTE["panel"],
        "plot_bgcolor": PALETTE["panel"],
        "bargap": 0.25,
        "bargroupgap": 0.12,
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.04,
            "xanchor": "left",
            "x": 0.0,
            "bgcolor": "rgba(255,255,255,0)",
            "borderwidth": 0,
            "font": {"size": 12, "color": PALETTE["slate"]},
            "itemsizing": "constant",
            "tracegroupgap": 8,
        },
        "hoverlabel": {
            "bgcolor": "rgba(255,255,255,0.95)",
            "bordercolor": "rgba(0,0,0,0.08)",
            "font": {"color": PALETTE["ink"], "size": 13},
        },
    }


def _format_period_label(period_start: date, period_end: date) -> str:
    if period_start == period_end:
        return period_start.strftime("%b %d")
    return f"{period_start.strftime('%b %d')}<br>{period_end.strftime('%b %d')}"


def _truncate_axis_label(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _comparison_margin(labels: list[str]) -> int:
    if not labels:
        return 20
    longest = max(len(label) for label in labels)
    return min(280, max(172, 92 + (longest * 4)))


def _average(total: float, count: int) -> float:
    if count == 0:
        return 0.0
    return total / count


def _is_zero_period(point: TrendPoint) -> bool:
    return (
        point.github_prs_merged == 0
        and point.github_commits_landed == 0
        and point.github_lines_added == 0
        and point.github_lines_deleted == 0
        and point.jira_issues_assigned == 0
        and point.github_prs_stale == 0
        and point.jira_todo_issues == 0
        and point.jira_in_progress_issues == 0
        and point.jira_review_issues == 0
        and point.jira_done_issues == 0
        and point.jira_other_issues == 0
    )


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _plotly_go():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RuntimeError("plotly is required to render dashboard charts.") from exc
    return go
