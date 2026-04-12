# Spec: Team Workload Analytics Dashboard

## Assumptions
1. This is a greenfield internal analytics project, not an extension of an existing production app.
2. The primary users are engineering managers, team leads, and PMs who want period-based workload visibility for a team.
3. GitHub workload for v1 is reported through both merged PR activity and landed commit activity, not review comments or issue comments.
4. Jira activity for v1 is measured from issues with a current assignee and an `updated` timestamp during the selected period.
5. The first release is an internal web dashboard with CSV export, not a public-facing product.
6. User identity between GitHub and Jira is matched by email address as the canonical key.
7. Generated files, lockfiles, vendored code, and merge commits should be excluded from GitHub workload metrics unless explicitly requested otherwise.
8. The first release targets one configured team scope, not cross-team analytics.
9. One team scope may include multiple GitHub repositories and multiple Jira projects, or it may discover GitHub repositories from one configured organization.
10. The first deployment mode is local execution only, not a shared hosted service.

## Objective
Build an internal analytics tool that pulls period-based workload data from GitHub and Jira, normalizes it by developer, and visualizes trends for one configured team.

The tool must answer these questions:
- Over a given date range, how much code activity did each developer contribute in GitHub?
- Over the same range, how many Jira tasks were assigned to each developer and updated in that window?
- How does team workload change by day, week, or month?
- Within one configured team, which developers or periods show unusually high or low workload relative to the selected window?

This is a workload visibility tool, not a performance ranking tool. The UI must make the metric definitions visible so the data is interpreted as operational signal rather than absolute productivity.

## Tech Stack
- Python 3.14
- Streamlit for the internal dashboard UI
- Python standard library HTTP clients for GitHub and Jira API calls in v1
- SQLite via `sqlite3` for local raw snapshots, normalized events, and aggregated tables
- Plotly for charts
- unittest for tests
- ruff for linting
- mypy for type checking

## Commands
- Setup venv: `python3 -m venv .venv`
- Run dashboard: `PYTHONPATH=src streamlit run src/workload_analytics/dashboard/app.py`
- Sync data once: `PYTHONPATH=src python3 -m workload_analytics.jobs.sync_metrics --start-date 2026-01-01 --end-date 2026-03-31 --granularity week`
- Run tests: `python3 -m unittest discover -s tests -p 'test_*.py'`
- Run syntax check: `python3 -m compileall src tests`

## Project Structure
```text
docs/specs/                         -> Product and technical specs
scripts/                            -> Utility scripts (e.g. Jira-only sync)
src/workload_analytics/
src/workload_analytics/config/      -> Env parsing, secrets, team mapping
src/workload_analytics/clients/     -> GitHub and Jira API clients, HTTP helpers, payload parsing
src/workload_analytics/models/      -> Typed metric models and schemas
src/workload_analytics/pipelines/   -> Fetch, normalize, aggregate logic
src/workload_analytics/storage/     -> SQLite access, schema, helpers
src/workload_analytics/dashboard/   -> Streamlit pages, filters, charts, styles, export, guides
src/workload_analytics/jobs/        -> CLI entrypoints for sync or backfill
tests/conftest.py                   -> Shared test configuration
tests/unit/                         -> Pure logic and transform tests
tests/integration/                  -> API client, storage, and sync flow tests
```

## Code Style
Use explicit typed models and keep metric definitions centralized so the UI and sync pipeline cannot drift.

```python
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class DeveloperPeriodMetrics:
    granularity: Granularity
    developer_email: str
    period_start: date
    period_end: date
    github_prs_merged: int
    github_commits_landed: int
    github_lines_added: int
    github_lines_deleted: int
    github_pr_cycle_time_hours: float
    github_prs_with_cycle_time: int
    github_pr_review_wait_hours: float
    github_prs_with_review_wait: int
    github_prs_stale: int
    github_prs_small: int
    github_prs_medium: int
    github_prs_large: int
    jira_issues_assigned: int
    jira_todo_issues: int
    jira_in_progress_issues: int
    jira_review_issues: int
    jira_done_issues: int
    jira_other_issues: int
```

Conventions:
- Use snake_case for Python modules, functions, variables, and CLI flags.
- Keep API payload parsing separate from business metric calculation.
- Normalize raw provider data into internal models before aggregation.
- Use email as the canonical join key between GitHub and Jira users in v1.
- When GitHub organization scope is enabled, keep the final aggregated people scope limited to `WORKLOAD_TEAM_MEMBERS`.
- Exclude hidden logic in UI files; dashboard components should consume prepared metric tables.
- Put metric formulas in one module with docstrings and tests.

## Testing Strategy
- Framework: unittest
- Unit tests:
  - GitHub metric calculation from commit and merged PR payload fixtures
  - Jira assigned-issue calculation from assignee and update-window fixtures
  - Period bucketing for day, week, and month aggregation
  - Identity mapping logic between GitHub users and Jira assignees by email
