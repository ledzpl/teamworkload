# Task Breakdown: Team Workload Analytics Dashboard

## Phase 1: Foundation

- [x] Task: Define runtime configuration and team scope schema
  - Acceptance: A typed configuration model exists for GitHub credentials, Jira credentials, one team definition, explicit GitHub repositories or one GitHub organization, multiple Jira projects, date defaults, and granularity options.
  - Acceptance: Invalid or incomplete local configuration fails fast with actionable errors.
  - Verify: `python3 -m unittest tests.unit.test_settings`
  - Files: `src/workload_analytics/config/settings.py`, `src/workload_analytics/config/team_scope.py`, `tests/unit/test_settings.py`

- [x] Task: Define internal metric and identity models
  - Acceptance: Internal models exist for raw source events, normalized developer identity keyed by email, and aggregated developer-period metrics.
  - Acceptance: GitHub PR, GitHub commit, and Jira assigned-issue metrics are represented without collapsing into a single score.
  - Verify: `python3 -m unittest tests.unit.test_metric_models`
  - Files: `src/workload_analytics/models/source_events.py`, `src/workload_analytics/models/metrics.py`, `tests/unit/test_metric_models.py`

- [x] Task: Implement metric definitions and period bucketing rules
  - Acceptance: Metric formulas and exclusion rules live in one module with clear docstrings.
  - Acceptance: Day, week, and month bucketing produce deterministic period boundaries.
  - Verify: `python3 -m unittest tests.unit.test_metric_rules tests.unit.test_period_bucketing`
  - Files: `src/workload_analytics/pipelines/metric_rules.py`, `src/workload_analytics/pipelines/periods.py`, `tests/unit/test_metric_rules.py`, `tests/unit/test_period_bucketing.py`

## Checkpoint: Foundation
- [x] All foundation tests pass.
- [x] One team, multi-repo, multi-project scope is explicit in config and models.
- [x] Metric definitions match the approved spec.

## Phase 2: GitHub Ingestion

- [x] Task: Build GitHub client for repository-scoped PR and commit fetch
  - Acceptance: The client can fetch merged PR data and landed commit data across multiple configured repositories for a selected date range.
  - Acceptance: The client can discover accessible repositories for one configured GitHub organization.
  - Acceptance: Pagination and rate-limit aware request flow are implemented.
  - Verify: `python3 -m unittest tests.integration.test_github_client`
  - Files: `src/workload_analytics/clients/github_client.py`, `tests/integration/test_github_client.py`

- [x] Task: Normalize GitHub activity into email-keyed metric events
  - Acceptance: Raw GitHub PR and commit payloads are transformed into normalized rows with repository, author email, merged or landed timestamps, and line counts.
  - Acceptance: Merge commits, vendored paths, generated files, and lockfiles are excluded by default.
  - Verify: `python3 -m unittest tests.unit.test_github_normalization`
  - Files: `src/workload_analytics/pipelines/github_normalize.py`, `tests/unit/test_github_normalization.py`, `tests/fixtures/github/`

## Phase 3: Jira Ingestion

- [x] Task: Build Jira client for assigned issue fetch across configured projects
  - Acceptance: The client can fetch issues with a current assignee and an `updated` timestamp inside the selected date range across all configured Jira projects for the team.
  - Acceptance: The query semantics match the documented assigned-issue metric.
  - Verify: `python3 -m unittest tests.integration.test_jira_client`
  - Files: `src/workload_analytics/clients/jira_client.py`, `tests/integration/test_jira_client.py`

- [x] Task: Normalize Jira assigned issues into email-keyed workload events
  - Acceptance: Jira issue payloads are normalized into rows keyed by assignee email and update timestamp.
  - Acceptance: Missing assignee or email cases are preserved as auditable dropped or unmatched records.
  - Verify: `python3 -m unittest tests.unit.test_jira_normalization`
  - Files: `src/workload_analytics/pipelines/jira_normalize.py`, `tests/unit/test_jira_normalization.py`, `tests/fixtures/jira/`

## Checkpoint: Source Ingestion
- [x] GitHub and Jira ingestion tests pass.
- [x] Missing-email and unmatched-user cases are surfaced, not silently discarded.
- [x] Provider-specific code is isolated from aggregation code.

## Phase 4: Aggregation and Storage

- [x] Task: Design SQLite schema for raw, normalized, and aggregated data
  - Acceptance: Tables exist for raw snapshots, normalized GitHub events, normalized Jira events, and developer-period aggregates.
  - Acceptance: The schema keeps PR count, commit count, lines added, lines deleted, and assigned issue count as separate fields.
  - Verify: `python3 -m unittest tests.integration.test_storage_schema`
  - Files: `src/workload_analytics/storage/schema.py`, `src/workload_analytics/storage/sqlite_store.py`, `tests/integration/test_storage_schema.py`

