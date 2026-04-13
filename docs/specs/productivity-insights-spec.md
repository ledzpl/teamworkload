# Spec: Productivity Insights Expansion

## Assumptions
1. The dashboard remains a team workload and delivery signal tool, not an individual performance ranking system.
2. PR flow metrics apply to merged pull requests inside the selected sync window.
3. DORA-lite delivery metrics use GitHub deployments as the deployment source for this iteration.
4. A successful deployment is the latest deployment status with state `success`; failed deployments use latest status `failure` or `error`.
5. Deployment lead time is measured from the deployed commit timestamp to the successful deployment status timestamp when both are available.
6. Because the GitHub deployments endpoint has no created-at range filter, the implementation bounds status lookup by scanning deployments created up to 7 days before the selected delivery window, then filters by latest deployment status time.
7. Workload balance uses Jira issue status names from the assigned-issue sync and maps them into coarse WIP buckets.
8. No new external services or dependencies are added.

## Objective
Add three production-oriented views on top of the existing commit, PR, and Jira assigned-issue counts:

- PR Flow: show how quickly PRs move from creation to merge and first review.
- DORA-lite Delivery: show team-level successful and failed deployments plus deployment lead time from GitHub deployments.
- Workload Balance: show assigned Jira issue load by status bucket so WIP concentration is visible.

## Tech Stack
- Python standard library HTTP client path already used by `GithubClient` and `JiraClient`
- SQLite via `sqlite3`
- Streamlit and Plotly dashboard
- unittest

## Commands
- Test: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- Syntax check: `.venv/bin/python -m compileall src tests`
- Sync: `PYTHONPATH=src .venv/bin/python -m workload_analytics.jobs.sync_metrics --start-date 2026-01-01 --end-date 2026-03-31 --granularity week`
- Dashboard: `PYTHONPATH=src .venv/bin/streamlit run src/workload_analytics/dashboard/app.py`

## Project Structure
- `src/workload_analytics/clients/` -> GitHub PR review/deployment payload fetch and Jira status parsing
- `src/workload_analytics/models/` -> Added flow, delivery, and WIP fields
- `src/workload_analytics/pipelines/` -> Normalization and aggregation rules
- `src/workload_analytics/storage/` -> SQLite schema migrations and persistence
- `src/workload_analytics/dashboard/` -> Queries, summary cards, charts, CSV/JSON/Excel exports, and Markdown report generation
- `tests/unit/` -> Pure aggregation and dashboard query tests
- `tests/integration/` -> API client, storage, and sync pipeline coverage

## Code Style
Metric fields stay explicit and additive so old SQLite snapshots can migrate forward.

```python
@dataclass(frozen=True, slots=True)
class TeamPeriodDeliveryMetrics:
    granularity: Granularity
    period_start: date
    period_end: date
    successful_deployments: int = 0
    failed_deployments: int = 0
    deployment_lead_time_hours: float = 0.0
    deployments_with_lead_time: int = 0
```

## Testing Strategy
- Add failing tests before each slice:
  - GitHub client parses PR created date, first review date, and deployments.
  - GitHub normalization computes PR flow metrics.
  - Jira normalization preserves status bucket.
  - Storage persists and migrates new metric fields.
  - Sync pipeline aggregates PR flow, WIP, and team delivery metrics.
  - Dashboard queries expose the new fields.
- Keep existing tests green after each slice.

## Boundaries
- Always:
  - Keep PR flow and delivery metrics separate from existing code volume metrics.
  - Treat GitHub/Jira payloads as untrusted and validate expected field shapes.
  - Keep deployment metrics team-scoped rather than assigning deployments to individual developers.
  - Keep missing deployment lead-time inputs visible by counting deployments with lead time separately.
  - Keep GitHub deployment status lookup bounded so old deployments do not trigger full-history status fetches on every sync.
- Ask first:
  - Switching deployment source from GitHub deployments to releases, tags, or Actions.
  - Introducing incident management data for full DORA MTTR/change failure rate.
  - Adding ranking, scoring, or HR-style labels.
- Never:
  - Treat PR count, line count, or deployment count as a standalone productivity score.
  - Commit provider credentials or raw secrets.
  - Drop existing tests to make the suite pass.

## Success Criteria
- PR flow metrics are visible per developer and period:
  - total PR cycle time hours
  - PRs with first-review timing
  - total first-review wait hours
  - stale PR count
  - PR size buckets
- GitHub deployments are fetched, normalized, persisted, and displayed as team-level DORA-lite metrics:
  - successful deployment count
  - failed deployment count
  - average deployment lead time when commit timestamp is available
- GitHub deployment candidate scanning is bounded by a 7-day created-at lookback before the selected delivery window.
- Jira assigned issues are grouped into WIP status buckets:
  - todo
  - in progress
  - review
  - done
  - other
- CSV export includes the new per-developer PR flow and Jira WIP fields.
- Existing setup and sync commands keep working.

## Confirmed Decisions
- Deployment source is GitHub deployments. If the team uses releases/tags/Actions instead, that should become a follow-up spec.

## Open Questions
- None at the current product scope.
