# Spec: Commit Heatmap Day Sums

## Assumptions
1. The requested change applies to the existing Streamlit/Plotly commit heatmap.
2. "각 요일 별 sum 데이터" means the total commit count per weekday within the current dashboard date range and optional developer filter.
3. Commit heatmap bucketing remains KST-based and still uses `normalized_github_commits`.
4. The change is display/query-layer only; no SQLite schema migration or new dependency is needed.

## Objective
Add weekday total commit counts to the commit time heatmap so users can read both the hourly distribution and each weekday's total commit volume in the same chart.

## Tech Stack
- Python dataclasses and sqlite3 query layer
- Streamlit dashboard
- Plotly heatmap chart
- unittest

## Commands
- Run targeted tests: `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_new_dashboard_features.CommitHeatmapTest`
- Run all tests: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- Run syntax check: `PYTHONPATH=src .venv/bin/python -m compileall src tests`
- Run dashboard: `PYTHONPATH=src .venv/bin/streamlit run src/workload_analytics/dashboard/app.py`

## Project Structure
- `src/workload_analytics/dashboard/queries.py` -> commit heatmap cell model and SQL aggregation
- `src/workload_analytics/dashboard/charts.py` -> heatmap rendering and labels
- `tests/unit/test_new_dashboard_features.py` -> query and chart behavior tests
- `docs/specs/` -> feature specs

## Code Style
Keep the heatmap data explicit and additive so existing callers can keep constructing cells without passing the new value.

```python
@dataclass(frozen=True, slots=True)
class CommitHeatmapCell:
    day_of_week: int
    hour: int
    commit_count: int
    day_total: int = 0
```

## Testing Strategy
- Add unit coverage for `load_commit_heatmap` to verify each returned cell carries the correct KST weekday total.
- Add chart coverage for `build_commit_heatmap_figure` to verify weekday totals are visible in row labels and hover text.
- Keep the empty heatmap behavior unchanged.

## Boundaries
- Always:
  - Preserve KST bucketing and developer/date filters.
  - Keep the existing 7x24 heatmap shape.
  - Treat the sum as a commit count total, not a productivity score.
- Ask first:
  - Changing the heatmap to a different timezone.
  - Adding a storage migration or changing normalized commit persistence.
  - Adding new charting dependencies.
- Never:
  - Count commits outside the selected date range or developer filter.
  - Change the underlying commit exclusion rules.
  - Remove existing heatmap empty-state behavior.

## Success Criteria
- `load_commit_heatmap` returns `day_total` for every non-empty day/hour cell.
- `day_total` equals the sum of `commit_count` across all hours for that weekday after KST conversion.
- The heatmap visibly includes weekday totals in its y-axis labels.
- Heatmap hover text includes both the hour count and weekday total.
- Existing commit heatmap empty-state behavior remains unchanged.

## Open Questions
- None. If a separate summary table is desired instead of row labels and hover text, that should be a follow-up display change.