- [x] Task: Implement sync pipeline from fetch to aggregate persistence
  - Acceptance: One sync command can fetch provider data, normalize rows, join by email, aggregate by chosen granularity, and persist results.
  - Acceptance: Sync output reports counts for repositories in scope, discovered repositories, excluded repositories, Jira projects, matched developers, unmatched records, and persisted rows.
  - Verify: `python3 -m unittest tests.integration.test_sync_pipeline`
  - Files: `src/workload_analytics/jobs/sync_metrics.py`, `src/workload_analytics/pipelines/sync_pipeline.py`, `tests/integration/test_sync_pipeline.py`

## Checkpoint: Aggregation
- [x] A 12-month backfill works against fixtures without manual intervention.
- [x] Aggregate totals match expected fixture outputs.
- [x] Sync summaries make data loss and identity gaps visible.

## Phase 5: Dashboard and Export

- [x] Task: Build dashboard filters and summary panels
  - Acceptance: The dashboard can select date range, granularity, and developer while staying within one configured team.
  - Acceptance: Summary panels show sync scope and top-level metric totals for the current filter state.
  - Verify: Manual check by running `PYTHONPATH=src streamlit run src/workload_analytics/dashboard/app.py`
  - Files: `src/workload_analytics/dashboard/app.py`, `src/workload_analytics/dashboard/filters.py`, `src/workload_analytics/dashboard/summary.py`

- [x] Task: Build trend and comparison visualizations
  - Acceptance: The dashboard renders team trend, per-developer comparison, and GitHub versus Jira split charts from stored aggregates.
  - Acceptance: Metric definitions and default exclusions are visible near the charts.
  - Verify: `python3 -m unittest tests.unit.test_dashboard_queries` and manual check with fixture-backed local database
  - Files: `src/workload_analytics/dashboard/charts.py`, `src/workload_analytics/dashboard/queries.py`, `tests/unit/test_dashboard_queries.py`

- [x] Task: Add CSV export for the current filtered dataset
  - Acceptance: Exported CSV rows and columns match the visible filtered dataset exactly.
  - Acceptance: Export metadata includes selected date range and granularity.
  - Verify: `python3 -m unittest tests.unit.test_csv_export` and manual export check from the dashboard
  - Files: `src/workload_analytics/dashboard/export.py`, `tests/unit/test_csv_export.py`

## Checkpoint: Dashboard
- [x] Dashboard values match stored aggregates.
- [x] Filters, charts, and export stay consistent with the same query state.
- [x] Metric definitions are visible in the local UI.

## Phase 6: Hardening

- [x] Task: Add error handling and operator-facing sync feedback
  - Acceptance: Credential failures, API failures, empty result windows, and unmatched-email conditions surface clear local messages.
  - Acceptance: Partial failures do not produce silently corrupted aggregates.
  - Verify: `python3 -m unittest tests.integration.test_sync_failures`
  - Files: `src/workload_analytics/pipelines/sync_pipeline.py`, `src/workload_analytics/dashboard/app.py`, `tests/integration/test_sync_failures.py`

- [x] Task: Add local setup and metric interpretation documentation
  - Acceptance: A local setup guide explains credentials, team scope configuration, sync usage, and dashboard launch.
  - Acceptance: Metric interpretation guidance explains what the charts mean and what they do not mean.
  - Verify: Manual review against the approved spec and local run commands.
  - Files: `README.md`, `docs/specs/workload-analytics-spec.md`

## Phase 7: Productivity Insights Expansion

- [x] Task: Add PR flow metrics to GitHub ingestion and normalization
  - Acceptance: PR cycle time (created to merged), first-review wait time, stale PR count, and PR size buckets (small/medium/large) are computed during normalization.
  - Acceptance: New fields are persisted in `developer_period_metrics` and `normalized_github_pull_requests`.
  - Verify: `python3 -m unittest tests.unit.test_github_normalization tests.unit.test_metric_rules`
  - Files: `src/workload_analytics/pipelines/github_normalize.py`, `src/workload_analytics/models/metrics.py`

- [x] Task: Add DORA-lite delivery metrics from GitHub deployments
  - Acceptance: GitHub deployments are fetched, normalized, and stored in `raw_github_deployments`, `normalized_github_deployments`, and `team_period_delivery_metrics`.
  - Acceptance: Successful/failed deployment counts and deployment lead time are computed per period.
  - Verify: `python3 -m unittest tests.integration.test_sync_pipeline`
  - Files: `src/workload_analytics/clients/github_client.py`, `src/workload_analytics/pipelines/github_normalize.py`, `src/workload_analytics/storage/schema.py`

- [x] Task: Add Jira WIP status buckets
  - Acceptance: Jira assigned issues are grouped into todo, in progress, review, done, other buckets based on status name mapping.
  - Acceptance: WIP bucket counts are persisted per developer per period.
  - Verify: `python3 -m unittest tests.unit.test_jira_normalization`
  - Files: `src/workload_analytics/pipelines/jira_normalize.py`, `src/workload_analytics/models/metrics.py`

