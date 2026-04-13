from __future__ import annotations

from datetime import UTC, date, datetime
import tempfile
import unittest

from workload_analytics.config import Granularity
from workload_analytics.dashboard.charts import (
    _moving_average,
    build_commit_heatmap_figure,
    build_developer_focus_figure,
)
from workload_analytics.dashboard.queries import (
    CommitHeatmapCell,
    DeveloperFocusRow,
    load_commit_heatmap,
    load_developer_focus,
)
from workload_analytics.models import DeveloperPeriodMetrics, GithubCommitEvent
from workload_analytics.storage import SQLiteStore


def _seed_store_with_commits(sqlite_path: str) -> SQLiteStore:
    store = SQLiteStore(sqlite_path=sqlite_path)
    store.replace_sync_snapshot(
        run_id="test-run",
        started_at=datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 10, 9, 1, tzinfo=UTC),
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        granularity=Granularity.WEEK,
        raw_pull_requests=(),
        raw_commits=(),
        raw_jira_issues=(),
        normalized_pull_requests=(),
        normalized_commits=(
            # Monday 9am
            GithubCommitEvent(
                repository="org/repo-a",
                commit_sha="aaa1",
                author_email="dev@example.com",
                committed_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
                lines_added=10,
                lines_deleted=2,
            ),
            # Monday 9am - same dev, different repo
            GithubCommitEvent(
                repository="org/repo-b",
                commit_sha="bbb1",
                author_email="dev@example.com",
                committed_at=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
                lines_added=5,
                lines_deleted=1,
            ),
            # Tuesday 14pm
            GithubCommitEvent(
                repository="org/repo-a",
                commit_sha="aaa2",
                author_email="dev@example.com",
                committed_at=datetime(2026, 4, 7, 14, 0, tzinfo=UTC),
                lines_added=20,
                lines_deleted=5,
            ),
            # Saturday 23pm (weekend/late)
            GithubCommitEvent(
                repository="org/repo-a",
                commit_sha="aaa3",
                author_email="dev@example.com",
                committed_at=datetime(2026, 4, 11, 23, 0, tzinfo=UTC),
                lines_added=3,
                lines_deleted=0,
            ),
            # Different developer, Wednesday 10am
            GithubCommitEvent(
                repository="org/repo-c",
                commit_sha="ccc1",
                author_email="other@example.com",
                committed_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                lines_added=15,
                lines_deleted=3,
            ),
        ),
        normalized_jira_issues=(),
        aggregates=(
            DeveloperPeriodMetrics(
                granularity=Granularity.WEEK,
                developer_email="dev@example.com",
                period_start=date(2026, 4, 6),
                period_end=date(2026, 4, 12),
                github_prs_merged=0,
                github_commits_landed=4,
                github_lines_added=38,
                github_lines_deleted=8,
                jira_issues_assigned=0,
            ),
        ),
        github_repository_count=3,
        discovered_repository_count=3,
        excluded_repository_count=0,
        jira_project_count=0,
        matched_developer_count=2,
        unmatched_record_count=0,
        persisted_row_count=1,
    )
    return store


