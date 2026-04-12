from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from .http_json import fetch_json_response
from .parsing import normalize_optional_email as _normalize_optional_email
from .parsing import parse_datetime as _parse_datetime


@dataclass(frozen=True, slots=True)
class GithubChangedFile:
    path: str
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class GithubPullRequestPayload:
    repository: str
    pull_request_number: int
    author_login: str | None
    merged_at: datetime
    commit_author_emails: tuple[str, ...]
    files: tuple[GithubChangedFile, ...]
    created_at: datetime | None = None
    first_reviewed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GithubCommitPayload:
    repository: str
    commit_sha: str
    author_login: str | None
    author_email: str | None
    committed_at: datetime
    parent_count: int
    files: tuple[GithubChangedFile, ...]


@dataclass(frozen=True, slots=True)
class GithubDeploymentPayload:
    repository: str
    deployment_id: int
    commit_sha: str
    environment: str
    created_at: datetime
    latest_status_state: str | None
    latest_status_at: datetime | None
    commit_committed_at: datetime | None


@dataclass(frozen=True, slots=True)
class GithubRepositoryPayload:
    full_name: str
    archived: bool
    fork: bool
    private: bool
    visibility: str | None
    pushed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GithubTransportResponse:
    status_code: int
    payload: object
    headers: Mapping[str, str]


