from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, date, datetime
from io import StringIO
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from workload_analytics.clients import GithubApiError
from workload_analytics.jobs import sync_metrics
from workload_analytics.pipelines.sync_pipeline import (
    SyncExecutionError,
    SyncProgressEvent,
    SyncSummary,
)
from tests.integration.test_sync_pipeline import _build_settings


class FailingPipeline:
    def __init__(
        self,
        *,
        settings,
        github_client,
        jira_client,
        store,
        progress_reporter=None,
    ) -> None:
        del settings, github_client, jira_client, store, progress_reporter

    def run(self, *, start_date, end_date, granularity):
        del start_date, end_date, granularity
        api_error = GithubApiError(
            status_code=404,
            path="/repos/org/missing/pulls",
            message=(
                "GitHub API request failed for '/repos/org/missing/pulls' "
                "(404 Not Found). Check WORKLOAD_GITHUB_REPOSITORIES."
            ),
        )
        raise SyncExecutionError(
            stage="github_pull_requests",
            message=str(api_error),
        ) from api_error


class SuccessfulPipeline:
    def __init__(
        self,
        *,
        settings,
        github_client,
        jira_client,
        store,
        progress_reporter=None,
    ) -> None:
        del settings, github_client, jira_client, store
        self._progress_reporter = progress_reporter

    def run(self, *, start_date, end_date, granularity):
        if self._progress_reporter is not None:
            self._progress_reporter(
                SyncProgressEvent(
                    stage="github_pull_requests",
                    state="started",
                    message="Fetching GitHub pull requests",
                )
            )
            self._progress_reporter(
                SyncProgressEvent(
                    stage="github_pull_requests",
                    state="completed",
                    message="Fetched 24 merged pull requests",
                )
            )

        return SyncSummary(
            run_id="sync-run-1",
            started_at=datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 10, 9, 1, tzinfo=UTC),
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            github_repository_count=2,
            discovered_repository_count=2,
            excluded_repository_count=0,
            jira_project_count=2,
            raw_pull_request_count=24,
            raw_commit_count=30,
            raw_deployment_count=4,
            raw_jira_issue_count=12,
            normalized_pull_request_count=20,
            normalized_commit_count=18,
            normalized_deployment_count=4,
            normalized_jira_issue_count=10,
            matched_developer_count=3,
            unmatched_record_count=1,
            aggregate_row_count=9,
            delivery_metric_row_count=2,
            persisted_row_count=123,
            messages=(),
        )


class SyncMetricsJobIntegrationTest(unittest.TestCase):
    def test_main_reports_github_path_and_status_code(self) -> None:
        stderr = StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(f"{temp_dir}/workload.sqlite3")
            argv = [
                "sync_metrics",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-03-31",
                "--granularity",
                "week",
            ]
            with (
                patch.object(sync_metrics, "load_settings", return_value=settings),
                patch.object(sync_metrics, "WorkloadSyncPipeline", FailingPipeline),
                patch.object(sys, "argv", argv),
                redirect_stderr(stderr),
            ):
                exit_code = sync_metrics.main()

        self.assertEqual(exit_code, 1)
        error_payload = json.loads(stderr.getvalue())
        self.assertEqual(error_payload["stage"], "github_pull_requests")
        self.assertEqual(error_payload["status_code"], 404)
        self.assertEqual(error_payload["path"], "/repos/org/missing/pulls")

    def test_main_can_emit_progress_lines_to_stderr(self) -> None:
        stderr = StringIO()
        stdout = StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(f"{temp_dir}/workload.sqlite3")
            argv = [
                "sync_metrics",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-03-31",
                "--granularity",
                "week",
                "--progress",
            ]
            with (
                patch.object(sync_metrics, "load_settings", return_value=settings),
                patch.object(sync_metrics, "WorkloadSyncPipeline", SuccessfulPipeline),
                patch.object(sys, "argv", argv),
                redirect_stderr(stderr),
                redirect_stdout(stdout),
            ):
                exit_code = sync_metrics.main()

        self.assertEqual(exit_code, 0)
        self.assertIn("Fetching GitHub pull requests", stderr.getvalue())
        self.assertIn("Fetched 24 merged pull requests", stderr.getvalue())
        output_payload = json.loads(stdout.getvalue())
        self.assertEqual(output_payload["run_id"], "sync-run-1")


if __name__ == "__main__":
    unittest.main()
