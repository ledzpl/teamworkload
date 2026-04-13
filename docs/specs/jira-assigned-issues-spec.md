# Spec: Jira Assigned Issue Metric

## Assumptions
1. The requested change only affects the Jira-side metric. GitHub pull request and commit metrics stay unchanged.
2. The dashboard must keep supporting the existing date window and day/week/month aggregations.
3. "Assigned issues" means issues whose current Jira assignee is a synced team member, not issues that merely passed through an assignee in the past.
4. Because the current integration does not fetch Jira changelogs, the safest v1 implementation is to treat "assigned issue activity" as issues with a non-empty assignee and an `updated` timestamp inside the selected sync window.
5. Metric, storage, and UI labels should be renamed away from `completed` and `done` where they would otherwise become misleading.
6. No new dependencies or external services are required for this change.

## Objective
Replace the Jira workload signal from completed issue throughput to assigned issue activity so the dashboard answers:

- Which issues are assigned to team members?
- How many assigned Jira issues were active in the selected period?
- How does assigned Jira workload compare with GitHub implementation activity for the same team members?

## Tech Stack
- Python 3
- Standard library HTTP integration for Jira and GitHub
- SQLite for local persistence
- Streamlit dashboard UI

## Commands
- Test: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- Compile: `.venv/bin/python -m compileall src tests`
- Sync: `PYTHONPATH=src .venv/bin/python -m workload_analytics.jobs.sync_metrics --start-date 2026-04-01 --end-date 2026-04-30 --granularity week`
- Dashboard: `PYTHONPATH=src .venv/bin/streamlit run src/workload_analytics/dashboard/app.py`

## Project Structure
- `src/workload_analytics/clients/` -> Jira JQL construction and payload parsing
- `src/workload_analytics/pipelines/` -> Jira normalization and sync orchestration
- `src/workload_analytics/storage/` -> SQLite schema and persistence
- `src/workload_analytics/dashboard/` -> query layer, summaries, charts, and exports
- `tests/integration/` -> end-to-end sync and Jira client scenarios
- `tests/unit/` -> settings, normalization, dashboard query, and export coverage
- `docs/specs/` -> change specification and follow-up implementation notes

## Code Style
```python
@dataclass(frozen=True, slots=True)
class JiraAssignedIssuePayload:
    project_key: str
    issue_key: str
    assignee_email: str | None
    assignee_display_name: str | None
    updated_at: datetime
    status_name: str
```

Conventions:
- Keep typed dataclasses for provider payloads and normalized domain events.
- Use explicit names that match metric semantics.
- Keep JQL builder logic isolated in small pure functions so tests can assert exact queries.

## Testing Strategy
- Unit tests:
  - Jira JQL builder generates assignee-based queries for the selected period.
  - Jira payload parsing accepts `updated` timestamps and rejects missing activity timestamps.
  - Jira normalization still drops records without assignee email.
  - Dashboard/export/query layers expose assigned naming consistently.
- Integration tests:
  - Jira client fetches assigned issues across multiple projects and paginates correctly.
  - Sync pipeline persists raw Jira payloads, normalized Jira events, and aggregated metrics using assigned semantics.
  - Storage schema tests cover any renamed tables or columns.
- Verification:
  - Run `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  - Run `.venv/bin/python -m compileall src tests`

## Boundaries
- Always:
  - Keep GitHub metrics and repository discovery behavior unchanged.
  - Preserve date-range filtering and granularity-based aggregation.
  - Update docs and tests together with code changes.
- Ask first:
  - Adding a config flag to support both `completed` and `assigned` modes at runtime.
  - Preserving backward compatibility for existing SQLite table names instead of renaming them.
  - Fetching Jira changelog/history to model historical assignment transitions.
- Never:
  - Reuse `completed` or `done` field names for assigned metrics when that would misstate the data.
  - Count issues without a resolved assignee email as matched team workload.
  - Introduce hidden breaking changes to the sync command contract.

## Success Criteria
- Jira sync fetches issues with a non-empty assignee and an `updated` timestamp within the selected window.
- Normalized Jira events remain keyed by assignee email and can still be filtered to configured team members.
- Aggregated metrics, dashboard labels, exports, and persistence names reflect assigned-issue semantics rather than completed-issue semantics.
- Existing automated tests are updated to the new meaning and pass locally.

## Confirmed Decisions
- Time anchor for the assigned metric: **`updated` within the selected period for issues with a current assignee** (the recommended v1 approach). Alternatives (assignment-regardless-of-update and changelog-based history) were deferred.

## Open Questions
- None at the current product scope.
