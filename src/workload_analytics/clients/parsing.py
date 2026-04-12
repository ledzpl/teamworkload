from __future__ import annotations

from datetime import datetime


def parse_datetime(raw_value: str | None) -> datetime | None:
    if raw_value is None:
        return None
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))


def normalize_optional_email(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip().lower()
    return normalized or None
