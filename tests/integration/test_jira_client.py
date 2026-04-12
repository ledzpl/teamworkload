from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import unittest

from workload_analytics.clients.jira_client import JiraClient, JiraTransportResponse


class FakeJiraTransport:
    def __init__(self, responses: Mapping[tuple[str, tuple[tuple[str, str], ...]], JiraTransportResponse]) -> None:
        self._responses = dict(responses)
        self.calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> JiraTransportResponse:
        key = (path, tuple(sorted(params.items())))
        self.calls.append(key)
        return self._responses[key]


class JiraClientIntegrationTest(unittest.TestCase):
    def test_fetch_assigned_issues_across_multiple_projects(self) -> None:
        updated_from = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        updated_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = FakeJiraTransport(
            {
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", 'project = "ENG" AND assignee IS NOT EMPTY AND updated >= "2026-04-01 00:00" AND updated <= "2026-04-30 23:59" ORDER BY updated DESC'),
                        ("maxResults", "50"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "isLast": True,
                        "issues": [
                            {
                                "key": "ENG-101",
                                "fields": {
                                    "project": {"key": "ENG"},
                                    "assignee": {
                                        "emailAddress": "Engineer@example.com",
                                        "displayName": "Engineer One",
                                    },
                                    "status": {"name": "In Progress"},
                                    "updated": "2026-04-04T08:30:00Z",
                                },
                            }
                        ],
                    },
                    headers={},
                ),
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", 'project = "WEB" AND assignee IS NOT EMPTY AND updated >= "2026-04-01 00:00" AND updated <= "2026-04-30 23:59" ORDER BY updated DESC'),
                        ("maxResults", "50"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "isLast": True,
                        "issues": [
                            {
                                "key": "WEB-12",
                                "fields": {
                                    "project": {"key": "WEB"},
                                    "assignee": {
                                        "emailAddress": "web@example.com",
                                        "displayName": "Web Dev",
                                    },
                                    "status": {"name": "Ready for QA"},
                                    "updated": "2026-04-08T14:00:00Z",
                                },
                            }
                        ],
                    },
                    headers={},
                ),
            }
        )
        client = JiraClient(
            base_url="https://jira.example.com",
            user_email="jira@example.com",
            api_token="token",
            transport=transport,
        )

        issues = client.fetch_assigned_issues(
            projects=("ENG", "WEB"),
            updated_from=updated_from,
            updated_to=updated_to,
        )

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].issue_key, "ENG-101")
        self.assertEqual(issues[0].assignee_email, "engineer@example.com")
        self.assertEqual(issues[1].issue_key, "WEB-12")
        self.assertEqual(issues[1].status_name, "Ready for QA")

    def test_fetch_assigned_issues_paginates_with_next_page_token(self) -> None:
        updated_from = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        updated_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        jql = 'project = "ENG" AND assignee IS NOT EMPTY AND updated >= "2026-04-01 00:00" AND updated <= "2026-04-30 23:59" ORDER BY updated DESC'
        transport = FakeJiraTransport(
            {
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", jql),
                        ("maxResults", "1"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "isLast": False,
                        "issues": [
                            {
                                "key": "ENG-101",
                                "fields": {
                                    "project": {"key": "ENG"},
                                    "assignee": {"emailAddress": "one@example.com"},
                                    "status": {"name": "In Progress"},
                                    "updated": "2026-04-01T09:00:00Z",
                                },
                            }
                        ],
                        "nextPageToken": "page-2",
                    },
                    headers={},
                ),
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", jql),
                        ("maxResults", "1"),
                        ("nextPageToken", "page-2"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "isLast": True,
                        "issues": [
                            {
                                "key": "ENG-102",
                                "fields": {
                                    "project": {"key": "ENG"},
                                    "assignee": {"emailAddress": "two@example.com"},
                                    "status": {"name": "Review"},
                                    "updated": "2026-04-02T09:00:00Z",
                                },
                            }
                        ],
                    },
                    headers={},
                ),
            }
        )
        client = JiraClient(
            base_url="https://jira.example.com",
            user_email="jira@example.com",
            api_token="token",
            transport=transport,
            page_size=1,
        )

        issues = client.fetch_assigned_issues(
            projects=("ENG",),
            updated_from=updated_from,
            updated_to=updated_to,
        )

        self.assertEqual([issue.issue_key for issue in issues], ["ENG-101", "ENG-102"])

    def test_fetch_assigned_issues_supports_legacy_total_pagination_shape(self) -> None:
        updated_from = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        updated_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        jql = 'project = "ENG" AND assignee IS NOT EMPTY AND updated >= "2026-04-01 00:00" AND updated <= "2026-04-30 23:59" ORDER BY updated DESC'
        transport = FakeJiraTransport(
            {
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", jql),
                        ("maxResults", "1"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "total": 1,
                        "issues": [
                            {
                                "key": "ENG-101",
                                "fields": {
                                    "project": {"key": "ENG"},
                                    "assignee": {"emailAddress": "one@example.com"},
                                    "status": {"name": "To Do"},
                                    "updated": "2026-04-01T09:00:00Z",
                                },
                            }
                        ],
                    },
                    headers={},
                ),
            }
        )
        client = JiraClient(
            base_url="https://jira.example.com",
            user_email="jira@example.com",
            api_token="token",
            transport=transport,
            page_size=1,
        )

        issues = client.fetch_assigned_issues(
            projects=("ENG",),
            updated_from=updated_from,
            updated_to=updated_to,
        )

        self.assertEqual([issue.issue_key for issue in issues], ["ENG-101"])

    def test_fetch_assigned_issues_advances_start_at_for_legacy_pagination(self) -> None:
        updated_from = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        updated_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        jql = 'project = "ENG" AND assignee IS NOT EMPTY AND updated >= "2026-04-01 00:00" AND updated <= "2026-04-30 23:59" ORDER BY updated DESC'
        transport = FakeJiraTransport(
            {
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", jql),
                        ("maxResults", "1"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "total": 2,
                        "issues": [
                            {
                                "key": "ENG-101",
                                "fields": {
                                    "project": {"key": "ENG"},
                                    "assignee": {"emailAddress": "one@example.com"},
                                    "status": {"name": "To Do"},
                                    "updated": "2026-04-01T09:00:00Z",
                                },
                            }
                        ],
                    },
                    headers={},
                ),
                (
                    "/rest/api/3/search/jql",
                    (
                        ("fields", "key,project,assignee,status,updated"),
                        ("jql", jql),
                        ("maxResults", "1"),
                        ("startAt", "1"),
                    ),
                ): JiraTransportResponse(
                    status_code=200,
                    payload={
                        "total": 2,
                        "issues": [
                            {
                                "key": "ENG-102",
                                "fields": {
                                    "project": {"key": "ENG"},
                                    "assignee": {"emailAddress": "two@example.com"},
                                    "status": {"name": "In Progress"},
                                    "updated": "2026-04-02T09:00:00Z",
                                },
                            }
                        ],
                    },
                    headers={},
                ),
            }
        )
        client = JiraClient(
            base_url="https://jira.example.com",
            user_email="jira@example.com",
            api_token="token",
            transport=transport,
            page_size=1,
        )

        issues = client.fetch_assigned_issues(
            projects=("ENG",),
            updated_from=updated_from,
            updated_to=updated_to,
        )

        self.assertEqual([issue.issue_key for issue in issues], ["ENG-101", "ENG-102"])


if __name__ == "__main__":
    unittest.main()
