"""INT pure Program workbook adapter for Academic File Exchange.

The shared file/job/parser lifecycle is intentionally not imported here. This
module only normalizes already-parsed logical Program rows into a canonical,
deterministic representation that later preflight/confirm code may consume. It
performs no database I/O and never invents Program identity from major, grade,
binding scope, or display names.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    BINDING_SCOPE_CLASS,
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_GRADUATION,
    PROGRAM_GROUP_MAIN,
    PROGRAM_GROUP_PRACTICE,
    PROGRAM_LOGICAL_GROUPS,
    PROGRAM_REQUIRED_FIELDS_BY_GROUP,
    missing_required_fields,
    program_binding_key,
    program_course_reference,
    program_credit_requirement,
    program_graduation_requirement,
    program_practice_segment,
    program_version_key,
)


def _positive_row_no(value) -> int:
    try:
        row_no = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("row_no must be a positive integer") from exc
    if row_no <= 0:
        raise ValueError("row_no must be a positive integer")
    return row_no


def _required_text(value, *, field: str, uppercase: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text.upper() if uppercase else text


def _positive_int(value, *, field: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _positive_decimal(value, *, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive number") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive number")
    return parsed


def _optional_positive_int(value, *, field: str) -> int | None:
    if not str(value if value is not None else "").strip():
        return None
    return _positive_int(value, field=field)


def _optional_sort_order(value) -> int:
    if not str(value if value is not None else "").strip():
        return 0
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("sortOrder must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError("sortOrder must be a non-negative integer")
    return parsed


def _logical_group(value: object) -> str:
    group = _required_text(value, field="logicalGroup", uppercase=True)
    if group not in PROGRAM_LOGICAL_GROUPS:
        raise ValueError(f"unsupported logicalGroup: {group}")
    return group


def _definition_key(parts: Iterable[object]) -> str:
    """Deterministic source-set key; not a replacement for domain identity."""
    return "|".join(str(part if part is not None else "").strip() for part in parts)


def normalize_program_import_row(
    logical_group: object,
    row: Mapping[str, object],
    *,
    row_no: int,
) -> dict:
    """Normalize one Program logical row with zero database access."""
    group = _logical_group(logical_group)
    row_number = _positive_row_no(row_no)
    missing = missing_required_fields(row, PROGRAM_REQUIRED_FIELDS_BY_GROUP[group])
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    program = program_version_key(row)
    program_key = program.text()

    if group == PROGRAM_GROUP_MAIN:
        grade_year = _required_text(row.get("gradeYear"), field="gradeYear")
        if len(grade_year) != 4 or not grade_year.isdigit():
            raise ValueError("gradeYear must be a four-digit year")
        payload = {
            "programSeriesKey": program.series_key,
            "programVersion": program.version,
            "programName": _required_text(row.get("programName"), field="programName"),
            "majorId": _positive_int(row.get("majorId"), field="majorId"),
            "gradeYear": grade_year,
            "totalCredits": _positive_decimal(row.get("totalCredits"), field="totalCredits"),
            # Optional source assertion only. Preflight compares it with Major.education_years;
            # confirm must never write organization master data from this field.
            "educationYearsAssertion": _optional_positive_int(
                row.get("educationYears"), field="educationYears"
            ),
        }
        definition_key = program_key

    elif group == PROGRAM_GROUP_COURSE:
        payload = program_course_reference(row)
        definition_key = _definition_key((program_key, "COURSE", payload["courseKey"]))

    elif group == PROGRAM_GROUP_CREDIT_REQUIREMENT:
        payload = program_credit_requirement(row)
        definition_key = _definition_key((program_key, "CREDIT", payload["module"]))

    elif group == PROGRAM_GROUP_PRACTICE:
        payload = program_practice_segment(row)
        payload["sortOrder"] = _optional_sort_order(row.get("sortOrder"))
        definition_key = _definition_key((
            program_key,
            "PRACTICE",
            payload["segmentType"],
            payload["segmentName"],
            payload["openTermNo"],
        ))

    elif group == PROGRAM_GROUP_GRADUATION:
        payload = program_graduation_requirement(row)
        payload["sortOrder"] = _optional_sort_order(row.get("sortOrder"))
        definition_key = _definition_key((
            program_key,
            "GRADUATION",
            payload["category"],
            payload["content"],
        ))

    elif group == PROGRAM_GROUP_BINDING:
        binding = program_binding_key(row)
        payload = {
            "programKey": binding.program.text(),
            "majorId": binding.major_id,
            "gradeYear": binding.grade_year,
            "bindingScope": binding.scope,
            "classId": binding.class_id if binding.scope == BINDING_SCOPE_CLASS else None,
        }
        definition_key = binding.text()

    else:  # pragma: no cover - _logical_group already fails closed
        raise AssertionError(f"unhandled logical group: {group}")

    return {
        "rowNo": row_number,
        "logicalGroup": group,
        "programKey": program_key,
        "definitionKey": definition_key,
        "payload": payload,
    }


def normalize_program_import_rows(
    grouped_rows: Mapping[str, Iterable[Mapping[str, object]]],
    *,
    first_data_row: int = 2,
) -> list[dict]:
    """Normalize all supplied logical groups in fixed canonical group order.

    Missing groups are preserved as absence for later whole-workbook preflight;
    this function does not silently manufacture rows. Row numbers restart per
    worksheet because File Exchange errors are reported together with group.
    """
    start = _positive_row_no(first_data_row)
    unknown = sorted(set(str(key).strip().upper() for key in grouped_rows) - PROGRAM_LOGICAL_GROUPS)
    if unknown:
        raise ValueError(f"unsupported logical groups: {', '.join(unknown)}")

    ordered_groups = (
        PROGRAM_GROUP_MAIN,
        PROGRAM_GROUP_COURSE,
        PROGRAM_GROUP_CREDIT_REQUIREMENT,
        PROGRAM_GROUP_PRACTICE,
        PROGRAM_GROUP_GRADUATION,
        PROGRAM_GROUP_BINDING,
    )
    normalized: list[dict] = []
    for group in ordered_groups:
        rows = list(grouped_rows.get(group, ()) or ())
        normalized.extend(
            normalize_program_import_row(group, row, row_no=start + index)
            for index, row in enumerate(rows)
        )
    return normalized
