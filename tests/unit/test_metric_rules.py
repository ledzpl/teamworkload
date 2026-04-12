from __future__ import annotations

import unittest

from workload_analytics.pipelines.metric_rules import (
    FileChange,
    should_exclude_commit,
    should_exclude_file_path,
    summarize_github_changes,
)


class MetricRulesTest(unittest.TestCase):
    def test_summarize_github_changes_applies_default_exclusions(self) -> None:
        summary = summarize_github_changes(
            [
                FileChange("src/app.py", 10, 2),
                FileChange("package-lock.json", 100, 50),
                FileChange("vendor/jquery.js", 250, 0),
                FileChange("dist/app.js", 40, 4),
                FileChange("src/types.generated.ts", 20, 10),
            ],
            is_merge_commit=False,
        )

        self.assertEqual(summary.lines_added, 10)
        self.assertEqual(summary.lines_deleted, 2)
        self.assertEqual(summary.included_paths, ("src/app.py",))
        self.assertEqual(
            summary.excluded_paths,
            (
                "package-lock.json",
                "vendor/jquery.js",
                "dist/app.js",
                "src/types.generated.ts",
            ),
        )

    def test_merge_commits_are_excluded(self) -> None:
        summary = summarize_github_changes(
            [FileChange("src/app.py", 10, 2)],
            is_merge_commit=should_exclude_commit(parent_count=2),
        )

        self.assertEqual(summary.lines_added, 0)
        self.assertEqual(summary.lines_deleted, 0)
        self.assertEqual(summary.included_paths, ())
        self.assertEqual(summary.excluded_paths, ("src/app.py",))

    def test_should_exclude_file_path_handles_known_patterns(self) -> None:
        self.assertTrue(should_exclude_file_path("node_modules/react/index.js"))
        self.assertTrue(should_exclude_file_path("coverage/index.html"))
        self.assertTrue(should_exclude_file_path("src/schema.pb.go"))
        self.assertFalse(should_exclude_file_path("src/service.py"))


if __name__ == "__main__":
    unittest.main()
