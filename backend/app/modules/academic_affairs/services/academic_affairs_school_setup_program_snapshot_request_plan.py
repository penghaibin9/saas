"""INT bounded snapshot request planner for Program import preflight.

This pure module derives the exact tenant-scoped lookup keys a future DB bridge
is allowed to query. It does not open a session and does not know SQLAlchemy.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    BINDING_SCOPE_CLASS,
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_MAIN,
)


def _series_key(program_key: object) -> str:
    text = str(program_key or "").strip()
    if not text.startswith("SERIES:") or ":v" not in text:
        raise ValueError(f"invalid normalized programKey: {text}")
    series_key, raw_version = text.removeprefix("SERIES:").rsplit(":v", 1)
    if not series_key or not raw_version.isdigit() or int(raw_version) <= 0:
        raise ValueError(f"invalid normalized programKey: {text}")
    return series_key


def binding_scope_key(payload: Mapping[str, object]) -> str:
    major_id = int(payload.get("majorId") or 0)
    grade_year = str(payload.get("gradeYear") or "").strip()
    scope = str(payload.get("bindingScope") or "").strip().upper()
    if major_id <= 0 or not grade_year:
        raise ValueError("normalized binding payload missing majorId/gradeYear")
    if scope == BINDING_SCOPE_CLASS:
        class_id = int(payload.get("classId") or 0)
        if class_id <= 0:
            raise ValueError("normalized CLASS binding missing classId")
        return f"MAJOR:{major_id}:GRADE:{grade_year}:CLASS:{class_id}"
    if scope == "MAJOR_GRADE":
        return f"MAJOR:{major_id}:GRADE:{grade_year}:MAJOR_GRADE"
    raise ValueError(f"unsupported normalized bindingScope: {scope}")


def plan_program_snapshot_requests(rows: Iterable[Mapping[str, object]]) -> dict:
    major_ids: set[int] = set()
    class_ids: set[int] = set()
    course_keys: set[str] = set()
    series_keys: set[str] = set()
    binding_scope_keys: set[str] = set()

    for raw in rows:
        row = dict(raw)
        group = str(row.get("logicalGroup") or "").strip().upper()
        series_keys.add(_series_key(row.get("programKey")))
        payload = dict(row.get("payload") or {})
        if group == PROGRAM_GROUP_MAIN:
            major_id = int(payload.get("majorId") or 0)
            if major_id <= 0:
                raise ValueError("normalized MAIN payload missing majorId")
            major_ids.add(major_id)
        elif group == PROGRAM_GROUP_COURSE:
            course_key = str(payload.get("courseKey") or "").strip()
            if not course_key:
                raise ValueError("normalized COURSE payload missing courseKey")
            course_keys.add(course_key)
        elif group == PROGRAM_GROUP_BINDING:
            binding_scope_keys.add(binding_scope_key(payload))
            if str(payload.get("bindingScope") or "").strip().upper() == BINDING_SCOPE_CLASS:
                class_ids.add(int(payload.get("classId") or 0))

    return {
        "majorIds": tuple(sorted(major_ids)),
        "classIds": tuple(sorted(class_ids)),
        "courseKeys": tuple(sorted(course_keys)),
        "seriesKeys": tuple(sorted(series_keys)),
        "bindingScopeKeys": tuple(sorted(binding_scope_keys)),
    }
