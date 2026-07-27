"""V2-02 独立教学班、教师关系与名单版本服务。

迁移规则：
- 教学任务仍是开课/任务流程来源，教学班按 teaching_task_id 一对一投影；
- 名单版本是正式成员事实，历史版本只 SUPERSEDED 不删除；
- 有选课关系但未锁定时继续 fail-closed，不回退行政班版本；
- 旧数据尚未投影时回退既有兼容解析器，支持逐学期迁移和对账。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_teaching_roster_service as _roster_base

_legacy_resolve_roster = _roster_base.resolve_teaching_task_roster
_legacy_validate_selection_lock = _roster_base.validate_selection_lock
_legacy_apply_locked_projection = _roster_base.apply_locked_roster_projection


def _operator() -> str:
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "system")


def _status(value) -> str:
    return str(value or "").strip().upper()


def _roster_hash(student_ids) -> str:
    normalized = ",".join(str(value) for value in sorted({int(value) for value in student_ids}))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _task_and_batch(db, task_id: int):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == int(task_id),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if not task:
        raise not_found("教学任务不存在")
    batch = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.id == task.batch_id,
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).first()
    if not batch or not batch.term_id:
        raise AppException("DATA_CONFLICT", "教学任务未关联正式学期批次", http_status=409)
    return task, batch


def _class_type(task) -> str:
    if bool(getattr(task, "is_merged", False)):
        return "MERGED"
    return "ADMIN"


def _class_code(task, term_id: int) -> str:
    value = str(getattr(task, "teaching_class_code", None) or "").strip()
    return value or f"TC-{term_id}-{task.id}"


def _class_name(task) -> str:
    value = str(getattr(task, "teaching_class_name", None) or "").strip()
    if value:
        return value
    class_name = str(getattr(task, "class_name", None) or "").strip()
    course_name = str(getattr(task, "course_name", None) or "").strip()
    return " · ".join(part for part in (course_name, class_name) if part) or f"教学班{task.id}"


def _task_snapshot(task, batch) -> str:
    return json.dumps({
        "teachingTaskId": str(task.id),
        "batchId": str(batch.id),
        "termId": str(batch.term_id),
        "courseId": str(task.course_id),
        "courseCode": task.course_code or "",
        "courseName": task.course_name or "",
        "administrativeClassId": str(task.class_id or ""),
        "administrativeClassName": task.class_name or "",
        "merged": bool(task.is_merged),
        "mergedIntoId": str(task.merged_into_id or ""),
    }, ensure_ascii=False, sort_keys=True)


def _sync_primary_teacher(db, teaching_class, task) -> None:
    from app.models import AaTeachingClassTeacher

    key = str(task.teacher_key or "").strip()
    existing = db.query(AaTeachingClassTeacher).filter(
        AaTeachingClassTeacher.tenant_id == _tid(),
        AaTeachingClassTeacher.teaching_class_id == teaching_class.id,
        AaTeachingClassTeacher.role_type == "PRIMARY",
        AaTeachingClassTeacher.is_deleted.is_(False),
    ).all()
    for row in existing:
        if key and row.teacher_key == key:
            row.teacher_id = task.teacher_id
            row.teacher_name = task.teacher_name
            row.start_week = task.start_week
            row.end_week = task.end_week
            row.status = "ACTIVE"
        else:
            row.status = "INACTIVE"
    if key and not any(row.teacher_key == key for row in existing):
        db.add(AaTeachingClassTeacher(
            tenant_id=_tid(), teaching_class_id=teaching_class.id,
            teacher_id=task.teacher_id, teacher_key=key, teacher_name=task.teacher_name,
            role_type="PRIMARY", start_week=task.start_week, end_week=task.end_week,
            status="ACTIVE",
        ))


def _member_profiles(db, student_ids):
    from app.models import StudentProfile

    ids = sorted({int(value) for value in student_ids})
    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id.in_(ids or [0]),
        StudentProfile.is_deleted.is_(False),
    ).all()
    by_id = {int(row.id): row for row in profiles}
    missing = [value for value in ids if value not in by_id]
    if missing:
        raise AppException(
            "DATA_CONFLICT",
            f"教学班名单存在 {len(missing)} 个无有效学生主档的成员",
            details={"missingStudentIds": [str(value) for value in missing[:50]]},
            http_status=409,
        )
    return ids, by_id


def create_roster_version(db, teaching_class, student_ids, *, source_type: str, source_id=None,
                          member_source_ids=None, reason=""):
    from app.models import AaTeachingClassMember, AaTeachingClassRosterVersion, AaTeachingTask

    ids, _profiles = _member_profiles(db, student_ids)
    if not ids:
        raise AppException("DATA_CONFLICT", "正式教学班名单不能为空", http_status=409)
    current = None
    if teaching_class.current_roster_version_id:
        current = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.id == teaching_class.current_roster_version_id,
            AaTeachingClassRosterVersion.tenant_id == _tid(),
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).first()
    digest = _roster_hash(ids)
    if current and current.roster_hash == digest and current.source_type == source_type and int(current.source_id or 0) == int(source_id or 0):
        return current, False

    locked_class = db.query(type(teaching_class)).filter(
        type(teaching_class).id == teaching_class.id,
        type(teaching_class).tenant_id == _tid(),
    ).with_for_update().first()
    if not locked_class:
        raise not_found("教学班不存在")
    next_version = int(locked_class.current_roster_version_no or 0) + 1
    if current:
        current.status = "SUPERSEDED"

    version = AaTeachingClassRosterVersion(
        tenant_id=_tid(), teaching_class_id=locked_class.id, version_no=next_version,
        source_type=source_type, source_id=int(source_id) if source_id else None,
        member_count=len(ids), roster_hash=digest, status="LOCKED",
        reason=(reason or "").strip() or None, locked_at=datetime.utcnow(), locked_by=_operator(),
    )
    db.add(version)
    db.flush()
    source_map = {int(key): int(value) for key, value in (member_source_ids or {}).items()}
    for student_id in ids:
        db.add(AaTeachingClassMember(
            tenant_id=_tid(), teaching_class_id=locked_class.id,
            roster_version_id=version.id, student_id=student_id,
            source_type=source_type, source_id=source_map.get(student_id), status="ACTIVE",
        ))
    locked_class.current_roster_version_id = version.id
    locked_class.current_roster_version_no = next_version
    locked_class.roster_status = "LOCKED"
    if source_type == "SELECTION_LOCK":
        locked_class.class_type = "SELECTION"
    task = db.get(AaTeachingTask, int(locked_class.teaching_task_id))
    if task and not task.is_deleted and task.tenant_id == _tid():
        task.expected_students = len(ids)
    return version, True


def _administrative_roster(db, task):
    from app.models import StudentProfile

    class_ids = _roster_base._administrative_class_ids(db, task)
    if not class_ids:
        return []
    return [
        int(value) for (value,) in db.query(StudentProfile.id).filter(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.class_id.in_(sorted(class_ids)),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.student_no, StudentProfile.id).all()
    ]


def ensure_teaching_class_for_task(db, task_id: int, *, initialize_admin_roster=True):
    from app.models import AaTeachingClass

    task, batch = _task_and_batch(db, task_id)
    teaching_class = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id == task.id,
        AaTeachingClass.is_deleted.is_(False),
    ).first()
    code = _class_code(task, int(batch.term_id))
    conflict = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.term_id == int(batch.term_id),
        AaTeachingClass.class_code == code,
        AaTeachingClass.teaching_task_id != task.id,
        AaTeachingClass.is_deleted.is_(False),
    ).first()
    if conflict:
        raise AppException(
            "DATA_CONFLICT",
            f"教学班编号 {code} 已被其它教学任务占用",
            details={"conflictTeachingClassId": str(conflict.id)},
            http_status=409,
        )
    if not teaching_class:
        teaching_class = AaTeachingClass(
            tenant_id=_tid(), teaching_task_id=task.id, term_id=int(batch.term_id),
            course_id=int(task.course_id), class_code=code, class_name=_class_name(task),
            class_type=_class_type(task), source_type="TEACHING_TASK", source_id=task.id,
            capacity=int(task.expected_students) if task.expected_students else None,
            roster_status="DRAFT", status="ARCHIVED" if _status(task.status) == "MERGED" else "ACTIVE",
            source_snapshot_json=_task_snapshot(task, batch),
        )
        db.add(teaching_class)
        db.flush()
    else:
        teaching_class.term_id = int(batch.term_id)
        teaching_class.course_id = int(task.course_id)
        teaching_class.class_code = code
        teaching_class.class_name = _class_name(task)
        teaching_class.class_type = _class_type(task) if teaching_class.class_type != "SELECTION" else teaching_class.class_type
        teaching_class.capacity = int(task.expected_students) if task.expected_students else teaching_class.capacity
        teaching_class.status = "ARCHIVED" if _status(task.status) == "MERGED" else "ACTIVE"
        teaching_class.source_snapshot_json = _task_snapshot(task, batch)
    _sync_primary_teacher(db, teaching_class, task)

    if initialize_admin_roster and not teaching_class.current_roster_version_id and teaching_class.status == "ACTIVE":
        student_ids = _administrative_roster(db, task)
        if student_ids:
            create_roster_version(
                db, teaching_class, student_ids,
                source_type="ADMIN_CLASS", source_id=task.class_id,
                reason="由教学任务行政班/合班快照初始化",
            )
    return teaching_class


def sync_batch_teaching_classes(db, batch_id: int) -> dict:
    from app.models import AaTeachingTask

    task_ids = [
        int(value) for (value,) in db.query(AaTeachingTask.id).filter(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == int(batch_id),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
    ]
    created_or_updated = []
    errors = []
    for task_id in task_ids:
        try:
            row = ensure_teaching_class_for_task(db, task_id)
            created_or_updated.append(str(row.id))
        except Exception as exc:
            errors.append({"teachingTaskId": str(task_id), "error": str(exc)})
    return {
        "taskCount": len(task_ids),
        "projectedCount": len(created_or_updated),
        "teachingClassIds": created_or_updated,
        "errors": errors,
    }


def project_selection_batch_locked(db, batch_id: int) -> dict:
    from app.models import AaSelectionCourse, AaSelectionRecord

    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(), AaSelectionCourse.batch_id == int(batch_id),
        AaSelectionCourse.status == "OPEN", AaSelectionCourse.is_deleted.is_(False),
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
        teaching_class = ensure_teaching_class_for_task(db, int(course.teaching_task_id), initialize_admin_roster=False)
        version, created = create_roster_version(
            db, teaching_class, student_ids,
            source_type="SELECTION_LOCK", source_id=int(batch_id), member_source_ids=source_ids,
            reason=f"选课批次 {batch_id} 锁定正式名单",
        )
        projected.append({
            "teachingTaskId": str(course.teaching_task_id),
            "teachingClassId": str(teaching_class.id),
            "rosterVersionId": str(version.id),
            "versionNo": version.version_no,
            "memberCount": version.member_count,
            "created": created,
        })
    return {"batchId": str(batch_id), "projected": projected}


def validate_selection_lock(db, batch) -> dict:
    result = _legacy_validate_selection_lock(db, batch)
    result["batchId"] = str(batch.id)
    return result


def apply_locked_roster_projection(db, validation: dict) -> None:
    _legacy_apply_locked_projection(db, validation)
    batch_id = validation.get("batchId")
    if batch_id:
        project_selection_batch_locked(db, int(batch_id))


def _new_roster_dto(db, teaching_class):
    from app.models import AaTeachingClassMember, AaTeachingClassRosterVersion, StudentProfile

    if not teaching_class or not teaching_class.current_roster_version_id or teaching_class.roster_status != "LOCKED":
        return None
    version = db.query(AaTeachingClassRosterVersion).filter(
        AaTeachingClassRosterVersion.id == teaching_class.current_roster_version_id,
        AaTeachingClassRosterVersion.tenant_id == _tid(),
        AaTeachingClassRosterVersion.status == "LOCKED",
        AaTeachingClassRosterVersion.is_deleted.is_(False),
    ).first()
    if not version:
        return None
    member_ids = [
        int(value) for (value,) in db.query(AaTeachingClassMember.student_id).filter(
            AaTeachingClassMember.tenant_id == _tid(),
            AaTeachingClassMember.roster_version_id == version.id,
            AaTeachingClassMember.status == "ACTIVE",
            AaTeachingClassMember.is_deleted.is_(False),
        ).all()
    ]
    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(member_ids or [0]),
        StudentProfile.is_deleted.is_(False),
    ).all()
    by_id = {int(row.id): row for row in profiles}
    if len(by_id) != len(set(member_ids)):
        return {
            "ready": False, "source": "TEACHING_CLASS_INVALID",
            "studentIds": sorted(set(member_ids)),
            "items": [_roster_base._profile_dto(by_id[value]) for value in sorted(by_id)],
            "batchIds": [str(version.source_id)] if version.source_type == "SELECTION_LOCK" and version.source_id else [],
            "teachingClassId": str(teaching_class.id), "rosterVersionId": str(version.id),
            "rosterVersionNo": version.version_no,
            "note": "教学班当前名单版本存在无有效学生主档的成员",
        }
    ids = sorted(set(member_ids))
    return {
        "ready": bool(ids),
        "source": version.source_type,
        "studentIds": ids,
        "items": [_roster_base._profile_dto(by_id[value]) for value in ids],
        "batchIds": [str(version.source_id)] if version.source_type == "SELECTION_LOCK" and version.source_id else [],
        "teachingClassId": str(teaching_class.id),
        "rosterVersionId": str(version.id),
        "rosterVersionNo": version.version_no,
        "rosterHash": version.roster_hash,
        "note": f"名单来自教学班第 {version.version_no} 版（{version.source_type}）",
    }


def resolve_teaching_task_roster(db, teaching_task_id: int) -> dict:
    from app.models import AaSelectionCourse, AaTeachingClass

    selection_exists = db.query(AaSelectionCourse.id).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.teaching_task_id == int(teaching_task_id),
        AaSelectionCourse.is_deleted.is_(False),
    ).first() is not None
    legacy = None
    if selection_exists:
        legacy = _legacy_resolve_roster(db, int(teaching_task_id))
        if not legacy.get("ready"):
            return legacy
    teaching_class = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id == int(teaching_task_id),
        AaTeachingClass.status == "ACTIVE",
        AaTeachingClass.is_deleted.is_(False),
    ).first()
    current = _new_roster_dto(db, teaching_class)
    if current:
        if selection_exists and current["source"] != "SELECTION_LOCK":
            return legacy or {
                "ready": False, "source": "SELECTION_PENDING", "studentIds": [], "items": [],
                "batchIds": [], "note": "选课关系已建立，但教学班名单版本尚未切换到选课锁定结果",
            }
        return current
    return legacy or _legacy_resolve_roster(db, int(teaching_task_id))


def backfill_term(user, term_id: int, *, dry_run=True) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    from .academic_affairs_task_security_facade import _scope

    with session() as db:
        scope = _scope(user, db)
        batch_ids = [
            int(value) for (value,) in db.query(AaTeachingTaskBatch.id).filter(
                AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == int(term_id),
                AaTeachingTaskBatch.is_deleted.is_(False),
            ).all()
        ]
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id.in_(batch_ids or [0]),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
        if not scope.all:
            if scope.class_ids:
                tasks = [row for row in tasks if row.class_id and int(row.class_id) in scope.class_ids]
            elif scope.college_ids:
                allowed_batches = {
                    int(value) for (value,) in db.query(AaTeachingTaskBatch.id).filter(
                        AaTeachingTaskBatch.tenant_id == _tid(),
                        AaTeachingTaskBatch.id.in_(batch_ids or [0]),
                        AaTeachingTaskBatch.college_id.in_(list(scope.college_ids)),
                        AaTeachingTaskBatch.is_deleted.is_(False),
                    ).all()
                }
                tasks = [row for row in tasks if int(row.batch_id) in allowed_batches]
            else:
                tasks = []
        report = []
        for task in tasks:
            legacy = _legacy_resolve_roster(db, int(task.id))
            report.append({
                "teachingTaskId": str(task.id), "courseName": task.course_name,
                "className": task.teaching_class_name or task.class_name,
                "legacyReady": bool(legacy.get("ready")), "legacySource": legacy.get("source"),
                "legacyMemberCount": len(legacy.get("studentIds") or []),
            })
            if not dry_run:
                teaching_class = ensure_teaching_class_for_task(db, int(task.id), initialize_admin_roster=False)
                if legacy.get("ready") and legacy.get("studentIds"):
                    source_type = "SELECTION_LOCK" if legacy.get("source") == "SELECTION_LOCKED" else "ADMIN_CLASS"
                    source_id = int(legacy.get("batchIds", [0])[0]) if legacy.get("batchIds") else task.class_id
                    create_roster_version(
                        db, teaching_class, legacy["studentIds"], source_type=source_type,
                        source_id=source_id, reason="V2-02存量教学班名单回填",
                    )
        if not dry_run:
            db.commit()
        else:
            db.rollback()
        return {
            "termId": str(term_id), "dryRun": bool(dry_run),
            "taskCount": len(tasks), "readyCount": sum(1 for row in report if row["legacyReady"]),
            "items": report,
        }


# 所有既有消费者继续从原名单模块导入，但运行时统一切到V2读写策略。
_roster_base.resolve_teaching_task_roster = resolve_teaching_task_roster
_roster_base.validate_selection_lock = validate_selection_lock
_roster_base.apply_locked_roster_projection = apply_locked_roster_projection
