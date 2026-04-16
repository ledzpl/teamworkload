from __future__ import annotations

from datetime import date

from workload_analytics.dashboard.types import TrendPoint


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
        "margin": {
            "l": left_margin,
            "r": right_margin,
            "t": top_margin,
            "b": bottom_margin,
        },
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
    r = int(hex_color[:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _plotly_go():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RuntimeError("plotly is required to render dashboard charts.") from exc
    return go
