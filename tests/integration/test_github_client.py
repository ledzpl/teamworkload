from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import threading
import time
import unittest

from workload_analytics.clients.github_client import (
    GithubApiError,
    GithubClient,
    GithubDeploymentPayload,
    GithubRepositoryPayload,
    GithubRateLimitError,
    GithubTransportResponse,
)


class FakeGithubTransport:
    def __init__(self, responses: Mapping[tuple[str, tuple[tuple[str, str], ...]], GithubTransportResponse]) -> None:
        self._responses = dict(responses)
        self.calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> GithubTransportResponse:
        key = (path, tuple(sorted(params.items())))
        self.calls.append(key)
        if key not in self._responses and path.endswith("/reviews"):
            return GithubTransportResponse(status_code=200, payload=[], headers={})
        return self._responses[key]


class SlowGithubTransport(FakeGithubTransport):
    def __init__(
        self,
        responses: Mapping[tuple[str, tuple[tuple[str, str], ...]], GithubTransportResponse],
        *,
        delay_seconds: float,
    ) -> None:
        super().__init__(responses)
        self._delay_seconds = delay_seconds
        self._lock = threading.Lock()
        self._active_requests = 0
        self.max_active_requests = 0

    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> GithubTransportResponse:
        del headers
        key = (path, tuple(sorted(params.items())))
        with self._lock:
            self.calls.append(key)
            self._active_requests += 1
            self.max_active_requests = max(
                self.max_active_requests,
                self._active_requests,
            )
        time.sleep(self._delay_seconds)
        try:
            if key not in self._responses and path.endswith("/reviews"):
                return GithubTransportResponse(status_code=200, payload=[], headers={})
            return self._responses[key]
        finally:
            with self._lock:
                self._active_requests -= 1


