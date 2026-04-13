# Team Workload Analytics

Local-only workload analytics dashboard for one configured engineering team. It combines GitHub implementation signals and Jira assigned-issue activity into period-based views for day, week, or month windows.

## What This Tool Measures

- GitHub implementation signals:
  - merged PR count
  - landed commit count
  - landed-commit lines added / deleted
  - PR cycle time (creation to merge)
  - first-review wait time
  - stale PR count (long-open unmerged PRs)
  - PR size buckets (small / medium / large)
- Jira assigned-issue activity:
  - assigned issue count within the selected update window
  - WIP status buckets: todo, in progress, review, done, other
- DORA-lite delivery:
  - successful / failed deployment count (GitHub deployments)
  - deployment lead time (commit to successful deployment)
  - deployment candidates are scanned from deployments created up to 7 days before the selected window, then filtered by latest deployment status time
- Developer focus:
  - active repository count per developer per period
- Commit heatmap:
  - commit distribution by day-of-week and hour (KST)

These numbers are workload signals, not a productivity score. Generated files, lockfiles, vendored paths, and merge commits are excluded by default.

## Dashboard Features

- **Overview cards**: Active Developers, GitHub Signals, PR Flow, Jira WIP, Delivery, Sync Scope with period-over-period delta badges
- **Trend sparklines**: period-by-period change rates for merged PRs, landed commits, assigned issues, done issues, stale PRs
- **Health indicators**: 업무 분배도, 리뷰 흐름, WIP 추세, 배포 안정성, 처리 흐름 (good / caution / warning / no_data)
- **Alerts**: WIP 편중, 리뷰 병목, Stale PR 누적, 대형 PR 비율, 비활성 개발자, 리뷰 대기 이상치
- **Signal charts**: team trend, PR flow, developer comparison, Jira throughput, DORA-lite delivery, review efficiency, workload balance, provider split, commit heatmap, developer focus
- **Global search**: filters developer-period rows and derived developer views by developer email, date, or metric value; delivery views remain team-level for the selected date range and granularity
- **Export**: CSV, JSON, Excel, 주간 리포트 (Markdown)
- **Configurable thresholds**: environment variables to tune alert and health indicator sensitivity
- **Dark mode**: automatic via `prefers-color-scheme`
- **Responsive layout**: adapts to mobile, tablet, and desktop widths

## Local Setup

1. Create a Python environment and install local UI dependencies.

```bash
python3 -m venv .venv
.venv/bin/pip install streamlit plotly openpyxl
```

2. Set sync environment variables when you plan to run data collection:

```bash
export WORKLOAD_TEAM_NAME="Platform"
export WORKLOAD_JIRA_PROJECTS="ENG,WEB"
export WORKLOAD_TEAM_MEMBERS="engineer@example.com,analyst@example.com,manager@example.com"
export WORKLOAD_LOOKBACK_DAYS="90"
export WORKLOAD_DEFAULT_GRANULARITY="day"
export WORKLOAD_ALLOWED_GRANULARITIES="day,week,month"
export WORKLOAD_SQLITE_PATH="var/workload_analytics.sqlite3"

export GITHUB_TOKEN="your-github-token"
export GITHUB_API_BASE_URL="https://api.github.com"
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_USER_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-jira-api-token"
```

Choose one GitHub scope mode:

- Explicit repositories:

```bash
export WORKLOAD_GITHUB_REPOSITORIES="org/api,org/web"
unset WORKLOAD_GITHUB_ORGANIZATION
```

- Organization-wide discovery:

```bash
unset WORKLOAD_GITHUB_REPOSITORIES
export WORKLOAD_GITHUB_ORGANIZATION="org"
```

Organization mode requires `WORKLOAD_TEAM_MEMBERS`. Explicit repository mode can omit it, but if you do configure a roster the final workload dataset is filtered to that team there as well.

3. (Optional) Configure alert and health indicator thresholds:

