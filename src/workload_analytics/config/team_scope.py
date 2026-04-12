from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from email.utils import parseaddr
from enum import StrEnum
import re

REPOSITORY_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
JIRA_PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class Granularity(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True, slots=True)
class TeamScope:
    team_name: str
    github_repositories: tuple[str, ...]
    github_organization: str | None
    jira_projects: tuple[str, ...]
    team_members: tuple[str, ...] = ()


def parse_team_scope(
    *,
    team_name: str,
    github_repositories: Iterable[str],
    github_organization: str | None = None,
    jira_projects: Iterable[str],
    team_members: Iterable[str] = (),
) -> TeamScope:
    normalized_team_name = team_name.strip()
    if not normalized_team_name:
        raise ValueError("WORKLOAD_TEAM_NAME must not be empty.")

    organization = parse_github_organization(github_organization)
    repositories = (
        ()
        if organization is not None
        else parse_github_repositories(github_repositories)
    )
    projects = parse_jira_projects(jira_projects)
    members = parse_team_members(team_members)

    if organization is None and not repositories:
        raise ValueError(
            "Either WORKLOAD_GITHUB_REPOSITORIES or WORKLOAD_GITHUB_ORGANIZATION must be configured."
        )
    if not projects:
        raise ValueError(
            "WORKLOAD_JIRA_PROJECTS must contain at least one Jira project key."
        )
    if organization is not None and not members:
        raise ValueError(
            "WORKLOAD_TEAM_MEMBERS must contain at least one team member email when WORKLOAD_GITHUB_ORGANIZATION is set."
        )

    return TeamScope(
        team_name=normalized_team_name,
        github_repositories=repositories,
        github_organization=organization,
        jira_projects=projects,
        team_members=members,
    )


def parse_csv_list(raw_value: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()

    for item in raw_value.split(","):
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        values.append(normalized)
        seen.add(normalized)

    return tuple(values)


def parse_github_repositories(github_repositories: Iterable[str]) -> tuple[str, ...]:
    repositories: list[str] = []
    seen: set[str] = set()

    for repository in github_repositories:
        normalized = repository.strip()
        if not normalized or normalized in seen:
            continue
        if not REPOSITORY_SLUG_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Invalid GitHub repository slug "
                f"{normalized!r}. Expected 'owner/repository'."
            )
        repositories.append(normalized)
        seen.add(normalized)

    return tuple(repositories)


def parse_github_organization(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None

    normalized = raw_value.strip()
    if not normalized:
        return None
    if "/" in normalized or any(character.isspace() for character in normalized):
        raise ValueError(
            "Invalid GitHub organization "
            f"{raw_value!r}. Expected an organization login without slashes or spaces."
        )
    return normalized


def parse_jira_projects(jira_projects: Iterable[str]) -> tuple[str, ...]:
    projects: list[str] = []
    seen: set[str] = set()

    for project in jira_projects:
        normalized = project.strip().upper()
        if not normalized or normalized in seen:
            continue
        if not JIRA_PROJECT_KEY_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Invalid Jira project key "
                f"{project!r}. Expected uppercase letters, numbers, or underscores."
            )
        projects.append(normalized)
        seen.add(normalized)

    return tuple(projects)


def parse_team_members(team_members: Iterable[str]) -> tuple[str, ...]:
    members: list[str] = []
    seen: set[str] = set()

    for member in team_members:
        normalized = _normalize_email(member)
        if not normalized or normalized in seen:
            continue
        members.append(normalized)
        seen.add(normalized)

    return tuple(members)


def _normalize_email(raw_value: str) -> str:
    _, address = parseaddr(raw_value)
    normalized = address.strip().lower()
    if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
        raise ValueError(
            f"Invalid team member email {raw_value!r}. Expected a valid email address."
        )
    return normalized
