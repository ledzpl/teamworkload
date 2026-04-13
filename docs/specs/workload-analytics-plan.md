# Implementation Plan: Team Workload Analytics Dashboard

## Overview
Build a v1 internal dashboard that collects workload data for one configured team from either multiple explicit GitHub repositories or one GitHub organization plus multiple Jira projects, normalizes it by developer email, stores aggregated period metrics locally, and visualizes trends by day, week, or month.

The plan optimizes for correctness of metric definitions first, then repeatable sync, then dashboard usability. Because this tool can be misread as a productivity scorecard, metric transparency and exclusions are treated as first-class requirements.

## Architecture Decisions
- Use SQLite as the local source of truth so sync and dashboard reads share the same persisted state without extra dependencies.
- Keep GitHub and Jira ingestion separate, and join only after normalization to an internal developer-period model.
- Use email as the canonical identity key in v1 to avoid manual mapping complexity in the first release.
- Expose GitHub workload as separate signals, not a single synthetic score:
  - merged PR count, landed commit count, lines added, lines deleted
  - PR cycle time, first-review wait, stale PR count, PR size buckets
- Expose Jira activity as assigned issue count with WIP status buckets (todo, in progress, review, done, other).
- Expose team-level delivery metrics from GitHub deployments: success/failure counts and deployment lead time (DORA-lite).
- Bound GitHub deployment status lookup by scanning deployments created up to 7 days before the selected delivery window, then filtering by latest deployment status time.
- Layer health indicators and operational alerts on top of raw metrics with configurable thresholds.
- Limit v1 to one configured team scope so configuration and validation stay tractable.
- Allow that team scope to include multiple GitHub repositories and multiple Jira projects.
- Support one optional GitHub organization discovery mode and exclude archived or fork repositories by default.
- When organization mode is enabled, keep the final aggregated people scope limited to the configured team roster.
- Support local execution only in v1; shared hosted deployment is explicitly out of scope.
- Precompute period aggregates during sync so SQLite reads stay simple and fast in the dashboard.

## Dependency Graph
```text
team configuration + credentials + threshold config
    ->
GitHub client / Jira client
    ->
raw fetch models (PRs, commits, deployments, issues)
    ->
normalized developer identity + metric events + delivery events
    ->
period aggregation (developer metrics + team delivery metrics)
    ->
SQLite storage
    ->
dashboard filters / summary / health / alerts / charts / export
```

## Implementation Order
1. Define configuration, internal metric models, and period bucketing rules.
2. Build GitHub ingestion and normalization.
3. Build Jira ingestion and normalization.
4. Build storage tables and the sync pipeline that joins by developer email.
5. Build dashboard views on top of the aggregated tables.
6. Add export, validation messaging, and performance tuning.
7. Add PR flow, DORA-lite delivery, and Jira WIP status metrics.
8. Add health indicators, alerts, trend sparklines, commit heatmap, developer focus, and multi-format export.
9. Apply Genesis editorial design system, dark mode, and responsive layout.

## Workstreams
### Phase 1: Foundations
- Define environment configuration for GitHub credentials, Jira credentials, one team scope, multiple repositories, multiple Jira projects, and date/granularity options.
- Define internal schemas for raw events, normalized developer records, and aggregated period metrics.
- Define explicit metric formulas and exclusion rules in one module with tests.

### Checkpoint: Foundations
- Internal metric model can represent GitHub and Jira data without ambiguity.
- Period bucketing is stable for day, week, and month.
- Metric definitions are documented and testable.

### Phase 2: Source Ingestion
- Implement GitHub client pagination, repository discovery, repository/date filtering, multi-repository PR fetch, and multi-repository commit fetch.
- Normalize GitHub records into developer email keyed activity rows.
- Implement Jira client queries for assigned issues across the selected Jira projects and update window.
- Normalize Jira records into developer email keyed assigned-issue rows.

### Checkpoint: Source Ingestion
- Fixture-based ingestion tests pass for both providers.
- Data loss cases are visible, especially missing emails or missing assignees.
- Provider-specific logic remains isolated from aggregation logic.

