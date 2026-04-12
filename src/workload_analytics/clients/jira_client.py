from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .http_json import fetch_json_response
from .parsing import normalize_optional_email as _normalize_optional_email
from .parsing import parse_datetime as _parse_datetime

_PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True, slots=True)
class JiraAssignedIssuePayload:
    project_key: str
    issue_key: str
    assignee_email: str | None
    assignee_display_name: str | None
    updated_at: datetime
    status_name: str


@dataclass(frozen=True, slots=True)
class JiraTransportResponse:
    status_code: int
    payload: object
    headers: Mapping[str, str]


class JiraTransport(Protocol):
    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> JiraTransportResponse: ...


class UrlLibJiraTransport:
    def __init__(self, *, base_url: str, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> JiraTransportResponse:
        response = fetch_json_response(
            base_url=self._base_url,
            path=path,
            params=params,
            headers=headers,
            timeout=self._timeout,
        )
        return JiraTransportResponse(
            status_code=response.status_code,
            payload=response.payload,
            headers=response.headers,
        )


class JiraClient:
    MAX_PAGES = 500

    def __init__(
        self,
        *,
        base_url: str,
        user_email: str,
        api_token: str,
        transport: JiraTransport | None = None,
        page_size: int = 50,
    ) -> None:
        self._user_email = user_email
        self._api_token = api_token
        self._transport = transport or UrlLibJiraTransport(base_url=base_url)
        self._page_size = page_size

    def fetch_assigned_issues(
        self,
        *,
        projects: Iterable[str],
        updated_from: datetime,
        updated_to: datetime,
    ) -> tuple[JiraAssignedIssuePayload, ...]:
        issues: list[JiraAssignedIssuePayload] = []

        for project_key in projects:
            jql = _build_assigned_issues_jql(
                project_key=project_key,
                updated_from=updated_from,
                updated_to=updated_to,
            )
            next_page_token: str | None = None
            start_at = 0
            pages_fetched = 0

            while pages_fetched < self.MAX_PAGES:
                params = _build_search_params(
                    jql=jql,
                    page_size=self._page_size,
                    next_page_token=next_page_token,
                    start_at=start_at,
                )

                pages_fetched += 1
                payload = self._get_json(
                    path="/rest/api/3/search/jql",
                    params=params,
                )
                page = _ensure_dict(payload)
                page_issues = _require_issue_list(page, "issues")
                issues.extend(_parse_issues(page_issues))

                is_last = _optional_bool(page.get("isLast"))
                if is_last is not None:
                    if is_last or not page_issues:
                        break
                    next_page_token = _optional_string(page.get("nextPageToken"))
                    if next_page_token is None:
                        raise ValueError(
                            "Jira payload is missing nextPageToken while isLast is false."
                        )
                    continue

                total = _coerce_int(page.get("total"), field_name="total")
                start_at += len(page_issues)
                if start_at >= total or not page_issues:
                    break

        return tuple(issues)

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
                "Accept": "application/json",
                "Authorization": _build_basic_auth(self._user_email, self._api_token),
                "User-Agent": "workload-analytics",
            },
        )

        if response.status_code >= 400:
            message = "Jira API request failed."
            if isinstance(response.payload, Mapping):
                error_messages = response.payload.get("errorMessages")
                if isinstance(error_messages, list) and error_messages:
                    first = error_messages[0]
                    if isinstance(first, str) and first.strip():
                        message = first
                elif isinstance(response.payload.get("message"), str):
                    message = response.payload["message"]
            raise RuntimeError(message)

        return response.payload


def _build_assigned_issues_jql(
    *,
    project_key: str,
    updated_from: datetime,
    updated_to: datetime,
) -> str:
    if not _PROJECT_KEY_PATTERN.fullmatch(project_key):
        raise ValueError(
            f"Invalid Jira project key {project_key!r}. "
            "Expected uppercase letters, digits, or underscores."
        )
    from_value = updated_from.strftime("%Y-%m-%d %H:%M")
    to_value = updated_to.strftime("%Y-%m-%d %H:%M")

    return (
        f'project = "{project_key}" AND assignee IS NOT EMPTY '
        f'AND updated >= "{from_value}" AND updated <= "{to_value}" '
        "ORDER BY updated DESC"
    )


def _build_search_params(
    *,
    jql: str,
    page_size: int,
    next_page_token: str | None,
    start_at: int,
) -> dict[str, str]:
    params = {
        "jql": jql,
        "fields": ",".join(
            (
                "key",
                "project",
                "assignee",
                "status",
                "updated",
            )
        ),
        "maxResults": str(page_size),
    }
    if next_page_token is not None:
        params["nextPageToken"] = next_page_token
    elif start_at > 0:
        params["startAt"] = str(start_at)
    return params


def _parse_issues(issue_payloads: list[dict[str, Any]]) -> tuple[JiraAssignedIssuePayload, ...]:
    return tuple(_parse_issue(payload) for payload in issue_payloads)


def _parse_issue(payload: Mapping[str, Any]) -> JiraAssignedIssuePayload:
    issue_key = _require_string(payload, "key")
    fields = _ensure_dict(payload.get("fields"))
    project = _ensure_dict(fields.get("project"))
    assignee = fields.get("assignee")
    assignee_payload = assignee if isinstance(assignee, Mapping) else {}
    status_payload = _ensure_dict(fields.get("status"))

    updated_at = _parse_datetime(_optional_string(fields.get("updated")))
    if updated_at is None:
        raise ValueError(f"Jira issue {issue_key!r} is missing updated timestamp.")

    return JiraAssignedIssuePayload(
        project_key=_require_string(project, "key"),
        issue_key=issue_key,
        assignee_email=_normalize_optional_email(_optional_string(assignee_payload.get("emailAddress"))),
        assignee_display_name=_optional_string(assignee_payload.get("displayName")),
        updated_at=updated_at,
        status_name=_require_string(status_payload, "name"),
    )


def _build_basic_auth(user_email: str, api_token: str) -> str:
    import base64

    token = f"{user_email}:{api_token}".encode("utf-8")
    encoded = base64.b64encode(token).decode("ascii")
    return f"Basic {encoded}"


def _ensure_dict(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Jira API response payload must be an object.")
    return dict(payload)


def _require_issue_list(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Jira payload is missing list field {key!r}.")

    issues: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Jira payload list {key!r} must contain objects.")
        issues.append(item)
    return issues


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Jira payload field {key!r} must be a non-empty string.")
    return value


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _coerce_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Jira payload field {field_name!r} must be an integer.")
    return value