class GithubClientIntegrationTest(unittest.TestCase):
    def test_fetch_merged_pull_requests_across_multiple_repositories(self) -> None:
        merged_from = datetime(2026, 4, 1, tzinfo=UTC)
        merged_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "number": 101,
                            "created_at": "2026-04-02T09:00:00Z",
                            "merged_at": "2026-04-03T10:00:00Z",
                            "user": {"login": "api-dev"},
                        },
                        {
                            "number": 102,
                            "merged_at": None,
                            "user": {"login": "not-merged"},
                        },
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/files",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"filename": "src/app.py", "additions": 12, "deletions": 2},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/commits",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"commit": {"author": {"email": "api.dev@example.com"}}},
                        {"commit": {"author": {"email": "api.dev@example.com"}}},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/reviews",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"state": "COMMENTED", "submitted_at": "2026-04-03T11:00:00Z"},
                        {"state": "APPROVED", "submitted_at": "2026-04-03T12:30:00Z"},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/web/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "number": 77,
                            "created_at": "2026-04-11T09:00:00Z",
                            "merged_at": "2026-04-12T09:30:00Z",
                            "user": {"login": "web-dev"},
                        }
                    ],
                    headers={},
                ),
                (
                    "/repos/org/web/pulls/77/files",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"filename": "src/page.tsx", "additions": 8, "deletions": 1},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/web/pulls/77/commits",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"commit": {"author": {"email": "web.dev@example.com"}}},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/web/pulls/77/reviews",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[],
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        pull_requests = client.fetch_merged_pull_requests(
            repositories=("org/api", "org/web"),
            merged_from=merged_from,
            merged_to=merged_to,
        )

        self.assertEqual(len(pull_requests), 2)
        self.assertEqual(pull_requests[0].repository, "org/api")
        self.assertEqual(pull_requests[0].commit_author_emails, ("api.dev@example.com",))
        self.assertEqual(
            pull_requests[0].created_at,
            datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        )
        self.assertEqual(
            pull_requests[0].first_reviewed_at,
            datetime(2026, 4, 3, 11, 0, tzinfo=UTC),
        )
        self.assertEqual(pull_requests[1].repository, "org/web")
        self.assertIsNone(pull_requests[1].first_reviewed_at)
        self.assertEqual(pull_requests[1].files[0].path, "src/page.tsx")

    def test_fetch_merged_pull_requests_stops_pagination_when_updated_at_is_older_than_window(self) -> None:
        merged_from = datetime(2026, 4, 1, tzinfo=UTC)
        merged_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "number": 101,
                            "merged_at": "2026-04-03T10:00:00Z",
                            "updated_at": "2026-04-03T12:00:00Z",
                            "user": {"login": "api-dev"},
                        },
                        {
                            "number": 88,
                            "merged_at": "2026-03-20T10:00:00Z",
                            "updated_at": "2026-03-20T10:30:00Z",
                            "user": {"login": "old-dev"},
                        },
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/files",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"filename": "src/app.py", "additions": 12, "deletions": 2},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/commits",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {"commit": {"author": {"email": "api.dev@example.com"}}},
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "2"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "number": 77,
                            "merged_at": "2026-02-10T10:00:00Z",
                            "updated_at": "2026-02-10T10:30:00Z",
                            "user": {"login": "older-dev"},
                        }
                    ],
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        pull_requests = client.fetch_merged_pull_requests(
            repositories=("org/api",),
            merged_from=merged_from,
            merged_to=merged_to,
        )

        self.assertEqual(len(pull_requests), 1)
        self.assertNotIn(
            (
                "/repos/org/api/pulls",
                (
                    ("direction", "desc"),
                    ("page", "2"),
                    ("per_page", "100"),
                    ("sort", "updated"),
                    ("state", "closed"),
                ),
            ),
            transport.calls,
        )

    def test_fetch_merged_pull_requests_fetches_repositories_in_parallel(self) -> None:
        merged_from = datetime(2026, 4, 1, tzinfo=UTC)
        merged_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = SlowGithubTransport(
            {
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[],
                    headers={},
                ),
                (
                    "/repos/org/web/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[],
                    headers={},
                ),
            },
            delay_seconds=0.05,
        )
        client = GithubClient(
            token="token",
            transport=transport,
            max_workers=2,
        )

        client.fetch_merged_pull_requests(
            repositories=("org/api", "org/web"),
            merged_from=merged_from,
            merged_to=merged_to,
        )

        self.assertGreaterEqual(transport.max_active_requests, 2)

    def test_fetch_merged_pull_requests_fetches_pull_request_details_in_parallel(self) -> None:
        merged_from = datetime(2026, 4, 1, tzinfo=UTC)
        merged_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = SlowGithubTransport(
            {
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "number": 101,
                            "merged_at": "2026-04-03T10:00:00Z",
                            "updated_at": "2026-04-03T12:00:00Z",
                            "user": {"login": "api-dev"},
                        },
                        {
                            "number": 102,
                            "merged_at": "2026-04-04T10:00:00Z",
                            "updated_at": "2026-04-04T12:00:00Z",
                            "user": {"login": "api-dev-2"},
                        },
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/files",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[{"filename": "src/a.py", "additions": 12, "deletions": 2}],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/101/commits",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[{"commit": {"author": {"email": "api.dev@example.com"}}}],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/102/files",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[{"filename": "src/b.py", "additions": 6, "deletions": 1}],
                    headers={},
                ),
                (
                    "/repos/org/api/pulls/102/commits",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[{"commit": {"author": {"email": "api.dev2@example.com"}}}],
                    headers={},
                ),
            },
            delay_seconds=0.05,
        )
        client = GithubClient(token="token", transport=transport, max_workers=2)

        pull_requests = client.fetch_merged_pull_requests(
            repositories=("org/api",),
            merged_from=merged_from,
            merged_to=merged_to,
        )

        self.assertEqual(len(pull_requests), 2)
        self.assertGreaterEqual(transport.max_active_requests, 2)

    def test_fetch_commits_landed_paginates_and_loads_commit_details(self) -> None:
        committed_from = datetime(2026, 4, 1, tzinfo=UTC)
        committed_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/commits",
                    (
                        ("page", "1"),
                        ("per_page", "1"),
                        ("since", "2026-04-01T00:00:00Z"),
                        ("until", "2026-04-30T23:59:00Z"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[{"sha": "abc123"}],
                    headers={},
                ),
                (
                    "/repos/org/api/commits",
                    (
                        ("page", "2"),
                        ("per_page", "1"),
                        ("since", "2026-04-01T00:00:00Z"),
                        ("until", "2026-04-30T23:59:00Z"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[],
                    headers={},
                ),
                (
                    "/repos/org/api/commits/abc123",
                    (),
                ): GithubTransportResponse(
                    status_code=200,
                    payload={
                        "author": {"login": "api-dev"},
                        "commit": {
                            "author": {
                                "email": "api.dev@example.com",
                                "date": "2026-04-08T08:45:00Z",
                            }
                        },
                        "parents": [{"sha": "parent1"}],
                        "files": [
                            {"filename": "src/app.py", "additions": 6, "deletions": 1},
                        ],
                    },
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport, page_size=1)

        commits = client.fetch_commits_landed(
            repositories=("org/api",),
            committed_from=committed_from,
            committed_to=committed_to,
        )

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].commit_sha, "abc123")
        self.assertEqual(commits[0].author_email, "api.dev@example.com")
        self.assertEqual(commits[0].files[0].path, "src/app.py")

    def test_fetch_commits_landed_fetches_commit_details_in_parallel(self) -> None:
        committed_from = datetime(2026, 4, 1, tzinfo=UTC)
        committed_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = SlowGithubTransport(
            {
                (
                    "/repos/org/api/commits",
                    (
                        ("page", "1"),
                        ("per_page", "100"),
                        ("since", "2026-04-01T00:00:00Z"),
                        ("until", "2026-04-30T23:59:00Z"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[{"sha": "abc123"}, {"sha": "def456"}],
                    headers={},
                ),
                (
                    "/repos/org/api/commits/abc123",
                    (),
                ): GithubTransportResponse(
                    status_code=200,
                    payload={
                        "author": {"login": "api-dev"},
                        "commit": {
                            "author": {
                                "email": "api.dev@example.com",
                                "date": "2026-04-08T08:45:00Z",
                            }
                        },
                        "parents": [{"sha": "parent1"}],
                        "files": [
                            {"filename": "src/app.py", "additions": 6, "deletions": 1},
                        ],
                    },
                    headers={},
                ),
                (
                    "/repos/org/api/commits/def456",
                    (),
                ): GithubTransportResponse(
                    status_code=200,
                    payload={
                        "author": {"login": "api-dev-2"},
                        "commit": {
                            "author": {
                                "email": "api.dev2@example.com",
                                "date": "2026-04-09T08:45:00Z",
                            }
                        },
                        "parents": [{"sha": "parent2"}],
                        "files": [
                            {"filename": "src/worker.py", "additions": 9, "deletions": 3},
                        ],
                    },
                    headers={},
                ),
            },
            delay_seconds=0.05,
        )
        client = GithubClient(token="token", transport=transport, max_workers=2)

        commits = client.fetch_commits_landed(
            repositories=("org/api",),
            committed_from=committed_from,
            committed_to=committed_to,
        )

        self.assertEqual(len(commits), 2)
        self.assertGreaterEqual(transport.max_active_requests, 2)

    def test_fetch_deployments_paginates_and_loads_latest_status(self) -> None:
        deployed_from = datetime(2026, 4, 1, tzinfo=UTC)
        deployed_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/deployments",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "id": 9001,
                            "sha": "abc123",
                            "environment": "production",
                            "created_at": "2026-04-12T08:00:00Z",
                        },
                        {
                            "id": 9000,
                            "sha": "old123",
                            "environment": "production",
                            "created_at": "2026-03-30T08:00:00Z",
                        },
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/deployments/9001/statuses",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "state": "success",
                            "created_at": "2026-04-12T08:30:00Z",
                        }
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/deployments/9000/statuses",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[],
                    headers={},
                ),
                (
                    "/repos/org/api/commits/abc123",
                    (),
                ): GithubTransportResponse(
                    status_code=200,
                    payload={
                        "commit": {
                            "author": {
                                "email": "api.dev@example.com",
                                "date": "2026-04-12T06:00:00Z",
                            }
                        },
                        "parents": [{"sha": "parent1"}],
                        "files": [],
                    },
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        deployments = client.fetch_deployments(
            repositories=("org/api",),
            deployed_from=deployed_from,
            deployed_to=deployed_to,
        )

        self.assertEqual(
            deployments,
            (
                GithubDeploymentPayload(
                    repository="org/api",
                    deployment_id=9001,
                    commit_sha="abc123",
                    environment="production",
                    created_at=datetime(2026, 4, 12, 8, 0, tzinfo=UTC),
                    latest_status_state="success",
                    latest_status_at=datetime(2026, 4, 12, 8, 30, tzinfo=UTC),
                    commit_committed_at=datetime(2026, 4, 12, 6, 0, tzinfo=UTC),
                ),
            ),
        )

    def test_fetch_deployments_filters_by_latest_status_window(self) -> None:
        deployed_from = datetime(2026, 4, 1, tzinfo=UTC)
        deployed_to = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/deployments",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "id": 9100,
                            "sha": "old-created",
                            "environment": "production",
                            "created_at": "2026-03-31T23:00:00Z",
                        },
                        {
                            "id": 9101,
                            "sha": "late-status",
                            "environment": "production",
                            "created_at": "2026-04-30T23:30:00Z",
                        },
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/deployments/9100/statuses",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "state": "success",
                            "created_at": "2026-04-01T00:15:00Z",
                        }
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/deployments/9101/statuses",
                    (("page", "1"), ("per_page", "100")),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "state": "success",
                            "created_at": "2026-05-01T00:15:00Z",
                        }
                    ],
                    headers={},
                ),
                (
                    "/repos/org/api/commits/old-created",
                    (),
                ): GithubTransportResponse(
                    status_code=200,
                    payload={
                        "commit": {"author": {"date": "2026-03-31T22:00:00Z"}},
                        "parents": [{"sha": "parent1"}],
                        "files": [],
                    },
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        deployments = client.fetch_deployments(
            repositories=("org/api",),
            deployed_from=deployed_from,
            deployed_to=deployed_to,
        )

        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0].deployment_id, 9100)
        self.assertEqual(
            deployments[0].latest_status_at,
            datetime(2026, 4, 1, 0, 15, tzinfo=UTC),
        )

    def test_rate_limit_response_raises_specialized_error(self) -> None:
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=403,
                    payload={"message": "API rate limit exceeded"},
                    headers={
                        "x-ratelimit-remaining": "0",
                        "x-ratelimit-reset": "1775520000",
                    },
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        with self.assertRaises(GithubRateLimitError) as context:
            client.fetch_merged_pull_requests(
                repositories=("org/api",),
                merged_from=datetime(2026, 4, 1, tzinfo=UTC),
                merged_to=datetime(2026, 4, 30, tzinfo=UTC),
            )

        self.assertEqual(
            context.exception.reset_at,
            datetime(2026, 4, 7, 0, 0, tzinfo=UTC),
        )

    def test_forbidden_response_without_rate_limit_headers_raises_api_error(self) -> None:
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/api/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=403,
                    payload={"message": "Resource not accessible by integration"},
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        with self.assertRaises(GithubApiError) as context:
            client.fetch_merged_pull_requests(
                repositories=("org/api",),
                merged_from=datetime(2026, 4, 1, tzinfo=UTC),
                merged_to=datetime(2026, 4, 30, tzinfo=UTC),
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertIn("403 Forbidden", str(context.exception))

    def test_not_found_response_includes_repository_diagnostics(self) -> None:
        transport = FakeGithubTransport(
            {
                (
                    "/repos/org/missing/pulls",
                    (
                        ("direction", "desc"),
                        ("page", "1"),
                        ("per_page", "100"),
                        ("sort", "updated"),
                        ("state", "closed"),
                    ),
                ): GithubTransportResponse(
                    status_code=404,
                    payload={"message": "Not Found"},
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport)

        with self.assertRaises(GithubApiError) as context:
            client.fetch_merged_pull_requests(
                repositories=("org/missing",),
                merged_from=datetime(2026, 4, 1, tzinfo=UTC),
                merged_to=datetime(2026, 4, 30, tzinfo=UTC),
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.path, "/repos/org/missing/pulls")
        self.assertIn("/repos/org/missing/pulls", str(context.exception))
        self.assertIn("GITHUB_API_BASE_URL", str(context.exception))

    def test_list_organization_repositories_paginates_and_parses_repo_metadata(self) -> None:
        transport = FakeGithubTransport(
            {
                (
                    "/orgs/openai/repos",
                    (
                        ("page", "1"),
                        ("per_page", "1"),
                        ("sort", "full_name"),
                        ("type", "all"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "full_name": "openai/api",
                            "archived": False,
                            "fork": False,
                            "private": True,
                            "visibility": "private",
                        }
                    ],
                    headers={},
                ),
                (
                    "/orgs/openai/repos",
                    (
                        ("page", "2"),
                        ("per_page", "1"),
                        ("sort", "full_name"),
                        ("type", "all"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[
                        {
                            "full_name": "openai/archive",
                            "archived": True,
                            "fork": False,
                            "private": False,
                            "visibility": "public",
                        }
                    ],
                    headers={},
                ),
                (
                    "/orgs/openai/repos",
                    (
                        ("page", "3"),
                        ("per_page", "1"),
                        ("sort", "full_name"),
                        ("type", "all"),
                    ),
                ): GithubTransportResponse(
                    status_code=200,
                    payload=[],
                    headers={},
                ),
            }
        )
        client = GithubClient(token="token", transport=transport, page_size=1)

        repositories = client.list_organization_repositories(organization="openai")

        self.assertEqual(
            repositories,
            (
                GithubRepositoryPayload(
                    full_name="openai/api",
                    archived=False,
                    fork=False,
                    private=True,
                    visibility="private",
                ),
                GithubRepositoryPayload(
                    full_name="openai/archive",
                    archived=True,
                    fork=False,
                    private=False,
                    visibility="public",
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
