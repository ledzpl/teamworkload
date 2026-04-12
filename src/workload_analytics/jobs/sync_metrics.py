from __future__ import annotations

import argparse
from datetime import date
import json
import sys

from workload_analytics.clients import GithubApiError, GithubClient, JiraClient
from workload_analytics.config import ConfigError, Granularity, load_settings
from workload_analytics.pipelines.sync_pipeline import (
    SyncProgressEvent,
    SyncExecutionError,
    WorkloadSyncPipeline,
)
from workload_analytics.storage import SQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync workload analytics metrics.")
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--granularity",
        required=True,
        choices=[item.value for item in Granularity],
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Force human-readable stage progress logs on stderr.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.start_date > args.end_date:
        parser.error("--start-date must be on or before --end-date")

    try:
        settings = load_settings()
        pipeline = WorkloadSyncPipeline(
            settings=settings,
            github_client=GithubClient(
                token=settings.github.token,
                base_url=settings.github.base_url,
            ),
            jira_client=JiraClient(
                base_url=settings.jira.base_url,
                user_email=settings.jira.user_email,
                api_token=settings.jira.api_token,
            ),
            store=SQLiteStore(sqlite_path=settings.storage.sqlite_path),
            progress_reporter=(
                _build_progress_reporter(sys.stderr)
                if args.progress or _stderr_supports_progress(sys.stderr)
                else None
            ),
        )
        summary = pipeline.run(
            start_date=args.start_date,
            end_date=args.end_date,
            granularity=Granularity(args.granularity),
        )
    except (ConfigError, SyncExecutionError, RuntimeError) as exc:
        error_payload = {"error": str(exc)}
        provider_error = exc
        if isinstance(exc, SyncExecutionError):
            error_payload["stage"] = exc.stage
            provider_error = exc.__cause__ if exc.__cause__ is not None else exc
        if isinstance(provider_error, GithubApiError):
            error_payload["path"] = provider_error.path
            error_payload["status_code"] = provider_error.status_code
        print(json.dumps(error_payload, sort_keys=True), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "run_id": summary.run_id,
                "start_date": summary.start_date.isoformat(),
                "end_date": summary.end_date.isoformat(),
                "granularity": summary.granularity.value,
                "github_repository_count": summary.github_repository_count,
                "discovered_repository_count": summary.discovered_repository_count,
                "excluded_repository_count": summary.excluded_repository_count,
                "jira_project_count": summary.jira_project_count,
                "matched_developer_count": summary.matched_developer_count,
                "unmatched_record_count": summary.unmatched_record_count,
                "aggregate_row_count": summary.aggregate_row_count,
                "persisted_row_count": summary.persisted_row_count,
                "messages": list(summary.messages),
            },
            sort_keys=True,
        )
    )
    return 0

def _stderr_supports_progress(stream) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)())


def _build_progress_reporter(stream):
    def report(event: SyncProgressEvent) -> None:
        print(f"[sync:{event.state}] {event.message}", file=stream, flush=True)

    return report


if __name__ == "__main__":
    raise SystemExit(main())
