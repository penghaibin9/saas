"""独立教学班、教师关系与名单版本公开 Service。

原始投影与兼容读取保存在 ``academic_affairs_teaching_class_core_service``。
本文件是唯一公开写入口：显式执行行锁、名单版本、选课权威对账和存量回填，
不修改其它模块函数，不依赖导入顺序，也不删除历史名单版本。
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_teaching_class_core_service as _core


def __getattr__(name):
    return getattr(_core, name)


def _safe_class_name(task) -> str:
    value = str(getattr(task, "teaching_class_name", None) or "").strip()
    if value:
        return value
    administrative_name = str(getattr(task, "class_name", None) or "").strip()
    course_name = str(getattr(task, "course_name", None) or "").strip()
    return " · ".join(part for part in (course_name, administrative_name) if part) or f"教学班{task.id}"


def _safe_task_snapshot(task, batch) -> str:
    return json.dumps({
        "teachingTaskId": str(task.id),
        "batchId": str(batch.id),
        "termId": str(batch.term_id),
        "courseId": str(task.course_id),
        "courseCode": task.course_code or "",
        "courseName": task.course_name or "",
        "administrativeClassId": str(task.class_id or ""),
        "administrativeClassName": str(getattr(task, "class_name", None) or ""),
        "merged": bool(task.is_merged),
        "mergedIntoId": str(task.merged_into_id or ""),
    }, ensure_ascii=False, sort_keys=True)


def create_roster_version(db, teaching_class, student_ids, *, source_type: str, source_id=None,
                          member_source_ids=None, reason=""):
    """为教学班创建不可变名单版本；同源同哈希幂等，其余版本只标记 SUPERSEDED。"""
    from app.models import (
        AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingTask,
    )

    ids, _profiles = _core._member_profiles(db, student_ids)
    if not ids:
        raise AppException("DATA_CONFLICT", "正式教学班名单不能为空", http_status=409)

    locked_class = db.query(AaTeachingClass).filter(
        AaTeachingClass.id == int(teaching_class.id),
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.is_deleted.is_(False),
    ).with_for_update().first()
    if not locked_class:
        raise not_found("教学班不存在")

    current = None
    if locked_class.current_roster_version_id:
        current = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.id == locked_class.current_roster_version_id,
            AaTeachingClassRosterVersion.tenant_id == _tid(),
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).with_for_update().first()

    digest = _core._roster_hash(ids)
    if (
        current
        and current.roster_hash == digest
        and current.source_type == source_type
        and int(current.source_id or 0) == int(source_id or 0)
        and current.status == "LOCKED"
    ):
        return current, False

    next_version = int(locked_class.current_roster_version_no or 0) + 1
    if current:
        current.status = "SUPERSEDED"

    version = AaTeachingClassRosterVersion(
        tenant_id=_tid(), teaching_class_id=locked_class.id,
        version_no=next_version, source_type=source_type,
        source_id=int(source_id) if source_id else None,
        member_count=len(ids), roster_hash=digest, status="LOCKED",
        reason=(reason or "").strip() or None,
        locked_at=datetime.utcnow(), locked_by=_core._operator(),
    )
    db.add(version)
    db.flush()

    source_map = {int(key): int(value) for key, value in (member_source_ids or {}).items()}
    for student_id in ids:
        db.add(AaTeachingClassMember(
            tenant_id=_tid(), teaching_class_id=locked_class.id,
            roster_version_id=version.id, student_id=student_id,
            source_type=source_type, source_id=source_map.get(student_id),
            status="ACTIVE",
        ))

    locked_class.current_roster_version_id = version.id
    locked_class.current_roster_version_no = next_version
    locked_class.roster_status = "LOCKED"
    if source_type == "SELECTION_LOCK":
        locked_class.class_type = "SELECTION"

    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == locked_class.teaching_task_id,
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if task:
        task.expected_students = len(ids)
    return version, True


def ensure_teaching_class_for_task(db, task_id: int, *, initialize_admin_roster=True):
    """将教学任务显式投影为独立教学班；已有选课关系时不再用行政班伪装正式名单。"""
    from app.models import AaSelectionCourse, AaTeachingClass

    task, batch = _core._task_and_batch(db, int(task_id))
    teaching_class = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id == task.id,
        AaTeachingClass.is_deleted.is_(False),
    ).first()
    code = _core._class_code(task, int(batch.term_id))
    conflict = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.term_id == int(batch.term_id),
        AaTeachingClass.class_code == code,
        AaTeachingClass.teaching_task_id != task.id,
        AaTeachingClass.is_deleted.is_(False),
    ).first()
    if conflict:
        raise AppException(
            "DATA_CONFLICT", f"教学班编号 {code} 已被其它教学任务占用",
            details={"conflictTeachingClassId": str(conflict.id)}, http_status=409,
        )

    if not teaching_class:
        teaching_class = AaTeachingClass(
            tenant_id=_tid(), teaching_task_id=task.id,
            term_id=int(batch.term_id), course_id=int(task.course_id),
            class_code=code, class_name=_safe_class_name(task),
            class_type=_core._class_type(task), source_type="TEACHING_TASK",
            source_id=task.id,
            capacity=int(task.expected_students) if task.expected_students else None,
            roster_status="DRAFT",
            status="ARCHIVED" if _core._status(task.status) == "MERGED" else "ACTIVE",
            source_snapshot_json=_safe_task_snapshot(task, batch),
        )
        db.add(teaching_class)
        db.flush()
    else:
        teaching_class.term_id = int(batch.term_id)
        teaching_class.course_id = int(task.course_id)
        teaching_class.class_code = code
        teaching_class.class_name = _safe_class_name(task)
        if teaching_class.class_type != "SELECTION":
            teaching_class.class_type = _core._class_type(task)
        if task.expected_students:
            teaching_class.capacity = int(task.expected_students)
        teaching_class.status = "ARCHIVED" if _core._status(task.status) == "MERGED" else "ACTIVE"
        teaching_class.source_snapshot_json = _safe_task_snapshot(task, batch)

    _core._sync_primary_teacher(db, teaching_class, task)

    if (
        initialize_admin_roster
        and not teaching_class.current_roster_version_id
        and teaching_class.status == "ACTIVE"
    ):
        selection_exists = db.query(AaSelectionCourse.id).filter(
            AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.teaching_task_id == int(task_id),
            AaSelectionCourse.is_deleted.is_(False),
        ).first() is not None
        if not selection_exists:
            student_ids = _core._administrative_roster(db, task)
            if student_ids:
                create_roster_version(
                    db, teaching_class, student_ids,
                    source_type="ADMIN_CLASS", source_id=task.class_id,
                    reason="由教学任务行政班或合班快照初始化",
                )
    return teaching_class


def sync_batch_teaching_classes(db, batch_id: int) -> dict:
    """批次投影必须全成全败；任一教学班或名单失败由调用方整体回滚。"""
    from app.models import AaTeachingTask

    task_ids = [
        int(value) for (value,) in db.query(AaTeachingTask.id).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id == int(batch_id),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
    ]
    projected, errors = [], []
    for task_id in task_ids:
        try:
            with db.begin_nested():
                row = ensure_teaching_class_for_task(db, task_id)
                db.flush()
            projected.append(str(row.id))
        except Exception as exc:
            errors.append({"teachingTaskId": str(task_id), "error": str(exc)})
    if errors:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务生成后教学班投影失败，已回滚整个批次",
            details={"batchId": str(batch_id), "errors": errors[:20]},
            http_status=409,
        )
    return {
        "taskCount": len(task_ids), "projectedCount": len(projected),
        "teachingClassIds": projected, "errors": [],
    }


def project_selection_batch_locked(db, batch_id: int) -> dict:
    from app.models import AaSelectionCourse, AaSelectionRecord

    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.batch_id == int(batch_id),
        AaSelectionCourse.status == "OPEN",
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    projected = []
    for course in courses:
        if not course.teaching_task_id:
            continue
        records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.batch_id == int(batch_id),
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.status == "LOCKED",
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        student_ids = sorted({int(row.student_id) for row in records})
        if not student_ids:
            continue
        source_ids = {int(row.student_id): int(row.id) for row in records}
        teaching_class = ensure_teaching_class_for_task(
            db, int(course.teaching_task_id), initialize_admin_roster=False,
        )
        if course.capacity is not None:
            teaching_class.capacity = int(course.capacity)
        version, created = create_roster_version(
            db, teaching_class, student_ids,
            source_type="SELECTION_LOCK", source_id=int(batch_id),
            member_source_ids=source_ids,
            reason=f"选课批次 {batch_id} 锁定正式名单",
        )
        projected.append({
            "teachingTaskId": str(course.teaching_task_id),
            "teachingClassId": str(teaching_class.id),
            "rosterVersionId": str(version.id),
            "versionNo": version.version_no,
            "memberCount": version.member_count,
            "capacity": teaching_class.capacity,
            "created": created,
        })
    return {"batchId": str(batch_id), "projected": projected}


def validate_selection_lock(db, batch) -> dict:
    result = _core._legacy_validate_selection_lock(db, batch)
    result["batchId"] = str(batch.id)
    return result


def apply_locked_roster_projection(db, validation: dict) -> None:
    _core._legacy_apply_locked_projection(db, validation)
    batch_id = validation.get("batchId")
    if batch_id:
        project_selection_batch_locked(db, int(batch_id))


def resolve_teaching_task_roster(db, teaching_task_id: int) -> dict:
    """读取当前名单；选课事实与教学班投影不一致时 fail-closed。"""
    from app.models import AaSelectionCourse, AaTeachingClass

    selection_exists = db.query(AaSelectionCourse.id).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.teaching_task_id == int(teaching_task_id),
        AaSelectionCourse.is_deleted.is_(False),
    ).first() is not None
    authoritative = _core._legacy_resolve_roster(db, int(teaching_task_id)) if selection_exists else None
    if authoritative is not None and not authoritative.get("ready"):
        return authoritative

    teaching_class = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id == int(teaching_task_id),
        AaTeachingClass.status == "ACTIVE",
        AaTeachingClass.is_deleted.is_(False),
    ).first()
    current = _core._new_roster_dto(db, teaching_class)
    if not current:
        return authoritative or _core._legacy_resolve_roster(db, int(teaching_task_id))

    if not selection_exists:
        return current
    if current.get("source") != "SELECTION_LOCK":
        return authoritative or {
            "ready": False, "source": "SELECTION_PENDING", "studentIds": [], "items": [],
            "batchIds": [], "note": "选课关系已建立，但教学班名单版本尚未切换到选课锁定结果",
        }

    current_batches = sorted(str(value) for value in (current.get("batchIds") or []))
    authoritative_batches = sorted(str(value) for value in (authoritative.get("batchIds") or []))
    current_students = sorted({int(value) for value in (current.get("studentIds") or [])})
    authoritative_students = sorted({int(value) for value in (authoritative.get("studentIds") or [])})
    if current_batches == authoritative_batches and current_students == authoritative_students:
        return current
    return {
        "ready": False,
        "source": "TEACHING_CLASS_PROJECTION_STALE",
        "studentIds": [], "items": [], "batchIds": authoritative_batches,
        "teachingClassId": current.get("teachingClassId"),
        "rosterVersionId": current.get("rosterVersionId"),
        "rosterVersionNo": current.get("rosterVersionNo"),
        "note": "教学班当前名单版本与最新已锁定选课批次不一致，请重新执行选课名单投影",
        "details": {
            "currentBatchIds": current_batches,
            "authoritativeBatchIds": authoritative_batches,
            "currentMemberCount": len(current_students),
            "authoritativeMemberCount": len(authoritative_students),
        },
    }


def backfill_term(user, term_id: int, *, dry_run=True, reason="") -> dict:
    """显式迁移存量教学班；正式写入必须给出审计原因。"""
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    reason = str(reason or "").strip()
    if not dry_run and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "正式回填原因必填且不少于5字")

    with session() as db:
        context = build_affairs_context(user, db)
        scope_type = str(getattr(context, "scope_type", None) or "NONE").upper()
        if scope_type in {"NONE", "BLOCKED"}:
            raise no_data_scope("当前身份未配置教学班迁移范围")
        class_ids = set(context.allowed_class_ids(db) or set()) if scope_type != "TENANT_ALL" else set()
        college_ids = {int(value) for value in (context.college_ids or set())}

        batches = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()
        if scope_type != "TENANT_ALL" and college_ids:
            batches = [row for row in batches if row.college_id and int(row.college_id) in college_ids]
        batch_ids = [int(row.id) for row in batches]
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id.in_(batch_ids or [0]),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
        if scope_type != "TENANT_ALL" and class_ids:
            tasks = [row for row in tasks if row.class_id and int(row.class_id) in class_ids]
        elif scope_type != "TENANT_ALL" and not college_ids:
            tasks = []

        report = []
        for task in tasks:
            legacy = _core._legacy_resolve_roster(db, int(task.id))
            report.append({
                "teachingTaskId": str(task.id),
                "courseName": task.course_name,
                "className": task.teaching_class_name or str(getattr(task, "class_name", None) or ""),
                "legacyReady": bool(legacy.get("ready")),
                "legacySource": legacy.get("source"),
                "legacyMemberCount": len(legacy.get("studentIds") or []),
            })
            if not dry_run:
                teaching_class = ensure_teaching_class_for_task(
                    db, int(task.id), initialize_admin_roster=False,
                )
                if legacy.get("ready") and legacy.get("studentIds"):
                    source_type_value = "SELECTION_LOCK" if legacy.get("source") == "SELECTION_LOCKED" else "ADMIN_CLASS"
                    source_id = int(legacy.get("batchIds", [0])[0]) if legacy.get("batchIds") else task.class_id
                    create_roster_version(
                        db, teaching_class, legacy["studentIds"],
                        source_type=source_type_value, source_id=source_id,
                        reason=reason,
                    )
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {
            "termId": str(term_id), "dryRun": bool(dry_run),
            "taskCount": len(tasks),
            "readyCount": sum(1 for row in report if row["legacyReady"]),
            "items": report,
        }
