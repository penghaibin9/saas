"""A-W4 Course Catalog atomic confirm writer.

This service owns only the Course domain transaction. FileObject/ImportJob
lease/version state remains in the shared Data Exchange authority and is wired by
INT later. A confirm therefore receives rows re-read from the authoritative
source file and applies them in exactly one Course transaction.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_course_service as _course_core
from .academic_affairs_school_setup_course_preflight_service import (
    _course_catalog_dry_run_with_db,
)
from .academic_affairs_school_setup_course_write_policy import (
    course_import_write_projection,
)
from .academic_affairs_school_setup_import_adapter import normalize_course_import_row
from .academic_affairs_school_setup_import_contract import (
    RECONCILIATION_CREATE,
    RECONCILIATION_REUSE,
)


def _normalized_rows(rows: list[Mapping[str, object]]) -> list[dict]:
    return [
        normalize_course_import_row(dict(raw), row_no=row_no)
        for row_no, raw in enumerate(rows, start=2)
    ]


def _stable_pair(item: Mapping[str, object]) -> tuple[str, int]:
    return str(item.get("courseCode") or "").strip().upper(), int(item.get("version") or 0)


def _action_index(preview: Mapping[str, object]) -> dict[tuple[int, str], dict]:
    result: dict[tuple[int, str], dict] = {}
    for raw in preview.get("items") or []:
        item = dict(raw)
        key = (int(item.get("row") or 0), str(item.get("businessKey") or ""))
        if key in result:
            raise AppException(
                "DATA_CONFLICT",
                "课程导入预检结果出现重复行标识，拒绝确认",
                details={"row": key[0], "businessKey": key[1]},
                http_status=409,
            )
        result[key] = item
    return result


def _db_error_code(exc: Exception) -> int | None:
    args = getattr(getattr(exc, "orig", None), "args", ()) or ()
    if not args:
        return None
    try:
        return int(args[0])
    except (TypeError, ValueError):
        return None


def _is_course_unique_conflict(exc: IntegrityError) -> bool:
    text = str(getattr(exc, "orig", exc)).lower()
    code = _db_error_code(exc)
    return (
        code == 1062
        and "duplicate entry" in text
        and "uk_aa_course" in text
    )


def _is_mysql_lock_conflict(exc: OperationalError) -> bool:
    return _db_error_code(exc) in {1205, 1213}


def _predecessor_snapshot(course) -> dict:
    try:
        applicable_majors = json.loads(course.applicable_majors_json) if course.applicable_majors_json else []
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppException(
            "DATA_CONFLICT",
            "课程历史版本的适用专业数据损坏，拒绝生成后继版本",
            details={"courseId": str(course.id), "courseCode": course.course_code, "version": course.version},
            http_status=409,
        ) from exc
    if not isinstance(applicable_majors, list):
        raise AppException(
            "DATA_CONFLICT",
            "课程历史版本的适用专业数据损坏，拒绝生成后继版本",
            details={"courseId": str(course.id), "courseCode": course.course_code, "version": course.version},
            http_status=409,
        )
    return {
        "courseId": int(course.id),
        "courseCode": str(course.course_code or "").strip().upper(),
        "version": int(course.version or 0),
        "status": str(course.status or "").strip().upper(),
        "courseNameEn": course.course_name_en,
        "description": course.description,
        "applicableMajors": list(applicable_majors),
        "isAllMajor": bool(course.is_all_major),
    }


def _index_predecessors(
    locked_course_rows: list[object],
    normalized: list[dict],
    action_by_row: dict[tuple[int, str], dict],
) -> dict[tuple[str, int], object]:
    """Index predecessor rows already locked by confirm preflight; never query again."""
    wanted: set[tuple[str, int]] = set()
    for item in normalized:
        action = action_by_row[(int(item["rowNo"]), str(item["businessKey"]))]
        if action.get("action") != RECONCILIATION_CREATE or int(item["version"]) == 1:
            continue
        wanted.add((str(item["courseCode"]).strip().upper(), int(item["version"]) - 1))
    if not wanted:
        return {}

    indexed = {
        (str(row.course_code or "").strip().upper(), int(row.version or 0)): row
        for row in locked_course_rows
        if (str(row.course_code or "").strip().upper(), int(row.version or 0)) in wanted
    }
    missing = sorted(wanted - set(indexed))
    if missing:
        raise AppException(
            "DATA_CONFLICT",
            "课程版本链在确认期间发生变化，请重新预检",
            details={"missingPredecessors": [f"{code}@v{version}" for code, version in missing]},
            http_status=409,
        )
    return indexed


def _apply_projection(course, projection: Mapping[str, object]) -> None:
    payload = dict(projection.get("payload") or {})
    course.course_name = payload["courseName"]
    course.course_name_en = payload.get("courseNameEn")
    course.category = payload["category"]
    course.nature = payload["nature"]
    course.credit = payload.get("credit") or 0
    course.hours_total = payload.get("hoursTotal")
    course.hours_theory = payload.get("hoursTheory")
    course.hours_practice = payload.get("hoursPractice")
    course.hours_experiment = payload.get("hoursExperiment")
    course.hours_computer = payload.get("hoursComputer")
    course.exam_mode = payload["examMode"]
    course.owner_college_id = int(payload["ownerCollegeId"]) if payload.get("ownerCollegeId") is not None else None
    course.owner_teacher_id = int(payload["ownerTeacherId"]) if payload.get("ownerTeacherId") is not None else None
    course.is_core = bool(payload.get("isCore"))
    course.prerequisite_codes_json = json.dumps(payload.get("prerequisiteCodes") or [], ensure_ascii=False)
    course.description = payload.get("description")
    course.applicable_majors_json = json.dumps(payload.get("applicableMajors") or [], ensure_ascii=False)
    course.is_all_major = bool(payload.get("isAllMajor"))


def _projection_facts(course) -> dict:
    return {
        "courseCode": str(course.course_code or "").strip().upper(),
        "version": int(course.version or 0),
        "prevVersionId": int(course.prev_version_id) if course.prev_version_id else None,
        "status": str(course.status or "").strip().upper(),
        "payload": {
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
            "prerequisiteCodes": json.loads(course.prerequisite_codes_json) if course.prerequisite_codes_json else [],
            "description": course.description,
            "applicableMajors": json.loads(course.applicable_majors_json) if course.applicable_majors_json else [],
            "isAllMajor": bool(course.is_all_major),
        },
    }


def _expected_facts(projection: Mapping[str, object]) -> dict:
    payload = dict(projection.get("payload") or {})
    return {
        "courseCode": str(projection.get("courseCode") or "").strip().upper(),
        "version": int(projection.get("version") or 0),
        "prevVersionId": int(projection["prevVersionId"]) if projection.get("prevVersionId") else None,
        "status": str(projection.get("status") or "").strip().upper(),
        "payload": {
            "courseName": payload.get("courseName"),
            "courseNameEn": payload.get("courseNameEn"),
            "category": payload.get("category"),
            "nature": payload.get("nature"),
            "credit": float(payload.get("credit") or 0),
            "hoursTotal": payload.get("hoursTotal"),
            "hoursTheory": payload.get("hoursTheory"),
            "hoursPractice": payload.get("hoursPractice"),
            "hoursExperiment": payload.get("hoursExperiment"),
            "hoursComputer": payload.get("hoursComputer"),
            "examMode": payload.get("examMode"),
            "ownerCollegeId": int(payload["ownerCollegeId"]) if payload.get("ownerCollegeId") is not None else None,
            "ownerTeacherId": int(payload["ownerTeacherId"]) if payload.get("ownerTeacherId") is not None else None,
            "isCore": bool(payload.get("isCore")),
            "prerequisiteCodes": list(payload.get("prerequisiteCodes") or []),
            "description": payload.get("description"),
            "applicableMajors": list(payload.get("applicableMajors") or []),
            "isAllMajor": bool(payload.get("isAllMajor")),
        },
    }


def _reread_reconciliation(
    db,
    normalized: list[dict],
    preview: Mapping[str, object],
    created: list[tuple[object, dict, dict]],
) -> tuple[list[dict], list[int]]:
    """Re-read every source stable key inside the same transaction.

    A bounded query covers CREATE and REUSE rows. CREATE rows additionally prove
    every persisted field equals the write projection; all rows receive the
    authoritative courseId for downstream reconciliation evidence.
    """
    from app.models import AaCourse

    wanted = {_stable_pair(item) for item in normalized}
    codes = sorted({code for code, _version in wanted})
    versions = sorted({version for _code, version in wanted})
    persisted = db.scalars(
        select(AaCourse).execution_options(populate_existing=True).where(
            AaCourse.tenant_id == _tid(),
            AaCourse.course_code.in_(codes),
            AaCourse.version.in_(versions),
            AaCourse.is_deleted.is_(False),
        ).order_by(AaCourse.course_code, AaCourse.version, AaCourse.id)
    ).all()
    persisted_by_key = {
        (str(course.course_code or "").strip().upper(), int(course.version or 0)): course
        for course in persisted
        if (str(course.course_code or "").strip().upper(), int(course.version or 0)) in wanted
    }
    missing = sorted(wanted - set(persisted_by_key))
    if missing:
        raise AppException(
            "DATA_CONFLICT",
            "课程导入事务内对账缺少稳定键记录，拒绝提交",
            details={"missingBusinessKeys": [f"{code}@v{version}" for code, version in missing]},
            http_status=409,
        )

    for _course, projection, item in created:
        actual = _projection_facts(persisted_by_key[_stable_pair(item)])
        expected = _expected_facts(projection)
        if actual != expected:
            raise AppException(
                "DATA_CONFLICT",
                "课程导入事务内对账失败，拒绝提交",
                details={"businessKey": item["businessKey"]},
                http_status=409,
            )

    normalized_by_business_key = {str(item["businessKey"]): item for item in normalized}
    reconciliation: list[dict] = []
    for raw in preview.get("items") or []:
        entry = dict(raw)
        source = normalized_by_business_key.get(str(entry.get("businessKey") or ""))
        if source is None:
            raise AppException(
                "DATA_CONFLICT",
                "课程导入对账结果无法回链源行，拒绝提交",
                details={"businessKey": str(entry.get("businessKey") or "")},
                http_status=409,
            )
        entry["courseId"] = str(persisted_by_key[_stable_pair(source)].id)
        reconciliation.append(entry)

    created_ids = [int(persisted_by_key[_stable_pair(item)].id) for _course, _projection, item in created]
    return reconciliation, created_ids


def confirm_course_catalog_import(rows: list[Mapping[str, object]], user: dict) -> dict:
    """Atomically confirm one already security-gated Course Catalog source snapshot."""
    source_rows = [dict(row) for row in (rows or [])]
    if not source_rows:
        raise AppException("VALIDATION_ERROR", "课程导入文件没有数据行，拒绝确认")
    try:
        normalized = _normalized_rows(source_rows)
    except (TypeError, ValueError) as exc:
        raise AppException(
            "VALIDATION_ERROR",
            "课程导入源数据格式非法，拒绝确认",
            details={"reason": str(exc)},
        ) from exc
    business_keys = sorted(str(item["businessKey"]) for item in normalized)

    with session() as db:
        try:
            locked_course_rows: list[object] = []
            preview = _course_catalog_dry_run_with_db(
                source_rows,
                user,
                db,
                lock_rows=True,
                locked_course_rows_out=locked_course_rows,
            )
            if int(preview.get("invalidRows") or 0) != 0:
                raise AppException(
                    "DATA_CONFLICT",
                    "课程导入数据在确认前重验失败，请重新预检",
                    details={
                        "conflictRows": int(preview.get("conflictRows") or 0),
                        "rejectRows": int(preview.get("rejectRows") or 0),
                        "errors": list(preview.get("errors") or []),
                    },
                    http_status=409,
                )

            action_by_row = _action_index(preview)
            expected_keys = {(int(item["rowNo"]), str(item["businessKey"])) for item in normalized}
            if set(action_by_row) != expected_keys:
                raise AppException(
                    "DATA_CONFLICT",
                    "课程导入预检结果与源文件行不一致，拒绝确认",
                    details={"sourceRows": len(expected_keys), "previewRows": len(action_by_row)},
                    http_status=409,
                )
            action_counts = Counter(str(item.get("action") or "") for item in action_by_row.values())
            unexpected = sorted(set(action_counts) - {RECONCILIATION_CREATE, RECONCILIATION_REUSE})
            if unexpected:
                raise AppException(
                    "DATA_CONFLICT",
                    "课程导入预检包含不可确认动作",
                    details={"actions": unexpected},
                    http_status=409,
                )

            predecessors = _index_predecessors(locked_course_rows, normalized, action_by_row)
            from app.models import AaCourse

            created: list[tuple[object, dict, dict]] = []
            for item in normalized:
                action = action_by_row[(int(item["rowNo"]), str(item["businessKey"]))]
                if action["action"] == RECONCILIATION_REUSE:
                    continue

                predecessor = None
                if int(item["version"]) > 1:
                    row = predecessors[(str(item["courseCode"]).strip().upper(), int(item["version"]) - 1)]
                    predecessor = _predecessor_snapshot(row)
                projection = course_import_write_projection(item, predecessor=predecessor)
                course = AaCourse(
                    tenant_id=_tid(),
                    course_code=projection["courseCode"],
                    credit=0,
                    version=projection["version"],
                    prev_version_id=projection["prevVersionId"],
                    status=projection["status"],
                )
                _apply_projection(course, projection)
                db.add(course)
                created.append((course, projection, item))

            db.flush()
            for course, projection, _item in created:
                action = "CREATE" if int(projection["version"]) == 1 else "NEW_VERSION"
                detail = (
                    f"IMPORT {projection['courseCode']}@v1"
                    if action == "CREATE"
                    else f"IMPORT v{int(projection['version']) - 1}->v{projection['version']}"
                )
                _course_core._audit(db, course.id, action, detail)

            reconciliation, created_ids = _reread_reconciliation(db, normalized, preview, created)
            db.commit()
            return {
                "confirmedRows": len(normalized),
                "createdCount": len(created_ids),
                "reusedCount": int(action_counts.get(RECONCILIATION_REUSE, 0)),
                "businessKeys": business_keys,
                "createdCourseIds": [str(value) for value in created_ids],
                "reconciliation": reconciliation,
            }
        except ValueError as exc:
            db.rollback()
            raise AppException(
                "DATA_CONFLICT",
                "课程导入确认前发现损坏或不可解释的课程数据，拒绝确认",
                details={"reason": str(exc)},
                http_status=409,
            ) from exc
        except IntegrityError as exc:
            db.rollback()
            if not _is_course_unique_conflict(exc):
                raise
            raise AppException(
                "DATA_CONFLICT",
                "课程导入发生并发版本冲突，请重新预检后确认",
                details={"businessKeys": business_keys},
                http_status=409,
            ) from exc
        except OperationalError as exc:
            db.rollback()
            if not _is_mysql_lock_conflict(exc):
                raise
            raise AppException(
                "DATA_CONFLICT",
                "课程导入遇到并发锁冲突，请重新预检后确认",
                details={"businessKeys": business_keys, "databaseErrorCode": _db_error_code(exc)},
                http_status=409,
            ) from exc
        except Exception:
            db.rollback()
            raise
