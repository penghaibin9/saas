"""A-W4 fixed-query Course Catalog dry-run bridge.

This is the bounded DB bridge between Academic File Exchange rows and the pure
Course import classifier. It owns no file/job lifecycle and never commits.

Query budget for one workbook (up to the existing 5000-row File Exchange cap):
- build the canonical affairs security context once using the same session;
- one tenant-scoped query for all existing Course versions of incoming codes;
- one tenant-scoped query for referenced owner colleges;
- one tenant-scoped query for referenced owner teachers.

There is deliberately no per-row SQL and no prerequisite existence query: the
current Course Authority validates prerequisite *code format* but does not make
catalog existence a create/update blocker.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Mapping

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context
from app.services.db_service import _tid, session

from .academic_affairs_school_setup_import_contract import RECONCILIATION_REJECT
from .academic_affairs_school_setup_import_adapter import normalize_course_import_row
from .academic_affairs_school_setup_import_preflight import course_catalog_preflight


def _reject(
    *,
    row_no: int,
    business_key: str,
    field: str,
    code: str,
    message: str,
    evidence: dict | None = None,
    how_to_resolve: str = "",
) -> tuple[dict, dict]:
    item = {
        "row": int(row_no),
        "businessKey": str(business_key or ""),
        "action": RECONCILIATION_REJECT,
        "code": code,
        "message": message,
        "evidence": dict(evidence or {}),
        "howToResolve": how_to_resolve,
    }
    error = {
        "row": int(row_no),
        "field": field,
        "code": code,
        "message": message,
        "evidence": dict(evidence or {}),
        "howToResolve": how_to_resolve,
    }
    return item, error


def _prerequisite_codes(value: object, *, business_key: str) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"existing Course {business_key} has corrupt prerequisiteCodes JSON") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"existing Course {business_key} has corrupt prerequisiteCodes JSON")
    return [item.strip().upper() for item in parsed if item.strip()]


def _existing_course_snapshot(course) -> dict:
    business_key = f"{str(course.course_code or '').strip().upper()}@v{int(course.version or 0)}"
    return {
        "courseId": int(course.id),
        "courseCode": str(course.course_code or "").strip().upper(),
        "version": int(course.version or 0),
        "prevVersionId": int(course.prev_version_id) if course.prev_version_id else None,
        "status": str(course.status or "").strip().upper(),
        "payload": {
            "courseCode": str(course.course_code or "").strip().upper(),
            "courseName": course.course_name,
            "courseNameEn": course.course_name_en,
            "category": course.category,
            "nature": course.nature,
            "credit": float(course.credit or 0),
            "hoursTotal": course.hours_total,
            "hoursTheory": course.hours_theory,
            "hoursPractice": course.hours_practice,
            "hoursExperiment": course.hours_experiment,
            "hoursComputer": course.hours_computer,
            "examMode": course.exam_mode,
            "ownerCollegeId": int(course.owner_college_id) if course.owner_college_id else None,
            "ownerTeacherId": int(course.owner_teacher_id) if course.owner_teacher_id else None,
            "isCore": bool(course.is_core),
            "description": course.description,
            "prerequisiteCodes": _prerequisite_codes(
                course.prerequisite_codes_json,
                business_key=business_key,
            ),
        },
    }


def _empty_result(total_rows: int, rejects: list[dict], errors: list[dict]) -> dict:
    return {
        "totalRows": int(total_rows),
        "validRows": 0,
        "invalidRows": len(rejects),
        "createRows": 0,
        "reuseRows": 0,
        "conflictRows": 0,
        "rejectRows": len(rejects),
        "items": sorted(rejects, key=lambda item: (item["row"], item["businessKey"])),
        "errors": sorted(errors, key=lambda item: (item["row"], item["code"])),
    }


def _merge_result(total_rows: int, classified: dict, rejects: list[dict], errors: list[dict]) -> dict:
    result = dict(classified)
    result["totalRows"] = int(total_rows)
    result["rejectRows"] = int(result.get("rejectRows") or 0) + len(rejects)
    result["invalidRows"] = int(result.get("invalidRows") or 0) + len(rejects)
    result["items"] = sorted(
        [*(result.get("items") or []), *rejects],
        key=lambda item: (int(item.get("row") or 0), str(item.get("businessKey") or "")),
    )
    result["errors"] = sorted(
        [*(result.get("errors") or []), *errors],
        key=lambda item: (int(item.get("row") or 0), str(item.get("code") or "")),
    )
    return result


def _reject_duplicate_source_keys(
    normalized: list[dict],
    rejects: list[dict],
    errors: list[dict],
) -> list[dict]:
    """Reject every occurrence before any reference filtering can hide a duplicate."""
    counts = Counter(str(item["businessKey"]) for item in normalized)
    unique_rows: list[dict] = []
    for item in normalized:
        business_key = str(item["businessKey"])
        if counts[business_key] <= 1:
            unique_rows.append(item)
            continue
        reject, error = _reject(
            row_no=item["rowNo"],
            business_key=business_key,
            field="courseCode/version",
            code="DUPLICATE_SOURCE_KEY",
            message="同一文件内课程稳定键重复，禁止按行顺序猜测覆盖关系",
            evidence={"businessKey": business_key, "sourceOccurrences": counts[business_key]},
            how_to_resolve="每个 courseCode + version 仅保留一行后重新预检",
        )
        rejects.append(reject)
        errors.append(error)
    return unique_rows


def course_catalog_dry_run(rows: list[Mapping[str, object]], user: dict) -> dict:
    """Dry-run Course Catalog rows with a fixed query count and zero writes."""
    source_rows = [dict(row) for row in (rows or [])]
    normalized: list[dict] = []
    rejects: list[dict] = []
    errors: list[dict] = []

    for row_no, raw in enumerate(source_rows, start=2):
        try:
            normalized.append(normalize_course_import_row(raw, row_no=row_no))
        except ValueError as exc:
            item, error = _reject(
                row_no=row_no,
                business_key="",
                field="row",
                code="COURSE_ROW_INVALID",
                message=str(exc),
                how_to_resolve="按课程导入模板修正该行后重新预检",
            )
            rejects.append(item)
            errors.append(error)

    normalized = _reject_duplicate_source_keys(normalized, rejects, errors)
    if not normalized:
        return _empty_result(len(source_rows), rejects, errors)

    course_codes = {str(item["courseCode"]).strip().upper() for item in normalized}
    owner_college_ids = {
        int(item["payload"]["ownerCollegeId"])
        for item in normalized
        if item["payload"].get("ownerCollegeId") is not None
    }
    owner_teacher_ids = {
        int(item["payload"]["ownerTeacherId"])
        for item in normalized
        if item["payload"].get("ownerTeacherId") is not None
    }

    from app.models import AaCourse, College, User

    with session() as db:
        security = build_affairs_context(user, db)
        existing_rows = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == _tid(),
            AaCourse.course_code.in_(sorted(course_codes)),
            AaCourse.is_deleted.is_(False),
        ).order_by(AaCourse.course_code, AaCourse.version, AaCourse.id)).all()
        college_rows = []
        if owner_college_ids:
            college_rows = db.scalars(select(College).where(
                College.tenant_id == _tid(),
                College.id.in_(sorted(owner_college_ids)),
                College.is_deleted.is_(False),
            )).all()
        teacher_rows = []
        if owner_teacher_ids:
            teacher_rows = db.scalars(select(User).where(
                User.tenant_id == _tid(),
                User.id.in_(sorted(owner_teacher_ids)),
                User.is_deleted.is_(False),
            )).all()

    existing_snapshots = [_existing_course_snapshot(course) for course in existing_rows]
    valid_college_ids = {
        int(row.id) for row in college_rows if str(row.status or "").strip().upper() == "ACTIVE"
    }
    valid_teacher_ids = {
        int(row.id)
        for row in teacher_rows
        if str(row.user_type or "").strip().upper() == "TEACHER"
        and str(row.status or "").strip().upper() == "ACTIVE"
    }

    role = str((user or {}).get("currentRoleCode") or "").strip().upper()
    allowed_college_ids: set[int] | None = None
    if role == "COLLEGE_ADMIN":
        allowed_college_ids = (
            {int(value) for value in security.college_ids}
            if security.scope_type == "COLLEGE"
            else set()
        )

    classifiable: list[dict] = []
    for item in normalized:
        payload = dict(item.get("payload") or {})
        owner_college_id = payload.get("ownerCollegeId")
        owner_teacher_id = payload.get("ownerTeacherId")
        if owner_college_id is not None and int(owner_college_id) not in valid_college_ids:
            reject, error = _reject(
                row_no=item["rowNo"],
                business_key=item["businessKey"],
                field="ownerCollegeId",
                code="COURSE_OWNER_COLLEGE_INVALID",
                message="开课单位不存在、已停用或不属于当前学校",
                evidence={"ownerCollegeId": str(owner_college_id)},
                how_to_resolve="改为当前学校有效学院 ID 后重新预检",
            )
            rejects.append(reject)
            errors.append(error)
            continue
        if owner_teacher_id is not None and int(owner_teacher_id) not in valid_teacher_ids:
            reject, error = _reject(
                row_no=item["rowNo"],
                business_key=item["businessKey"],
                field="ownerTeacherId",
                code="COURSE_OWNER_TEACHER_INVALID",
                message="课程负责人不存在、非教师、已停用或不属于当前学校",
                evidence={"ownerTeacherId": str(owner_teacher_id)},
                how_to_resolve="改为当前学校在职教师 ID 后重新预检",
            )
            rejects.append(reject)
            errors.append(error)
            continue
        classifiable.append(item)

    if not classifiable:
        return _empty_result(len(source_rows), rejects, errors)

    classified = course_catalog_preflight(
        classifiable,
        existing_snapshots,
        allowed_college_ids=allowed_college_ids,
    )
    return _merge_result(len(source_rows), classified, rejects, errors)
