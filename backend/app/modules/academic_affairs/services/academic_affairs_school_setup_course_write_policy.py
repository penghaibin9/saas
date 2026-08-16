"""A-W4 pure Course import write projection.

The policy is deliberately DB-free.  It freezes which workbook-asserted facts
may overwrite a Course row and which canonical Course facts must be inherited
when an import creates the direct successor of an existing ENABLED version.

Why this exists separately from ``academic_affairs_course_service._apply_fields``:
that legacy/page writer assigns defaults for fields missing from its body.  The
current ``course-catalog-v1`` workbook cannot express every Course field, so
reusing `_apply_fields` for an imported v+1 would silently clear predecessor
facts such as applicable majors.
"""
from __future__ import annotations

from typing import Mapping

_TEMPLATE_ASSERTED_FIELDS = (
    "courseCode",
    "courseName",
    "category",
    "nature",
    "credit",
    "hoursTotal",
    "hoursTheory",
    "hoursPractice",
    "hoursExperiment",
    "hoursComputer",
    "examMode",
    "ownerCollegeId",
    "ownerTeacherId",
    "isCore",
    "prerequisiteCodes",
)

_INHERITED_NON_TEMPLATE_FIELDS = (
    "courseNameEn",
    "description",
    "applicableMajors",
    "isAllMajor",
)


def _positive_int(value: object, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _course_code(value: object) -> str:
    code = str(value or "").strip().upper()
    if not code:
        raise ValueError("courseCode is required")
    return code


def _asserted_payload(item: Mapping[str, object]) -> dict:
    payload = dict(item.get("payload") or {})
    code = _course_code(item.get("courseCode") or payload.get("courseCode"))
    projected = {field: payload.get(field) for field in _TEMPLATE_ASSERTED_FIELDS}
    projected["courseCode"] = code
    return projected


def new_v1_write_projection(item: Mapping[str, object]) -> dict:
    """Projection for a brand-new Course stable identity.

    Non-template fields receive explicit safe defaults only for v1 because
    there is no predecessor truth to preserve.
    """
    version = _positive_int(item.get("version"), field="version")
    if version != 1:
        raise ValueError("new Course import must start at version 1")
    payload = _asserted_payload(item)
    payload.update({
        "courseNameEn": None,
        "description": None,
        "applicableMajors": [],
        "isAllMajor": False,
    })
    return {
        "courseCode": payload["courseCode"],
        "version": 1,
        "prevVersionId": None,
        "status": "DRAFT",
        "payload": payload,
    }


def successor_write_projection(
    item: Mapping[str, object],
    predecessor: Mapping[str, object],
) -> dict:
    """Projection for the single direct successor of a persisted Course.

    Version/prev/status are generated from the locked predecessor, not trusted
    from workbook-internal IDs.  Workbook-asserted fields overwrite only the
    current template surface; non-template fields are inherited verbatim.
    """
    incoming_code = _course_code(item.get("courseCode"))
    predecessor_code = _course_code(predecessor.get("courseCode"))
    if incoming_code != predecessor_code:
        raise ValueError("successor courseCode must match predecessor")

    predecessor_id = _positive_int(predecessor.get("courseId"), field="predecessor.courseId")
    predecessor_version = _positive_int(
        predecessor.get("version"), field="predecessor.version"
    )
    requested_version = _positive_int(item.get("version"), field="version")
    expected_version = predecessor_version + 1
    if requested_version != expected_version:
        raise ValueError(
            f"successor version must be direct v{expected_version}, got v{requested_version}"
        )
    predecessor_status = str(predecessor.get("status") or "").strip().upper()
    if predecessor_status != "ENABLED":
        raise ValueError("successor predecessor must be ENABLED")

    payload = _asserted_payload(item)
    for field in _INHERITED_NON_TEMPLATE_FIELDS:
        payload[field] = predecessor.get(field)
    payload["applicableMajors"] = list(payload.get("applicableMajors") or [])
    payload["isAllMajor"] = bool(payload.get("isAllMajor"))

    return {
        "courseCode": predecessor_code,
        "version": expected_version,
        "prevVersionId": predecessor_id,
        "status": "DRAFT",
        "payload": payload,
    }


def course_import_write_projection(
    item: Mapping[str, object],
    *,
    predecessor: Mapping[str, object] | None,
) -> dict:
    return (
        new_v1_write_projection(item)
        if predecessor is None
        else successor_write_projection(item, predecessor)
    )


def course_import_write_contract() -> dict:
    return {
        "templateAssertedFields": list(_TEMPLATE_ASSERTED_FIELDS),
        "successorInheritedFields": list(_INHERITED_NON_TEMPLATE_FIELDS),
        "authorityGeneratedFields": ["version", "prevVersionId", "status"],
        "newStatus": "DRAFT",
    }
