from __future__ import annotations

from datetime import date
import tempfile
import unittest

from workload_analytics.config import Granularity
from workload_analytics.pipelines.sync_pipeline import SyncExecutionError, WorkloadSyncPipeline
from workload_analytics.storage import SQLiteStore
from tests.integration.test_sync_pipeline import _build_settings


class FailingGithubClient:
    def fetch_merged_pull_requests(self, *, repositories, merged_from, merged_to):
        del repositories, merged_from, merged_to
        raise RuntimeError("invalid GitHub token")

    def fetch_commits_landed(self, *, repositories, committed_from, committed_to):
        del repositories, committed_from, committed_to
        raise AssertionError("Should not reach commit fetch after PR failure")


class EmptyGithubClient:
    def fetch_merged_pull_requests(self, *, repositories, merged_from, merged_to):
        del repositories, merged_from, merged_to
        return ()

    def fetch_commits_landed(self, *, repositories, committed_from, committed_to):
        del repositories, committed_from, committed_to
        return ()

    def fetch_deployments(self, *, repositories, deployed_from, deployed_to):
        del repositories, deployed_from, deployed_to
        return ()


class EmptyJiraClient:
    def fetch_assigned_issues(self, *, projects, updated_from, updated_to):
        del projects, updated_from, updated_to
        return ()


class SyncFailuresIntegrationTest(unittest.TestCase):
    def test_pipeline_wraps_provider_failures_with_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(f"{temp_dir}/workload.sqlite3")
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            store.initialize()
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=FailingGithubClient(),
                jira_client=EmptyJiraClient(),
                store=store,
            )

            with self.assertRaises(SyncExecutionError) as context:
                pipeline.run(
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 4, 30),
                    granularity=Granularity.WEEK,
                )

            self.assertEqual(context.exception.stage, "github_pull_requests")
            self.assertIn("invalid GitHub token", str(context.exception))
            self.assertEqual(store.table_row_count("sync_runs"), 0)
            self.assertEqual(store.table_row_count("developer_period_metrics"), 0)

    def test_pipeline_reports_empty_windows_as_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _build_settings(f"{temp_dir}/workload.sqlite3")
            store = SQLiteStore(sqlite_path=settings.storage.sqlite_path)
            pipeline = WorkloadSyncPipeline(
                settings=settings,
                github_client=EmptyGithubClient(),
                jira_client=EmptyJiraClient(),
                store=store,
            )

            summary = pipeline.run(
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                granularity=Granularity.WEEK,
            )

            self.assertEqual(
                summary.messages,
                ("No workload records matched the selected date range.",),
            )
            self.assertEqual(summary.aggregate_row_count, 0)
            self.assertEqual(store.table_row_count("sync_runs"), 1)


if __name__ == "__main__":
    unittest.main()
