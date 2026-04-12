from __future__ import annotations

import unittest

from workload_analytics.config import ConfigError, Granularity, load_settings


class LoadSettingsTest(unittest.TestCase):
    def test_load_settings_builds_expected_models(self) -> None:
        settings = load_settings(
            {
                "WORKLOAD_TEAM_NAME": "Data Platform",
                "WORKLOAD_GITHUB_REPOSITORIES": "org/api, org/web, org/api",
                "WORKLOAD_JIRA_PROJECTS": "eng, data_ops, eng",
                "WORKLOAD_TEAM_MEMBERS": "Lead.Engineer@example.com, analyst@example.com, lead.engineer@example.com",
                "WORKLOAD_LOOKBACK_DAYS": "60",
                "WORKLOAD_DEFAULT_GRANULARITY": "month",
                "WORKLOAD_ALLOWED_GRANULARITIES": "week,month",
                "GITHUB_TOKEN": "github-token",
                "JIRA_BASE_URL": "https://jira.example.com/",
                "JIRA_USER_EMAIL": "Lead.Engineer@example.com",
                "JIRA_API_TOKEN": "jira-token",
                "WORKLOAD_SQLITE_PATH": "var/test-workload.sqlite3",
            }
        )

        self.assertEqual(settings.team_scope.team_name, "Data Platform")
        self.assertEqual(
            settings.team_scope.github_repositories,
            ("org/api", "org/web"),
        )
        self.assertEqual(settings.team_scope.jira_projects, ("ENG", "DATA_OPS"))
        self.assertEqual(
            settings.team_scope.team_members,
            ("lead.engineer@example.com", "analyst@example.com"),
        )
        self.assertEqual(settings.github.token, "github-token")
        self.assertEqual(settings.github.base_url, "https://api.github.com")
        self.assertEqual(settings.jira.base_url, "https://jira.example.com")
        self.assertEqual(settings.jira.user_email, "lead.engineer@example.com")
        self.assertEqual(settings.date_defaults.lookback_days, 60)
        self.assertEqual(settings.date_defaults.default_granularity, Granularity.MONTH)
        self.assertEqual(settings.storage.sqlite_path, "var/test-workload.sqlite3")
        self.assertEqual(
            settings.date_defaults.allowed_granularities,
            (Granularity.WEEK, Granularity.MONTH),
        )

    def test_github_api_base_url_can_be_overridden(self) -> None:
        settings = load_settings(
            {
                "WORKLOAD_TEAM_NAME": "Platform",
                "WORKLOAD_GITHUB_REPOSITORIES": "org/api",
                "WORKLOAD_JIRA_PROJECTS": "ENG",
                "GITHUB_TOKEN": "github-token",
                "GITHUB_API_BASE_URL": "https://github.example.com/api/v3/",
                "JIRA_BASE_URL": "https://jira.example.com",
                "JIRA_USER_EMAIL": "engineer@example.com",
                "JIRA_API_TOKEN": "jira-token",
            }
        )

        self.assertEqual(
            settings.github.base_url,
            "https://github.example.com/api/v3",
        )

    def test_load_settings_supports_github_organization_scope(self) -> None:
        settings = load_settings(
            {
                "WORKLOAD_TEAM_NAME": "Platform",
                "WORKLOAD_GITHUB_ORGANIZATION": "OpenAI-Platform",
                "WORKLOAD_JIRA_PROJECTS": "ENG",
                "WORKLOAD_TEAM_MEMBERS": "engineer@example.com, analyst@example.com",
                "GITHUB_TOKEN": "github-token",
                "JIRA_BASE_URL": "https://jira.example.com",
                "JIRA_USER_EMAIL": "engineer@example.com",
                "JIRA_API_TOKEN": "jira-token",
            }
        )

        self.assertEqual(settings.team_scope.github_organization, "OpenAI-Platform")
        self.assertEqual(settings.team_scope.github_repositories, ())
        self.assertEqual(
            settings.team_scope.team_members,
            ("engineer@example.com", "analyst@example.com"),
        )

    def test_org_scope_requires_team_members(self) -> None:
        with self.assertRaises(ConfigError) as context:
            load_settings(
                {
                    "WORKLOAD_TEAM_NAME": "Platform",
                    "WORKLOAD_GITHUB_ORGANIZATION": "platform",
                    "WORKLOAD_JIRA_PROJECTS": "ENG",
                    "GITHUB_TOKEN": "github-token",
                    "JIRA_BASE_URL": "https://jira.example.com",
                    "JIRA_USER_EMAIL": "engineer@example.com",
                    "JIRA_API_TOKEN": "jira-token",
                }
            )

        self.assertIn(
            "WORKLOAD_TEAM_MEMBERS must contain at least one team member email when WORKLOAD_GITHUB_ORGANIZATION is set.",
            str(context.exception),
        )

    def test_invalid_github_api_base_url_is_reported(self) -> None:
        with self.assertRaises(ConfigError) as context:
            load_settings(
                {
                    "WORKLOAD_TEAM_NAME": "Platform",
                    "WORKLOAD_GITHUB_REPOSITORIES": "org/api",
                    "WORKLOAD_JIRA_PROJECTS": "ENG",
                    "GITHUB_TOKEN": "github-token",
                    "GITHUB_API_BASE_URL": "github.example.com/api/v3",
                    "JIRA_BASE_URL": "https://jira.example.com",
                    "JIRA_USER_EMAIL": "engineer@example.com",
                    "JIRA_API_TOKEN": "jira-token",
                }
            )

        self.assertIn(
            "GITHUB_API_BASE_URL must be a valid http or https URL.",
            str(context.exception),
        )

    def test_invalid_team_member_email_is_reported(self) -> None:
        with self.assertRaises(ConfigError) as context:
            load_settings(
                {
                    "WORKLOAD_TEAM_NAME": "Platform",
                    "WORKLOAD_GITHUB_REPOSITORIES": "org/api",
                    "WORKLOAD_JIRA_PROJECTS": "ENG",
                    "WORKLOAD_TEAM_MEMBERS": "engineer@example.com, not-an-email",
                    "GITHUB_TOKEN": "github-token",
                    "JIRA_BASE_URL": "https://jira.example.com",
                    "JIRA_USER_EMAIL": "engineer@example.com",
                    "JIRA_API_TOKEN": "jira-token",
                }
            )

        self.assertIn(
            "Invalid team member email 'not-an-email'. Expected a valid email address.",
            str(context.exception),
        )

    def test_load_settings_reports_missing_and_invalid_values(self) -> None:
        with self.assertRaises(ConfigError) as context:
            load_settings(
                {
                    "WORKLOAD_TEAM_NAME": "   ",
                    "WORKLOAD_GITHUB_REPOSITORIES": "missing-slash",
                    "WORKLOAD_JIRA_PROJECTS": "bad key",
                    "WORKLOAD_LOOKBACK_DAYS": "0",
                    "WORKLOAD_DEFAULT_GRANULARITY": "quarter",
                    "WORKLOAD_ALLOWED_GRANULARITIES": "",
                    "GITHUB_TOKEN": "",
                    "JIRA_BASE_URL": "jira.example.com",
                    "JIRA_USER_EMAIL": "not-an-email",
                    "JIRA_API_TOKEN": "",
                }
            )

        error_message = str(context.exception)
        self.assertIn("WORKLOAD_TEAM_NAME is required.", error_message)
        self.assertIn("GITHUB_TOKEN is required.", error_message)
        self.assertIn("JIRA_API_TOKEN is required.", error_message)
        self.assertIn(
            "Invalid GitHub repository slug 'missing-slash'. Expected 'owner/repository'.",
            error_message,
        )
        self.assertIn(
            "Invalid Jira project key 'bad key'. Expected uppercase letters, numbers, or underscores.",
            error_message,
        )
        self.assertIn(
            "WORKLOAD_ALLOWED_GRANULARITIES must contain at least one granularity.",
            error_message,
        )
        self.assertIn(
            "WORKLOAD_DEFAULT_GRANULARITY must be one of day, week, month.",
            error_message,
        )
        self.assertIn("WORKLOAD_LOOKBACK_DAYS must be greater than zero.", error_message)
        self.assertIn("JIRA_BASE_URL must be a valid http or https URL.", error_message)
        self.assertIn("JIRA_USER_EMAIL must be a valid email address.", error_message)

    def test_default_granularity_must_be_in_allowed_granularities(self) -> None:
        with self.assertRaises(ConfigError) as context:
            load_settings(
                {
                    "WORKLOAD_TEAM_NAME": "Platform",
                    "WORKLOAD_GITHUB_REPOSITORIES": "org/api",
                    "WORKLOAD_JIRA_PROJECTS": "ENG",
                    "WORKLOAD_LOOKBACK_DAYS": "90",
                    "WORKLOAD_DEFAULT_GRANULARITY": "day",
                    "WORKLOAD_ALLOWED_GRANULARITIES": "week,month",
                    "GITHUB_TOKEN": "github-token",
                    "JIRA_BASE_URL": "https://jira.example.com",
                    "JIRA_USER_EMAIL": "engineer@example.com",
                    "JIRA_API_TOKEN": "jira-token",
                }
            )

        self.assertIn(
            "WORKLOAD_DEFAULT_GRANULARITY must be one of week, month.",
            str(context.exception),
        )


if __name__ == "__main__":
    unittest.main()