- Integration tests:
  - GitHub client pagination and date filtering with mocked HTTP responses
  - Jira client assigned-issue parsing with mocked HTTP responses
  - SQLite writes and reloads for raw, normalized, and aggregated tables
  - End-to-end sync flow using fixture payloads into dashboard-ready tables
- Coverage target:
  - 85%+ on `pipelines/`, `clients/`, and `storage/`
- Manual verification:
  - Dashboard can filter by date range, developer, and granularity
  - Chart values match fixture-driven expected totals
  - CSV export matches the visible filtered dataset

## Boundaries
- Always:
  - Exclude generated files, vendored directories, and merge commits from default GitHub metrics
  - Keep raw provider payloads and normalized metric tables distinguishable
  - Show metric definitions and filter state in the dashboard
  - Validate date ranges, granularity, and required credentials before sync starts
  - Keep GitHub and Jira identity mapping auditable
  - Keep the first release scoped to one configured team
  - Support multiple GitHub repositories and Jira projects inside that team configuration
  - Support one GitHub organization discovery mode that excludes archived and fork repositories by default
- Ask first:
  - Adding a shared database or cloud deployment target
  - Changing the default metric definition for "code implementation amount"
  - Introducing HR-style ranking, scoring, or individual performance labels
  - Adding new external services beyond GitHub and Jira
  - Persisting raw provider responses longer than needed for debugging
- Never:
  - Commit tokens, cookies, Jira API keys, or raw secrets to the repository
  - Treat lines changed as a standalone productivity score
  - Count generated code or dependency lockfile churn as implementation work by default
  - Drop failed tests to get the pipeline green

## Success Criteria
- A user can sync GitHub and Jira data for a selectable date range and see a successful sync summary with record counts.
- A user can configure one team scope that includes multiple GitHub repositories and multiple Jira projects, or GitHub organization-wide discovery plus multiple Jira projects.
- A user can switch aggregation granularity between day, week, and month without re-entering filters.
- The dashboard shows at least these metrics per developer and per period:
  - merged PR count
  - landed commit count
  - lines added
  - lines deleted
  - assigned issues
  - PR cycle time hours, first-review wait hours, stale PR count, PR size buckets
  - Jira WIP status buckets (todo, in progress, review, done, other)
- The dashboard shows team-level delivery metrics per period:
  - successful deployment count
  - failed deployment count
  - deployment lead time (DORA-lite)
- The dashboard shows at least these visualizations:
  - team total workload trend over time (with moving averages)
  - per-developer comparison for the selected period
  - GitHub versus Jira split view for the same developer or team
  - PR flow chart (cycle time, review wait, stale PRs)
  - Jira throughput chart (done vs open with done-rate trend)
  - DORA-lite delivery chart (deployments and lead time)
  - review efficiency chart (per-developer review wait vs team average)
  - workload balance chart (per-developer Jira WIP by status bucket)
  - commit heatmap (day-of-week by hour, KST timezone)
  - developer focus chart (active repo count per developer)
  - trend sparklines (period-over-period change for key metrics)
- The dashboard shows summary cards with period-over-period delta badges for Active Developers, GitHub Signals, PR Flow, Jira WIP, Delivery, and Sync Scope.
- The dashboard shows health indicators for 업무 분배도, 리뷰 흐름, WIP 추세, 배포 안정성, 처리 흐름 with good/caution/warning/no_data status.
- The dashboard shows operational alerts for WIP 편중, 리뷰 병목, Stale PR 누적, 대형 PR 비율, 비활성 개발자, 리뷰 대기 이상치.
- Global search filters the entire dashboard by developer email, date, or metric value.
- Export supports CSV, JSON, Excel, and 주간 리포트 (Markdown) formats.
- Alert and health indicator thresholds are configurable via `WORKLOAD_THRESHOLD_*` environment variables with sensible defaults.
- The dashboard supports dark mode automatically via `prefers-color-scheme`.
- Cached queries for a 12-month window and a team of up to 30 developers render the main charts in under 3 seconds on a typical laptop.
- The system can backfill at least 12 months of data without manual data editing.
- Metric definitions and exclusions are visible in the UI.

## Confirmed Decisions
- GitHub implementation metrics use both merged PR activity and landed commit activity.
- Jira assigned-issue activity uses assigned issue count within the selected update window.
- GitHub and Jira user identities are joined by email.
- The first release is scoped to one configured team.
- One team scope can include multiple GitHub repositories and multiple Jira projects.
- GitHub v1 also supports one organization-wide discovery mode, filtered back down to `WORKLOAD_TEAM_MEMBERS`.
- The first release is local execution only.

## Open Questions
- None at the current product scope.