class GithubRateLimitError(RuntimeError):
    def __init__(self, *, reset_at: datetime | None, message: str) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class GithubApiError(RuntimeError):
    def __init__(self, *, status_code: int, path: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


class GithubTransport(Protocol):
    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> GithubTransportResponse: ...


class UrlLibGithubTransport:
    def __init__(self, *, base_url: str = "https://api.github.com", timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> GithubTransportResponse:
        response = fetch_json_response(
            base_url=self._base_url,
            path=path,
            params=params,
            headers=headers,
            timeout=self._timeout,
        )
        return GithubTransportResponse(
            status_code=response.status_code,
            payload=response.payload,
            headers=response.headers,
        )


class GithubClient:
    MAX_PAGES = 500

    def __init__(
        self,
        *,
        token: str,
        base_url: str = "https://api.github.com",
        transport: GithubTransport | None = None,
        page_size: int = 100,
        max_workers: int = 8,
    ) -> None:
        self._token = token
        self._transport = transport or UrlLibGithubTransport(base_url=base_url)
        self._page_size = page_size
        self._max_workers = max(1, max_workers)

    def fetch_merged_pull_requests(
        self,
        *,
        repositories: Iterable[str],
        merged_from: datetime,
        merged_to: datetime,
    ) -> tuple[GithubPullRequestPayload, ...]:
        repositories_tuple = tuple(repositories)
        return tuple(
            pull_request
            for repository_pull_requests in self._map_repositories(
                repositories_tuple,
                lambda repository: self._fetch_repository_pull_requests(
                    repository=repository,
                    merged_from=merged_from,
                    merged_to=merged_to,
                ),
            )
            for pull_request in repository_pull_requests
        )

    def fetch_commits_landed(
        self,
        *,
        repositories: Iterable[str],
        committed_from: datetime,
        committed_to: datetime,
    ) -> tuple[GithubCommitPayload, ...]:
        repositories_tuple = tuple(repositories)
        return tuple(
            commit
            for repository_commits in self._map_repositories(
                repositories_tuple,
                lambda repository: self._fetch_repository_commits(
                    repository=repository,
                    committed_from=committed_from,
                    committed_to=committed_to,
                ),
            )
            for commit in repository_commits
        )

    def fetch_deployments(
        self,
        *,
        repositories: Iterable[str],
        deployed_from: datetime,
        deployed_to: datetime,
    ) -> tuple[GithubDeploymentPayload, ...]:
        repositories_tuple = tuple(repositories)
        return tuple(
            deployment
            for repository_deployments in self._map_repositories(
                repositories_tuple,
                lambda repository: self._fetch_repository_deployments(
                    repository=repository,
                    deployed_from=deployed_from,
                    deployed_to=deployed_to,
                ),
            )
            for deployment in repository_deployments
        )

    def list_organization_repositories(
        self,
        *,
        organization: str,
    ) -> tuple[GithubRepositoryPayload, ...]:
        return tuple(
            GithubRepositoryPayload(
                full_name=_require_string(payload, "full_name"),
                archived=_require_bool(payload, "archived"),
                fork=_require_bool(payload, "fork"),
                private=_require_bool(payload, "private"),
                visibility=_optional_string(payload.get("visibility")),
                pushed_at=_parse_datetime(_optional_string(payload.get("pushed_at"))),
            )
            for payload in self._paginate(
                path=f"/orgs/{organization}/repos",
                params={
                    "type": "all",
                    "sort": "full_name",
                },
            )
        )

    def _fetch_repository_pull_requests(
        self,
        *,
        repository: str,
        merged_from: datetime,
        merged_to: datetime,
    ) -> tuple[GithubPullRequestPayload, ...]:
        matching_summaries: list[dict[str, Any]] = []

        for page_items in self._iterate_pages(
            path=f"/repos/{repository}/pulls",
            params={
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
            },
        ):
            should_stop_pagination = False
            for summary in page_items:
                updated_at = _parse_datetime(summary.get("updated_at"))
                if updated_at is not None and updated_at < merged_from:
                    should_stop_pagination = True
                    break

                merged_at = _parse_datetime(summary.get("merged_at"))
                if merged_at is None or not (merged_from <= merged_at <= merged_to):
                    continue

                matching_summaries.append(summary)

            if should_stop_pagination:
                break

        return self._map_items(
            tuple(matching_summaries),
            lambda summary: self._build_pull_request_payload(
                repository=repository,
                summary=summary,
            ),
        )

    def _fetch_repository_commits(
        self,
        *,
        repository: str,
        committed_from: datetime,
        committed_to: datetime,
    ) -> tuple[GithubCommitPayload, ...]:
        summaries = self._paginate(
            path=f"/repos/{repository}/commits",
            params={
                "since": committed_from.astimezone(UTC).isoformat().replace(
                    "+00:00",
                    "Z",
                ),
                "until": committed_to.astimezone(UTC).isoformat().replace(
                    "+00:00",
                    "Z",
                ),
            },
        )
        return self._map_items(
            summaries,
            lambda summary: self._build_commit_payload(
                repository=repository,
                summary=summary,
            ),
        )

    def _fetch_repository_deployments(
        self,
        *,
        repository: str,
        deployed_from: datetime,
        deployed_to: datetime,
    ) -> tuple[GithubDeploymentPayload, ...]:
        candidate_summaries: list[dict[str, Any]] = []

        for page_items in self._iterate_pages(
            path=f"/repos/{repository}/deployments",
            params={},
        ):
            for summary in page_items:
                created_at = _parse_datetime(_optional_string(summary.get("created_at")))
                if created_at is None or created_at > deployed_to:
                    continue
                candidate_summaries.append(summary)

        deployments = self._map_items(
            tuple(candidate_summaries),
            lambda summary: self._build_deployment_payload(
                repository=repository,
                summary=summary,
                load_commit_committed_at=False,
            ),
        )
        matching_deployments = tuple(
            deployment
            for deployment in deployments
            if deployed_from <= _deployment_deployed_at(deployment) <= deployed_to
        )
        return self._map_items(
            matching_deployments,
            self._load_deployment_commit_committed_at,
        )

    def _build_pull_request_payload(
        self,
        *,
        repository: str,
        summary: Mapping[str, Any],
    ) -> GithubPullRequestPayload:
        number = _require_int(summary, "number")
        files = self._fetch_pull_request_files(repository, number)
        commit_author_emails = self._fetch_pull_request_commit_emails(
            repository,
            number,
        )
        first_reviewed_at = self._fetch_pull_request_first_reviewed_at(
            repository,
            number,
        )
        merged_at = _parse_datetime(summary.get("merged_at"))
        if merged_at is None:
            raise ValueError(f"Pull request {number!r} is missing merged_at.")

        return GithubPullRequestPayload(
            repository=repository,
            pull_request_number=number,
            author_login=_get_nested_string(summary, "user", "login"),
            merged_at=merged_at,
            commit_author_emails=commit_author_emails,
            files=files,
            created_at=_parse_datetime(_optional_string(summary.get("created_at"))),
            first_reviewed_at=first_reviewed_at,
        )

    def _build_commit_payload(
        self,
        *,
        repository: str,
        summary: Mapping[str, Any],
    ) -> GithubCommitPayload:
        sha = _require_string(summary, "sha")
        detail = self._get_json(
            path=f"/repos/{repository}/commits/{sha}",
            params={},
        )

        committed_at = _parse_datetime(
            _get_nested_string(detail, "commit", "author", "date")
        )
        if committed_at is None:
            raise ValueError(f"Commit {sha!r} is missing commit.author.date.")

        return GithubCommitPayload(
            repository=repository,
            commit_sha=sha,
            author_login=_get_nested_string(detail, "author", "login"),
            author_email=_normalize_optional_email(
                _get_nested_string(detail, "commit", "author", "email")
            ),
            committed_at=committed_at,
            parent_count=len(_require_list(detail, "parents")),
            files=_parse_changed_files(_require_list(detail, "files")),
        )

    def _build_deployment_payload(
        self,
        *,
        repository: str,
        summary: Mapping[str, Any],
        load_commit_committed_at: bool = True,
    ) -> GithubDeploymentPayload:
        deployment_id = _require_int(summary, "id")
        commit_sha = _require_string(summary, "sha")
        created_at = _parse_datetime(_optional_string(summary.get("created_at")))
        if created_at is None:
            raise ValueError(f"Deployment {deployment_id!r} is missing created_at.")

        latest_status_state, latest_status_at = self._fetch_latest_deployment_status(
            repository=repository,
            deployment_id=deployment_id,
        )
        commit_committed_at = None
        if (
            load_commit_committed_at
            and (latest_status_state or "").strip().lower() == "success"
        ):
            commit_committed_at = self._fetch_commit_committed_at(
                repository=repository,
                commit_sha=commit_sha,
            )

        return GithubDeploymentPayload(
            repository=repository,
            deployment_id=deployment_id,
            commit_sha=commit_sha,
            environment=_optional_string(summary.get("environment")) or "default",
            created_at=created_at,
            latest_status_state=latest_status_state,
            latest_status_at=latest_status_at,
            commit_committed_at=commit_committed_at,
        )

    def _load_deployment_commit_committed_at(
        self,
        deployment: GithubDeploymentPayload,
    ) -> GithubDeploymentPayload:
        if (deployment.latest_status_state or "").strip().lower() != "success":
            return deployment
        return replace(
            deployment,
            commit_committed_at=self._fetch_commit_committed_at(
                repository=deployment.repository,
                commit_sha=deployment.commit_sha,
            ),
        )

    def _fetch_latest_deployment_status(
        self,
        *,
        repository: str,
        deployment_id: int,
    ) -> tuple[str | None, datetime | None]:
        statuses = self._paginate(
            path=f"/repos/{repository}/deployments/{deployment_id}/statuses",
            params={},
        )
        if not statuses:
            return None, None

        latest_status = max(
            statuses,
            key=lambda status: (
                _parse_datetime(_optional_string(status.get("created_at")))
                or datetime.min.replace(tzinfo=UTC)
            ),
        )
        return (
            _optional_string(latest_status.get("state")),
            _parse_datetime(_optional_string(latest_status.get("created_at"))),
        )

    def _fetch_commit_committed_at(
        self,
        *,
        repository: str,
        commit_sha: str,
    ) -> datetime | None:
        detail = self._get_json(
            path=f"/repos/{repository}/commits/{commit_sha}",
            params={},
        )
        if not isinstance(detail, Mapping):
            raise ValueError("GitHub commit payload must be an object.")
        return _parse_datetime(_get_nested_string(detail, "commit", "author", "date"))

    def _fetch_pull_request_files(
        self,
        repository: str,
        pull_request_number: int,
    ) -> tuple[GithubChangedFile, ...]:
        return tuple(
            file_change
            for file_payload in self._paginate(
                path=f"/repos/{repository}/pulls/{pull_request_number}/files",
                params={},
            )
            for file_change in [_parse_changed_file(file_payload)]
        )

    def _fetch_pull_request_commit_emails(
        self,
        repository: str,
        pull_request_number: int,
    ) -> tuple[str, ...]:
        emails: list[str] = []
        seen: set[str] = set()

        for commit_payload in self._paginate(
            path=f"/repos/{repository}/pulls/{pull_request_number}/commits",
            params={},
        ):
            email = _normalize_optional_email(
                _get_nested_string(commit_payload, "commit", "author", "email")
            )
            if email is None or email in seen:
                continue
            emails.append(email)
            seen.add(email)

        return tuple(emails)

    def _fetch_pull_request_first_reviewed_at(
        self,
        repository: str,
        pull_request_number: int,
    ) -> datetime | None:
        reviewed_at_values: list[datetime] = []

        for review_payload in self._paginate(
            path=f"/repos/{repository}/pulls/{pull_request_number}/reviews",
            params={},
        ):
            reviewed_at = _parse_datetime(
                _optional_string(review_payload.get("submitted_at"))
            )
            if reviewed_at is not None:
                reviewed_at_values.append(reviewed_at)

        return min(reviewed_at_values) if reviewed_at_values else None

    def _paginate(
        self,
        *,
        path: str,
        params: Mapping[str, str],
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            item
            for page_items in self._iterate_pages(path=path, params=params)
            for item in page_items
        )

    def _iterate_pages(
        self,
        *,
        path: str,
        params: Mapping[str, str],
    ) -> Iterator[tuple[dict[str, Any], ...]]:
        page = 1

        while page <= self.MAX_PAGES:
            response = self._get_json(
                path=path,
                params={
                    **params,
                    "per_page": str(self._page_size),
                    "page": str(page),
                },
            )
            page_items = tuple(_ensure_dict_list(response))
            if not page_items:
                break

            yield page_items

            if len(page_items) < self._page_size:
                break
            page += 1

    def _map_repositories(self, repositories: tuple[str, ...], action) -> tuple[tuple[object, ...], ...]:
        return self._map_items(repositories, action)

    def _map_items(self, items: tuple[object, ...], action) -> tuple[object, ...]:
        if len(items) <= 1 or self._max_workers <= 1:
            return tuple(action(item) for item in items)

        max_workers = min(self._max_workers, len(items))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: list[Future[object]] = [
                executor.submit(action, item) for item in items
            ]
            return tuple(future.result() for future in futures)

    def _get_json(
        self,
        *,
        path: str,
        params: Mapping[str, str],
    ) -> object:
        response = self._transport.get(
            path=path,
            params=params,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "workload-analytics",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        self._raise_for_error(response, path=path)
        return response.payload

    def _raise_for_error(
        self,
        response: GithubTransportResponse,
        *,
        path: str,
    ) -> None:
        if response.status_code < 400:
            return

        headers = {key.lower(): value for key, value in response.headers.items()}
        payload_message = _extract_error_message(response.payload)
        if _is_rate_limited_response(
            status_code=response.status_code,
            headers=headers,
            payload_message=payload_message,
        ):
            reset_at = _parse_rate_limit_reset(headers.get("x-ratelimit-reset"))
            raise GithubRateLimitError(
                reset_at=reset_at,
                message="GitHub API rate limit reached.",
            )

        if response.status_code == 401:
            message = (
                f"GitHub API request failed for {path!r} (401 Unauthorized). "
                "Check GITHUB_TOKEN."
            )
        elif response.status_code == 404 and path.startswith("/repos/"):
            message = (
                f"GitHub API request failed for {path!r} (404 Not Found). "
                "Check WORKLOAD_GITHUB_REPOSITORIES, confirm the token can access "
                "the repository, and set GITHUB_API_BASE_URL if you use "
                "GitHub Enterprise."
            )
        elif response.status_code == 404 and path.startswith("/orgs/"):
            message = (
                f"GitHub API request failed for {path!r} (404 Not Found). "
                "Check WORKLOAD_GITHUB_ORGANIZATION, confirm the token can list "
                "organization repositories, and set GITHUB_API_BASE_URL if you "
                "use GitHub Enterprise."
            )
        elif response.status_code == 403:
            message = (
                f"GitHub API request failed for {path!r} (403 Forbidden). "
                "Check token repository access and any required organization SSO "
                "authorization."
            )
        elif payload_message:
            message = (
                f"GitHub API request failed for {path!r} "
                f"({response.status_code}): {payload_message}"
            )
        else:
            message = f"GitHub API request failed for {path!r} ({response.status_code})."

        raise GithubApiError(
            status_code=response.status_code,
            path=path,
            message=message,
        )


def _parse_changed_files(file_payloads: list[dict[str, Any]]) -> tuple[GithubChangedFile, ...]:
    return tuple(_parse_changed_file(payload) for payload in file_payloads)


def _deployment_deployed_at(deployment: GithubDeploymentPayload) -> datetime:
    return deployment.latest_status_at or deployment.created_at


def _parse_changed_file(file_payload: Mapping[str, Any]) -> GithubChangedFile:
    filename = file_payload.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("GitHub changed file payload is missing filename.")

    return GithubChangedFile(
        path=filename,
        additions=_coerce_int(file_payload.get("additions")),
        deletions=_coerce_int(file_payload.get("deletions")),
    )


def _ensure_dict_list(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("GitHub API response payload must be a list.")

    items: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("GitHub API list items must be objects.")
        items.append(item)
    return items


def _require_list(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"GitHub payload is missing list field {key!r}.")

    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"GitHub payload list {key!r} must contain objects.")
        items.append(item)
    return items


def _require_int(payload: Mapping[str, Any], key: str) -> int:
    return _coerce_int(payload.get(key), field_name=key)


def _coerce_int(value: object, *, field_name: str = "value") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"GitHub payload field {field_name!r} must be an integer.")
    return value


def _require_bool(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"GitHub payload field {key!r} must be a boolean.")
    return value


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"GitHub payload field {key!r} must be a non-empty string.")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("GitHub payload optional string field must be a string.")
    normalized = value.strip()
    return normalized or None


def _get_nested_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    current: object = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)

    if isinstance(current, str) and current.strip():
        return current
    return None


def _parse_rate_limit_reset(raw_value: str | None) -> datetime | None:
    if raw_value is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw_value), tz=UTC)
    except ValueError:
        return None


def _extract_error_message(payload: object) -> str:
    if not isinstance(payload, Mapping):
        return ""
    raw_payload_message = payload.get("message")
    if not isinstance(raw_payload_message, str):
        return ""
    return raw_payload_message.strip()


def _is_rate_limited_response(
    *,
    status_code: int,
    headers: Mapping[str, str],
    payload_message: str,
) -> bool:
    if status_code == 429:
        return True
    if headers.get("x-ratelimit-remaining") == "0":
        return True
    if status_code != 403:
        return False
    return "rate limit" in payload_message.lower()