### Phase 3: Aggregation and Storage
- Build local SQLite tables for raw snapshots, normalized events, and period aggregates.
- Implement sync jobs that fetch, normalize, join, aggregate, and persist.
- Generate sync summaries with counts for repositories in scope, discovered repositories, excluded repositories, Jira projects, issues, developers, and dropped records.

### Checkpoint: Aggregation and Storage
- A full sync can backfill a 12-month window into reproducible tables.
- Aggregated metrics match fixture expectations.
- Missing or unmatched emails are surfaced clearly.

### Phase 4: Dashboard and Export
- Build filter controls for date range, granularity, and developer selection.
- Build charts for team trend, developer comparison, and GitHub vs Jira split view.
- Add metric-definition help text and visible exclusion notes.
- Add CSV export for the currently filtered dataset.

### Checkpoint: Dashboard
- Dashboard values match stored aggregates.
- Filters update charts consistently.
- CSV export matches the visible filtered data.

### Phase 5: Hardening
- Add sync error handling, retry boundaries, and user-facing failure messages.
- Tune queries and caching so a 12-month view for up to 30 developers renders in under 3 seconds.
- Finalize documentation for local setup, sync, and metric interpretation.

### Checkpoint: Hardening
- Spec acceptance criteria map cleanly to implementation tasks.
- Critical risks have mitigation paths.
- The system boundary for v1 remains one team, multi-repo and multi-project, local-only dashboard mode.

### Phase 6: Productivity Insights
- Add PR flow metrics: cycle time, first-review wait, stale PR count, PR size buckets.
- Add DORA-lite delivery metrics from GitHub deployments: success/failure counts, deployment lead time.
- Add Jira WIP status buckets: todo, in progress, review, done, other.
- Build PR flow, delivery, review efficiency, workload balance, and Jira throughput charts.

### Checkpoint: Productivity Insights
- PR flow, delivery, and WIP metrics visible in dashboard.
- New fields persisted in SQLite and survive re-sync.

### Phase 7: Health, Alerts, and Advanced Views
- Build summary cards with period-over-period delta badges.
- Build trend sparklines for key metrics.
- Build health indicators with configurable thresholds.
- Build operational alerts with configurable thresholds.
- Build commit heatmap (KST) and developer focus charts.
- Add global search and multi-format export (CSV, JSON, Excel, Markdown).
- Add interpretation guides for each dashboard section.

### Checkpoint: Health and Alerts
- Health indicators, alerts, and advanced charts visible.
- Export supports all four formats.

### Phase 8: UI Polish
- Apply Genesis editorial design system.
- Implement automatic dark mode via prefers-color-scheme.
- Implement responsive layout for mobile, tablet, and desktop.

### Checkpoint: Ready for Release
- All acceptance criteria in the spec are satisfied.
- Dark mode and responsive layout functional.
- Documentation updated to reflect all features.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| GitHub and Jira users do not share reliable emails | High | Validate identity coverage early and emit unmatched-user reports during sync |
| GitHub commit and PR signals can be double-counted if combined into one score | High | Keep metrics separate in storage and UI; do not compute a single productivity number |
| Jira issue updates can reflect non-workflow edits as well as assignment activity | Medium | Keep the metric definition explicit in UI/docs and test query + aggregation semantics against fixtures |
| Multiple repositories, organization discovery, and Jira projects increase config and fetch complexity | Medium | Treat team scope as explicit config and add per-source sync summaries |
| SQLite is less flexible for ad hoc analytics than DuckDB | Medium | Precompute developer-period aggregates and index the dashboard lookup paths |
| API rate limits or long backfills slow sync | Medium | Use incremental sync windows, local caching, bounded pagination, and bounded GitHub deployment status scans |
| Team scope grows before v1 stabilizes | Medium | Keep config model extensible but enforce one-team validation in v1 |

## Parallelization Opportunities
- Safe in parallel after the metric model is fixed:
  - GitHub client implementation
  - Jira client implementation
  - Dashboard shell and static filter layout
- Must remain sequential:
  - Final metric schema definition
  - Developer identity join strategy
  - Aggregate table design

## Implementation Status
All 8 phases are complete. The v1 dashboard is feature-complete per the spec, with all acceptance criteria satisfied.

## Open Questions
- None at the current planning scope.
