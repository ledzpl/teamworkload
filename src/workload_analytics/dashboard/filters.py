from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from workload_analytics.config import Granularity


@dataclass(frozen=True, slots=True)
class DashboardFilterState:
    start_date: date
    end_date: date
    granularity: Granularity
    developer_email: str | None = None


def normalize_developer_selection(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip().lower()
    if not normalized or normalized in {"all", "all team"}:
        return None
    return normalized