- [x] Task: Build PR flow, delivery, review efficiency, workload balance, and Jira throughput charts
  - Acceptance: Dashboard renders PR flow, DORA-lite delivery, per-developer review efficiency, workload balance, and Jira throughput charts.
  - Verify: Manual check with `PYTHONPATH=src streamlit run src/workload_analytics/dashboard/app.py`
  - Files: `src/workload_analytics/dashboard/charts.py`, `src/workload_analytics/dashboard/queries.py`

## Checkpoint: Productivity Insights
- [x] PR flow, delivery, and WIP metrics are visible in the dashboard.
- [x] New metric fields are persisted in SQLite and survive re-sync.
- [x] Existing tests remain green.

## Phase 8: Dashboard Health, Alerts, and Advanced Views

- [x] Task: Build summary cards with period-over-period delta badges
  - Acceptance: Overview section shows 6 summary cards (Active Developers, GitHub Signals, PR Flow, Jira WIP, Delivery, Sync Scope) with delta badges comparing to the previous period.
  - Verify: Manual check on the dashboard.
  - Files: `src/workload_analytics/dashboard/summary.py`, `src/workload_analytics/dashboard/app.py`

- [x] Task: Build trend sparklines for key metrics
  - Acceptance: Trend section shows sparkline charts for merged PRs, landed commits, assigned issues, done issues, and stale PRs with percentage change labels.
  - Verify: Manual check on the dashboard.
  - Files: `src/workload_analytics/dashboard/summary.py`, `src/workload_analytics/dashboard/charts.py`

- [x] Task: Build health indicators
  - Acceptance: Health section shows 5 indicators (업무 분배도, 리뷰 흐름, WIP 추세, 배포 안정성, 처리 흐름) with good/caution/warning/no_data status.
  - Acceptance: Thresholds are configurable via WORKLOAD_THRESHOLD_* environment variables.
  - Verify: `python3 -m unittest tests.unit.test_health_indicators`
  - Files: `src/workload_analytics/dashboard/health.py`, `src/workload_analytics/config/settings.py`

- [x] Task: Build operational alerts
  - Acceptance: Alerts section detects WIP 편중, 리뷰 병목, Stale PR 누적, 대형 PR 비율, 비활성 개발자, 리뷰 대기 이상치.
  - Acceptance: Alert thresholds are configurable via environment variables.
  - Verify: `python3 -m unittest tests.unit.test_alerts`
  - Files: `src/workload_analytics/dashboard/alerts.py`

- [x] Task: Build commit heatmap and developer focus charts
  - Acceptance: Commit heatmap shows day-of-week by hour distribution in KST timezone.
  - Acceptance: Developer focus shows average active repository count per developer.
  - Verify: Manual check on the dashboard.
  - Files: `src/workload_analytics/dashboard/charts.py`, `src/workload_analytics/dashboard/queries.py`

- [x] Task: Add global search and multi-format export
  - Acceptance: Global search filters the entire dashboard by developer email, date, or metric value.
  - Acceptance: Export supports CSV, JSON, Excel, and 주간 리포트 (Markdown) formats.
  - Verify: Manual check on the dashboard.
  - Files: `src/workload_analytics/dashboard/app.py`, `src/workload_analytics/dashboard/queries.py`, `src/workload_analytics/dashboard/export.py`, `src/workload_analytics/dashboard/report.py`

- [x] Task: Add interpretation guides for each dashboard section
  - Acceptance: Each major section (Overview, Health, Alerts, Signals) has an expandable guide explaining how to read the data.
  - Verify: Manual check on the dashboard.
  - Files: `src/workload_analytics/dashboard/guides.py`

## Checkpoint: Dashboard Health, Alerts, and Advanced Views
- [x] Health indicators, alerts, and advanced charts are visible.
- [x] Thresholds are configurable and have sensible defaults.
- [x] Export supports all four formats.

## Phase 9: UI Polish and Dark Mode

- [x] Task: Implement Genesis design system and dark mode
  - Acceptance: Dashboard follows the Genesis editorial design language with proper typography, spacing, and color tokens.
  - Acceptance: Dark mode activates automatically via prefers-color-scheme.
  - Acceptance: Responsive layout adapts to mobile, tablet, and desktop widths.
  - Verify: Manual check at 320px, 768px, 1024px, and 1440px widths.
  - Files: `src/workload_analytics/dashboard/styles.py`, `src/workload_analytics/dashboard/app.py`

## Final Checkpoint
- [x] All acceptance criteria in the spec are satisfied.
- [x] Local setup, sync, and dashboard flows are documented.
- [x] The v1 scope remains one team, multi-repo or organization-scope GitHub ingestion, multi-project Jira ingestion, local-only execution.
- [x] Health indicators, alerts, trend sparklines, and advanced charts are operational.
- [x] Export supports CSV, JSON, Excel, and Markdown.
- [x] Dark mode and responsive layout are functional.
