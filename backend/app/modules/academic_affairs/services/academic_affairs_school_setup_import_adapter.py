"""A-W4 domain adapters for Course/Program rows entering Academic File Exchange.

The existing Academic File Exchange remains the only file/job/parser lifecycle.
This module only normalizes already-parsed logical rows into canonical domain
payloads.  It performs no database I/O and never confirms/writes an import.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Mapping

from . import academic_affairs_course_service as course_service
from .academic_affairs_school_setup_import_contract import (
    COURSE_REQUIRED_FIELDS,
    course_business_key,
    missing_required_fields,
)

_TRUE_VALUES = frozenset({"1", "TRUE", "YES", "Y", "是"})
_FALSE_VALUES = frozenset({"0", "FALSE", "NO", "N", "否", ""})
_SPLIT_CODES = re.compile(r"[,，;；\s]+")


def _required_text(value, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _optional_text(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value, *, field: str, required: bool = False) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def _integer(value, *, field: str, required: bool = False, minimum: int = 0) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        parsed = int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return parsed


def _boolean(value, *, field: str) -> bool:
    text = str(value if value is not None else "").strip().upper()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise ValueError(f"{field} must be yes/no")


def _code_list(value) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in _SPLIT_CODES.split(text):
        code = item.strip().upper()
        if not code or code in seen:
            continue
        if not course_service._CODE_RE.match(code):
            raise ValueError(f"invalid prerequisite courseCode: {code}")
        seen.add(code)
        result.append(code)
    return result


def normalize_course_import_row(row: Mapping[str, object], *, row_no: int) -> dict:
    """Normalize one Course Catalog row without consulting names as identity.

    The result is intentionally shaped like the existing Course domain writer
    payload while retaining the explicit imported ``version`` separately. The
    later dry-run/confirm layer decides CREATE/REUSE/CONFLICT/REJECT against the
    database; this adapter never guesses from current rows.
    """
    row_no = int(row_no)
    if row_no <= 0:
        raise ValueError("row_no must be positive")

    missing = missing_required_fields(row, COURSE_REQUIRED_FIELDS)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    key = course_business_key(row)
    if not course_service._CODE_RE.match(key.course_code):
        raise ValueError("courseCode format is invalid")

    category = _required_text(row.get("category"), field="category").upper()
    nature = _required_text(row.get("nature"), field="nature").upper()
    exam_mode = _required_text(row.get("examMode"), field="examMode").upper()
    if category not in course_service.CATEGORIES:
        raise ValueError(f"unsupported category: {category}")
    if nature not in course_service.NATURES:
        raise ValueError(f"unsupported nature: {nature}")
    if exam_mode not in course_service.EXAM_MODES:
        raise ValueError(f"unsupported examMode: {exam_mode}")

    credit = _decimal(row.get("credit"), field="credit", required=True)
    hours_total = _integer(row.get("hoursTotal"), field="hoursTotal")
    hours_theory = _integer(row.get("hoursTheory"), field="hoursTheory")
    hours_practice = _integer(row.get("hoursPractice"), field="hoursPractice")
    hours_experiment = _integer(row.get("hoursExperiment"), field="hoursExperiment")
    hours_computer = _integer(row.get("hoursComputer"), field="hoursComputer")
    parts = [hours_theory, hours_practice, hours_experiment, hours_computer]
    populated_parts = [value for value in parts if value is not None]
    if hours_total is not None and populated_parts and sum(populated_parts) != hours_total:
        raise ValueError(
            f"hour components sum({sum(populated_parts)}) != hoursTotal({hours_total})"
        )

    owner_college_id = _integer(row.get("ownerCollegeId"), field="ownerCollegeId", minimum=1)
    owner_teacher_id = _integer(row.get("ownerTeacherId"), field="ownerTeacherId", minimum=1)

    payload = {
        "courseCode": key.course_code,
        "courseName": _required_text(row.get("courseName"), field="courseName"),
        "courseNameEn": _optional_text(row.get("courseNameEn")),
        "category": category,
        "nature": nature,
        "credit": float(credit),
        "hoursTotal": hours_total,
        "hoursTheory": hours_theory,
        "hoursPractice": hours_practice,
        "hoursExperiment": hours_experiment,
        "hoursComputer": hours_computer,
        "examMode": exam_mode,
        "ownerCollegeId": owner_college_id,
        "ownerTeacherId": owner_teacher_id,
        "isCore": _boolean(row.get("isCore"), field="isCore"),
        "description": _optional_text(row.get("description")),
        "prerequisiteCodes": _code_list(row.get("prerequisiteCodes")),
    }
    return {
        "rowNo": row_no,
        "businessKey": key.text(),
        "courseCode": key.course_code,
        "version": key.version,
        "payload": payload,
    }


def normalize_course_import_rows(rows: list[Mapping[str, object]]) -> list[dict]:
    """Normalize all rows; caller owns error aggregation and File Exchange state."""
    return [normalize_course_import_row(row, row_no=index) for index, row in enumerate(rows, start=2)]