class MovingAverageTest(unittest.TestCase):
    def test_basic_moving_average(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _moving_average(values, window=3)
        self.assertEqual(result[0], None)
        self.assertEqual(result[1], None)
        self.assertAlmostEqual(result[2], 2.0)
        self.assertAlmostEqual(result[3], 3.0)
        self.assertAlmostEqual(result[4], 4.0)

    def test_window_one_returns_original(self) -> None:
        values = [10.0, 20.0, 30.0]
        result = _moving_average(values, window=1)
        self.assertEqual(result, [10.0, 20.0, 30.0])

    def test_empty_values(self) -> None:
        result = _moving_average([], window=3)
        self.assertEqual(result, [])

    def test_window_larger_than_data(self) -> None:
        values = [1.0, 2.0]
        result = _moving_average(values, window=5)
        self.assertEqual(result, [None, None])

    def test_default_window(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        result = _moving_average(values)
        # default window = 4
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertIsNone(result[2])
        self.assertAlmostEqual(result[3], 2.5)  # (1+2+3+4)/4


class CommitHeatmapTest(unittest.TestCase):
    def test_load_commit_heatmap_returns_grouped_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_store_with_commits(sqlite_path)

            cells = load_commit_heatmap(
                sqlite_path=sqlite_path,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
            )

            self.assertGreater(len(cells), 0)
            # Monday 9am UTC → Monday 18시 KST (dow=1, hour=18)
            # Two commits from dev@example.com at 09:00 and 09:30 UTC
            monday_18 = [c for c in cells if c.day_of_week == 1 and c.hour == 18]
            self.assertEqual(len(monday_18), 1)
            self.assertEqual(monday_18[0].commit_count, 2)
            self.assertEqual(monday_18[0].day_total, 2)

            # Saturday 23pm UTC → Sunday 8시 KST (dow=0, hour=8)
            sunday_8 = [c for c in cells if c.day_of_week == 0 and c.hour == 8]
            self.assertEqual(len(sunday_8), 1)
            self.assertEqual(sunday_8[0].commit_count, 1)
            self.assertEqual(sunday_8[0].day_total, 1)

    def test_load_commit_heatmap_filters_by_developer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_store_with_commits(sqlite_path)

            cells = load_commit_heatmap(
                sqlite_path=sqlite_path,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                developer_email="other@example.com",
            )

            total = sum(c.commit_count for c in cells)
            self.assertEqual(total, 1)
            self.assertTrue(all(c.day_total == 1 for c in cells))

    def test_load_commit_heatmap_empty_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_store_with_commits(sqlite_path)

            cells = load_commit_heatmap(
                sqlite_path=sqlite_path,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

            self.assertEqual(cells, ())

    def test_build_commit_heatmap_figure_renders(self) -> None:
        cells = (
            CommitHeatmapCell(day_of_week=1, hour=9, commit_count=5),
            CommitHeatmapCell(day_of_week=3, hour=14, commit_count=3),
        )
        figure = build_commit_heatmap_figure(cells)
        self.assertEqual(figure.layout.title.text, "커밋 시간대 히트맵 (KST)")
        self.assertEqual(
            tuple(figure.data[0].y),
            ("월 합계 5", "화 합계 0", "수 합계 3", "목 합계 0", "금 합계 0", "토 합계 0", "일 합계 0"),
        )
        self.assertIn("요일 합계: 5건", figure.data[0].text[0][9])

    def test_build_commit_heatmap_figure_empty(self) -> None:
        figure = build_commit_heatmap_figure(())
        # Should return empty figure with annotation
        self.assertEqual(len(figure.data), 0)


class DeveloperFocusTest(unittest.TestCase):
    def test_load_developer_focus_counts_repos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_store_with_commits(sqlite_path)

            rows = load_developer_focus(
                sqlite_path=sqlite_path,
                granularity=Granularity.WEEK,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
            )

            # dev@example.com has repos a and b in same period
            dev_rows = [r for r in rows if r.developer_email == "dev@example.com"]
            self.assertEqual(len(dev_rows), 1)
            self.assertEqual(dev_rows[0].active_repo_count, 2)
            self.assertIn("org/repo-a", dev_rows[0].repo_names)
            self.assertIn("org/repo-b", dev_rows[0].repo_names)

            # other@example.com has only repo-c
            other_rows = [r for r in rows if r.developer_email == "other@example.com"]
            self.assertEqual(len(other_rows), 1)
            self.assertEqual(other_rows[0].active_repo_count, 1)

    def test_load_developer_focus_filters_by_developer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = f"{temp_dir}/workload.sqlite3"
            _seed_store_with_commits(sqlite_path)

            rows = load_developer_focus(
                sqlite_path=sqlite_path,
                granularity=Granularity.WEEK,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                developer_email="other@example.com",
            )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].developer_email, "other@example.com")

    def test_build_developer_focus_figure_renders(self) -> None:
        rows = (
            DeveloperFocusRow(
                developer_email="dev@example.com",
                period_start=date(2026, 4, 6),
                period_end=date(2026, 4, 12),
                active_repo_count=3,
                repo_names=("a", "b", "c"),
            ),
        )
        figure = build_developer_focus_figure(rows)
        self.assertEqual(figure.layout.title.text, "개발자 포커스 타임")

    def test_build_developer_focus_figure_empty(self) -> None:
        figure = build_developer_focus_figure(())
        self.assertEqual(len(figure.data), 0)


if __name__ == "__main__":
    unittest.main()
