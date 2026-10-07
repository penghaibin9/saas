from __future__ import annotations

from datetime import datetime, timezone


def naive_utc(value: datetime | None) -> datetime | None:
    """Normalize transport-aware datetimes to the repository's naive UTC convention."""
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
