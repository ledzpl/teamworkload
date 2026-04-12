from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parseaddr
import os
from urllib.parse import urlparse

from .team_scope import (
    Granularity,
    TeamScope,
    parse_csv_list,
    parse_github_organization,
    parse_github_repositories,
    parse_jira_projects,
    parse_team_members,
)


class ConfigError(ValueError):
    """Raised when the local workload analytics configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    review_wait_hours: float = 24.0
    review_wait_caution_hours: float = 12.0
    review_wait_warning_hours: float = 48.0
    stale_pr_count: int = 5
    large_pr_lines: int = 500
    large_pr_ratio: float = 0.5
    wip_concentration_factor: float = 2.0
    workload_cv_good: float = 0.5
    workload_cv_caution: float = 1.0
    wip_trend_caution_rate: float = 0.3
    deployment_success_good: float = 0.9
    deployment_success_caution: float = 0.7


def load_threshold_config(environ: Mapping[str, str] | None = None) -> ThresholdConfig:
    env = dict(os.environ if environ is None else environ)
    return ThresholdConfig(
        review_wait_hours=_parse_float(env, "WORKLOAD_REVIEW_WAIT_HOURS", 24.0),
        review_wait_caution_hours=_parse_float(env, "WORKLOAD_REVIEW_WAIT_CAUTION_HOURS", 12.0),
        review_wait_warning_hours=_parse_float(env, "WORKLOAD_REVIEW_WAIT_WARNING_HOURS", 48.0),
        stale_pr_count=_parse_int(env, "WORKLOAD_STALE_PR_COUNT", 5),
        large_pr_lines=_parse_int(env, "WORKLOAD_LARGE_PR_LINES", 500),
        large_pr_ratio=_parse_float(env, "WORKLOAD_LARGE_PR_RATIO", 0.5),
        wip_concentration_factor=_parse_float(env, "WORKLOAD_WIP_CONCENTRATION_FACTOR", 2.0),
        workload_cv_good=_parse_float(env, "WORKLOAD_CV_GOOD", 0.5),
        workload_cv_caution=_parse_float(env, "WORKLOAD_CV_CAUTION", 1.0),
        wip_trend_caution_rate=_parse_float(env, "WORKLOAD_WIP_TREND_CAUTION_RATE", 0.3),
        deployment_success_good=_parse_float(env, "WORKLOAD_DEPLOYMENT_SUCCESS_GOOD", 0.9),
        deployment_success_caution=_parse_float(env, "WORKLOAD_DEPLOYMENT_SUCCESS_CAUTION", 0.7),
    )


def _parse_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class GithubCredentials:
    token: str
    base_url: str


@dataclass(frozen=True, slots=True)
class JiraCredentials:
    base_url: str
    user_email: str
    api_token: str


@dataclass(frozen=True, slots=True)
class DateDefaults:
    lookback_days: int
    default_granularity: Granularity
    allowed_granularities: tuple[Granularity, ...]


@dataclass(frozen=True, slots=True)
class StorageSettings:
    sqlite_path: str


@dataclass(frozen=True, slots=True)
class AppSettings:
    github: GithubCredentials
    jira: JiraCredentials
    team_scope: TeamScope
    date_defaults: DateDefaults
    storage: StorageSettings


def load_settings(environ: Mapping[str, str] | None = None) -> AppSettings:
    env = dict(os.environ if environ is None else environ)
    errors: list[str] = []

    team_scope = _parse_team_scope_settings(env, errors)
    github = _parse_github_settings(env, errors)
    jira = _parse_jira_settings(env, errors)
    date_defaults = _parse_date_defaults(env, errors)
    storage = _parse_storage_settings(env)

    if errors:
        raise ConfigError(_format_errors(errors))

    return AppSettings(
        github=github,
        jira=jira,
        team_scope=team_scope,
        date_defaults=date_defaults,
        storage=storage,
    )


def _parse_team_scope_settings(
    env: Mapping[str, str],
    errors: list[str],
) -> TeamScope:
    team_name = _require(env, "WORKLOAD_TEAM_NAME", errors)
    github_repositories = parse_csv_list(env.get("WORKLOAD_GITHUB_REPOSITORIES", ""))
    github_organization = env.get("WORKLOAD_GITHUB_ORGANIZATION")
    jira_projects = parse_csv_list(env.get("WORKLOAD_JIRA_PROJECTS", ""))
    team_members = parse_csv_list(env.get("WORKLOAD_TEAM_MEMBERS", ""))

    normalized_team_name = team_name.strip()
    normalized_repositories: tuple[str, ...] | None = None
    normalized_github_organization: str | None = None
    normalized_projects: tuple[str, ...] | None = None

    if not normalized_team_name:
        errors.append("WORKLOAD_TEAM_NAME is required.")

    try:
        normalized_github_organization = parse_github_organization(github_organization)
    except ValueError as exc:
        errors.append(str(exc))

    if normalized_github_organization is None:
        try:
            normalized_repositories = parse_github_repositories(github_repositories)
        except ValueError as exc:
            errors.append(str(exc))
    else:
        normalized_repositories = ()

    try:
        normalized_projects = parse_jira_projects(jira_projects)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        normalized_team_members = parse_team_members(team_members)
    except ValueError as exc:
        errors.append(str(exc))
        normalized_team_members = ()

    if (
        normalized_github_organization is None
        and normalized_repositories is not None
        and not normalized_repositories
    ):
        errors.append(
            "Either WORKLOAD_GITHUB_REPOSITORIES or WORKLOAD_GITHUB_ORGANIZATION must be configured."
        )
    if normalized_projects is not None and not normalized_projects:
        errors.append(
            "WORKLOAD_JIRA_PROJECTS must contain at least one Jira project key."
        )
    if normalized_github_organization is not None and not normalized_team_members:
        errors.append(
            "WORKLOAD_TEAM_MEMBERS must contain at least one team member email when WORKLOAD_GITHUB_ORGANIZATION is set."
        )

    return TeamScope(
        team_name=normalized_team_name,
        github_repositories=normalized_repositories or (),
        github_organization=normalized_github_organization,
        jira_projects=normalized_projects or (),
        team_members=normalized_team_members,
    )


def _parse_github_settings(
    env: Mapping[str, str],
    errors: list[str],
) -> GithubCredentials:
    github_token = _require(env, "GITHUB_TOKEN", errors)
    normalized_github_base_url = _parse_base_url(
        env.get("GITHUB_API_BASE_URL", "https://api.github.com"),
        errors,
        env_key="GITHUB_API_BASE_URL",
    )

    return GithubCredentials(
        token=github_token,
        base_url=normalized_github_base_url,
    )


def _parse_jira_settings(
    env: Mapping[str, str],
    errors: list[str],
) -> JiraCredentials:
    jira_base_url = _require(env, "JIRA_BASE_URL", errors)
    jira_user_email = _require(env, "JIRA_USER_EMAIL", errors)
    jira_api_token = _require(env, "JIRA_API_TOKEN", errors)

    normalized_jira_base_url = _parse_base_url(
        jira_base_url,
        errors,
        env_key="JIRA_BASE_URL",
    )
    normalized_jira_user_email = _parse_email(
        jira_user_email,
        env_key="JIRA_USER_EMAIL",
        errors=errors,
    )

    return JiraCredentials(
        base_url=normalized_jira_base_url,
        user_email=normalized_jira_user_email,
        api_token=jira_api_token,
    )


def _parse_date_defaults(
    env: Mapping[str, str],
    errors: list[str],
) -> DateDefaults:
    lookback_days = _parse_lookback_days(
        env.get("WORKLOAD_LOOKBACK_DAYS", "90"),
        errors,
    )
    allowed_granularities = _parse_granularity_list(
        env.get("WORKLOAD_ALLOWED_GRANULARITIES", "day,week,month"),
        errors,
        env_key="WORKLOAD_ALLOWED_GRANULARITIES",
    )
    default_granularity = _parse_granularity(
        env.get("WORKLOAD_DEFAULT_GRANULARITY", Granularity.WEEK.value),
        errors,
        env_key="WORKLOAD_DEFAULT_GRANULARITY",
    )

    if default_granularity and allowed_granularities:
        if default_granularity not in allowed_granularities:
            allowed_display = ", ".join(item.value for item in allowed_granularities)
            errors.append(
                "WORKLOAD_DEFAULT_GRANULARITY must be one of "
                f"{allowed_display}."
            )

    return DateDefaults(
        lookback_days=lookback_days,
        default_granularity=default_granularity or Granularity.WEEK,
        allowed_granularities=allowed_granularities or (Granularity.WEEK,),
    )


def _parse_storage_settings(env: Mapping[str, str]) -> StorageSettings:
    return StorageSettings(
        sqlite_path=env.get(
            "WORKLOAD_SQLITE_PATH",
            "var/workload_analytics.sqlite3",
        ).strip()
        or "var/workload_analytics.sqlite3"
    )


def _require(env: Mapping[str, str], key: str, errors: list[str]) -> str:
    value = env.get(key, "").strip()
    if value:
        return value
    errors.append(f"{key} is required.")
    return ""


def _parse_lookback_days(raw_value: str, errors: list[str]) -> int:
    try:
        value = int(raw_value)
    except ValueError:
        errors.append("WORKLOAD_LOOKBACK_DAYS must be an integer.")
        return 0

    if value <= 0:
        errors.append("WORKLOAD_LOOKBACK_DAYS must be greater than zero.")
        return 0

    return value


def _parse_granularity_list(
    raw_value: str,
    errors: list[str],
    *,
    env_key: str,
) -> tuple[Granularity, ...]:
    values = parse_csv_list(raw_value)
    if not values:
        errors.append(f"{env_key} must contain at least one granularity.")
        return ()

    granularities: list[Granularity] = []
    for value in values:
        granularity = _parse_granularity(value, errors, env_key=env_key)
        if granularity is not None and granularity not in granularities:
            granularities.append(granularity)

    return tuple(granularities)


def _parse_granularity(
    raw_value: str,
    errors: list[str],
    *,
    env_key: str,
) -> Granularity | None:
    normalized = raw_value.strip().lower()
    try:
        return Granularity(normalized)
    except ValueError:
        allowed = ", ".join(granularity.value for granularity in Granularity)
        errors.append(f"{env_key} must be one of {allowed}.")
        return None


def _parse_base_url(
    raw_value: str,
    errors: list[str],
    *,
    env_key: str,
) -> str:
    parsed = urlparse(raw_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{env_key} must be a valid http or https URL.")
        return ""
    return raw_value.rstrip("/")


def _parse_email(raw_value: str, *, env_key: str, errors: list[str]) -> str:
    _, address = parseaddr(raw_value)
    if "@" not in address or "." not in address.rsplit("@", 1)[-1]:
        errors.append(f"{env_key} must be a valid email address.")
        return ""
    return address.lower()


def _format_errors(errors: list[str]) -> str:
    unique_errors = list(dict.fromkeys(errors))
    return "Invalid configuration:\n- " + "\n- ".join(unique_errors)
