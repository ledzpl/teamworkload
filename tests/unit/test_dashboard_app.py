from __future__ import annotations

import os
import unittest

from workload_analytics.dashboard.app import (
    DashboardArgumentError,
    DashboardConfigError,
    load_dashboard_runtime_settings,
    resolve_dashboard_sqlite_path,
)


class DashboardAppArgumentTest(unittest.TestCase):
    def test_load_dashboard_runtime_settings_uses_dashboard_only_env(self) -> None:
        original_environ = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(
                {
                    "WORKLOAD_SQLITE_PATH": "var/custom.sqlite3",
                    "WORKLOAD_TEAM_MEMBERS": "Engineer@example.com, analyst@example.com",
                }
            )

            settings = load_dashboard_runtime_settings()

            self.assertEqual(settings.sqlite_path, "var/custom.sqlite3")
            self.assertEqual(
                settings.team_members,
                ("engineer@example.com", "analyst@example.com"),
            )
        finally:
            os.environ.clear()
            os.environ.update(original_environ)

    def test_load_dashboard_runtime_settings_rejects_invalid_team_member_email(self) -> None:
        original_environ = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(
                {
                    "WORKLOAD_TEAM_MEMBERS": "engineer@example.com, not-an-email",
                }
            )

            with self.assertRaises(DashboardConfigError) as context:
                load_dashboard_runtime_settings()

            self.assertIn("Invalid team member email", str(context.exception))
        finally:
            os.environ.clear()
            os.environ.update(original_environ)

    def test_resolve_dashboard_sqlite_path_uses_default_when_option_missing(self) -> None:
        sqlite_path = resolve_dashboard_sqlite_path(
            argv=("app.py",),
            default_sqlite_path="var/default.sqlite3",
        )

        self.assertEqual(sqlite_path, "var/default.sqlite3")

    def test_resolve_dashboard_sqlite_path_prefers_explicit_option(self) -> None:
        sqlite_path = resolve_dashboard_sqlite_path(
            argv=("app.py", "--sqlite-path", "/tmp/custom.sqlite3"),
            default_sqlite_path="var/default.sqlite3",
        )

        self.assertEqual(sqlite_path, "/tmp/custom.sqlite3")

    def test_resolve_dashboard_sqlite_path_reports_invalid_argument_usage(self) -> None:
        with self.assertRaises(DashboardArgumentError) as context:
            resolve_dashboard_sqlite_path(
                argv=("app.py", "--sqlite-path"),
                default_sqlite_path="var/default.sqlite3",
            )

        self.assertIn("Invalid dashboard arguments.", str(context.exception))


if __name__ == "__main__":
    unittest.main()