```bash
export WORKLOAD_REVIEW_WAIT_HOURS="24"            # alert: review bottleneck threshold (hours)
export WORKLOAD_REVIEW_WAIT_CAUTION_HOURS="12"     # health: review wait caution (hours)
export WORKLOAD_REVIEW_WAIT_WARNING_HOURS="48"     # health: review wait warning (hours)
export WORKLOAD_STALE_PR_COUNT="5"                 # alert: stale PR accumulation threshold
export WORKLOAD_LARGE_PR_LINES="500"               # alert: large PR line threshold
export WORKLOAD_LARGE_PR_RATIO="0.5"               # alert: large PR ratio threshold
export WORKLOAD_WIP_CONCENTRATION_FACTOR="2.0"     # alert: WIP concentration multiplier
export WORKLOAD_CV_GOOD="0.5"                      # health: workload distribution CV good
export WORKLOAD_CV_CAUTION="1.0"                   # health: workload distribution CV caution
export WORKLOAD_WIP_TREND_CAUTION_RATE="0.3"       # health: WIP trend caution rate
export WORKLOAD_DEPLOYMENT_SUCCESS_GOOD="0.9"      # health: deployment success rate good
export WORKLOAD_DEPLOYMENT_SUCCESS_CAUTION="0.7"   # health: deployment success rate caution
```

All thresholds have sensible defaults and are optional.

4. Run the sync command:

```bash
PYTHONPATH=src .venv/bin/python -m workload_analytics.jobs.sync_metrics \
  --start-date 2026-01-01 \
  --end-date 2026-03-31 \
  --granularity week
```

Interactive terminals show stage progress on `stderr` automatically. If you want to force progress logs in a non-interactive shell, add `--progress`.

5. Start the dashboard:

```bash
PYTHONPATH=src .venv/bin/streamlit run src/workload_analytics/dashboard/app.py
```

The dashboard itself only needs a readable SQLite file. `WORKLOAD_SQLITE_PATH` is optional, and `WORKLOAD_TEAM_MEMBERS` is only needed if you want the developer picker to show your configured roster even during inactive periods.

If you want to point the dashboard at a different SQLite file for one run, pass it after Streamlit's `--` separator:

```bash
PYTHONPATH=src .venv/bin/streamlit run src/workload_analytics/dashboard/app.py -- \
  --sqlite-path var/workload_analytics.backfill.sqlite3
```

## Utility Scripts

### Jira-only Sync

Re-fetch Jira data and re-aggregate without touching GitHub data. Useful when Jira issues update more frequently than code activity:

```bash
source .env && PYTHONPATH=src .venv/bin/python scripts/sync_jira_only.py
```

The script reads the existing sync date range from the database, fetches fresh Jira issues, and re-aggregates all developer-period metrics.

## Local Test Commands

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m compileall src tests
```

## Project Structure

```text
docs/specs/                         -> Product and technical specs
scripts/                            -> Utility scripts (e.g. Jira-only sync)
src/workload_analytics/
  config/                           -> Env parsing, secrets, team mapping
  clients/                          -> GitHub and Jira API clients, HTTP helpers, payload parsing
  models/                           -> Typed metric models and schemas
  pipelines/                        -> Fetch, normalize, aggregate logic
  storage/                          -> SQLite access, schema, helpers
  dashboard/                        -> Streamlit pages, filters, charts, styles, export, guides
  jobs/                             -> CLI entrypoints for full sync
tests/
  unit/                             -> Pure logic and transform tests
  integration/                      -> API client, storage, and sync flow tests
```

## SQLite Layout

The local database stores:

- `raw_github_pull_requests`
- `raw_github_commits`
- `raw_github_deployments`
- `raw_jira_assigned_issues`
- `normalized_github_pull_requests`
- `normalized_github_commits`
- `normalized_github_deployments`
- `normalized_jira_assigned_issues`
- `developer_period_metrics`
- `team_period_delivery_metrics`
- `sync_runs`

Dashboard views read from `developer_period_metrics`, `team_period_delivery_metrics`, and `sync_runs`, not re-aggregate raw payloads on every page load. In organization mode, `sync_runs` also captures discovered and excluded repository counts for the latest sync scope summary. GitHub deployment fetches are bounded by a 7-day created-at lookback before the requested delivery window to avoid status lookups across a repository's full deployment history.

## Interpreting the Charts

- **Team trend**: shows how GitHub and Jira workload moves across periods, with moving averages
- **PR flow**: cycle time, review wait time, and stale PR accumulation over periods
- **Per-developer comparison**: compares developers over the selected filter window
- **Jira throughput**: done vs open issue ratio by period with done-rate trend
- **DORA-lite delivery**: successful and failed deployments with deployment lead time
- **Review efficiency**: per-developer average review wait time against team average
- **Workload balance**: per-developer Jira WIP distribution by status bucket
- **GitHub vs Jira split**: contrasts implementation activity with Jira issue activity
- **Commit heatmap**: shows when the team commits by day-of-week and hour (KST)
- **Developer focus**: average active repository count per developer

Use the charts to spot load concentration, review process changes, deployment health, or project rhythm shifts. Do not use them as a standalone ranking mechanism.
