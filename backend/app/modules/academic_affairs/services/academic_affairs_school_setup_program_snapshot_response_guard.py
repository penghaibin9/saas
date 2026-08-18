"""INT fail-closed guards for bounded Program preflight snapshot loaders.

Request planning alone is not enough: a future DB bridge can still accidentally
return rows outside the requested tenant-scoped keys. These pure guards prove the
loader response is a subset of the exact request before any classifier consumes
it. Missing requested rows are allowed because downstream preflight must report
NOT_FOUND; extra rows are a bridge contract violation and fail closed.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .academic_affairs_school_setup_program_snapshot_request_plan import (
    binding_scope_key,
)


def _allowed_text(values: Iterable[object]) -> set[str]:
    return {str(value).strip() for value in values if str(value).strip()}


def _violation(kind: str, returned: object, requested: Iterable[object]) -> RuntimeError:
    return RuntimeError(
        f"PROGRAM_SNAPSHOT_SCOPE_VIOLATION:{kind}:returned={returned}:"
        f"requested={sorted(str(value) for value in requested)}"
    )


def guard_major_snapshots(
    rows: Iterable[Mapping[str, object]], requested_ids: Iterable[int]
) -> list[dict]:
    requested = {int(value) for value in requested_ids}
    result = [dict(row) for row in rows]
    for row in result:
        try:
            major_id = int(row.get("majorId"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("PROGRAM_SNAPSHOT_SCOPE_VIOLATION:MAJOR:missing majorId") from exc
        if major_id not in requested:
            raise _violation("MAJOR", major_id, requested)
    return result


def guard_class_snapshots(
    rows: Iterable[Mapping[str, object]], requested_ids: Iterable[int]
) -> list[dict]:
    requested = {int(value) for value in requested_ids}
    result = [dict(row) for row in rows]
    for row in result:
        try:
            class_id = int(row.get("classId"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("PROGRAM_SNAPSHOT_SCOPE_VIOLATION:CLASS:missing classId") from exc
        if class_id not in requested:
            raise _violation("CLASS", class_id, requested)
    return result


def guard_course_snapshots(
    rows: Iterable[Mapping[str, object]], requested_keys: Iterable[str]
) -> list[dict]:
    requested = {str(value).strip().upper() for value in requested_keys}
    result = [dict(row) for row in rows]
    for row in result:
        code = str(row.get("courseCode") or "").strip().upper()
        try:
            version = int(row.get("version") or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("PROGRAM_SNAPSHOT_SCOPE_VIOLATION:COURSE:invalid version") from exc
        key = f"{code}@V{version}"
        if not code or version <= 0 or key not in requested:
            raise _violation("COURSE", key, requested)
    return result


def guard_program_snapshots(
    rows: Iterable[Mapping[str, object]], requested_series_keys: Iterable[str]
) -> list[dict]:
    requested = {str(value).strip().upper() for value in requested_series_keys}
    result = [dict(row) for row in rows]
    for row in result:
        series_key = str(row.get("seriesKey") or "").strip().upper()
        if not series_key or series_key not in requested:
            raise _violation("PROGRAM_SERIES", series_key or "<missing>", requested)
    return result


def guard_definition_snapshots(
    rows: Iterable[Mapping[str, object]], requested_program_ids: Iterable[str]
) -> list[dict]:
    requested = _allowed_text(requested_program_ids)
    result = [dict(row) for row in rows]
    for row in result:
        program_id = str(row.get("programId") or "").strip()
        if not program_id or program_id not in requested:
            raise _violation("PROGRAM_DEFINITION", program_id or "<missing>", requested)
    return result


def guard_program_status_by_id(
    statuses: Mapping[str, object], requested_program_ids: Iterable[str]
) -> dict[str, object]:
    requested = _allowed_text(requested_program_ids)
    result = {str(key).strip(): value for key, value in statuses.items()}
    for program_id in result:
        if not program_id or program_id not in requested:
            raise _violation("PROGRAM_STATUS", program_id or "<missing>", requested)
    return result


def guard_active_binding_snapshots(
    rows: Iterable[Mapping[str, object]], requested_scope_keys: Iterable[str]
) -> list[dict]:
    requested = _allowed_text(requested_scope_keys)
    result = [dict(row) for row in rows]
    for row in result:
        scope_key = str(row.get("scopeKey") or "").strip()
        if not scope_key:
            scope_key = binding_scope_key(row)
        if scope_key not in requested:
            raise _violation("ACTIVE_BINDING", scope_key, requested)
    return result
