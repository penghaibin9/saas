"""V2-02 教学班名单版本并发与权威一致性最终层。"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_service as _base

_original_ensure_teaching_class = _base.ensure_teaching_class_for_task
_original_resolve_roster = _base.resolve_teaching_task_roster


def __getattr__(name):
    return getattr(_base, name)


def create_roster_version(db, teaching_class, student_ids, *, source_type: str, source_id=None,
                           member_source_ids=None, reason=""):
    from app.models import (
        AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingTask,
    )

    ids, _profiles = _base._member_profiles(db, student_ids)
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
    digest = _base._roster_hash(ids)
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
        tenant_id=_tid(), teaching_class_id=locked_class.id, version_no=next_version,
        source_type=source_type, source_id=int(source_id) if source_id else None,
        member_count=len(ids), roster_hash=digest, status="LOCKED",
        reason=(reason or "").strip() or None,
        locked_at=datetime.utcnow(), locked_by=_base._operator(),
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
    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == locked_class.teaching_task_id,
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if task:
        task.expected_students = len(ids)
    return version, True


def ensure_teaching_class_for_task(db, task_id: int, *, initialize_admin_roster=True):
    """选课关系一旦建立，行政班名单只作历史来源，不再自动伪装成当前锁定版本。"""
    from app.models import AaSelectionCourse

    teaching_class = _original_ensure_teaching_class(
        db, int(task_id), initialize_admin_roster=False,
    )
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
            task, _batch = _base._task_and_batch(db, int(task_id))
            student_ids = _base._administrative_roster(db, task)
            if student_ids:
                create_roster_version(
                    db, teaching_class, student_ids,
                    source_type="ADMIN_CLASS", source_id=task.class_id,
                    reason="由教学任务行政班/合班快照初始化",
                )
    return teaching_class


def resolve_teaching_task_roster(db, teaching_task_id: int) -> dict:
    """选课正式事实必须与当前教学班版本的批次和成员完全一致。"""
    result = _original_resolve_roster(db, int(teaching_task_id))
    if not result.get("ready") or result.get("source") != "SELECTION_LOCK":
        return result

    authoritative = _base._legacy_resolve_roster(db, int(teaching_task_id))
    if not authoritative.get("ready"):
        return authoritative
    if authoritative.get("source") != "SELECTION_LOCKED":
        return result

    current_batches = sorted(str(value) for value in (result.get("batchIds") or []))
    authoritative_batches = sorted(str(value) for value in (authoritative.get("batchIds") or []))
    current_students = sorted({int(value) for value in (result.get("studentIds") or [])})
    authoritative_students = sorted({int(value) for value in (authoritative.get("studentIds") or [])})
    if current_batches == authoritative_batches and current_students == authoritative_students:
        return result

    return {
        "ready": False,
        "source": "TEACHING_CLASS_PROJECTION_STALE",
        "studentIds": [],
        "items": [],
        "batchIds": authoritative_batches,
        "teachingClassId": result.get("teachingClassId"),
        "rosterVersionId": result.get("rosterVersionId"),
        "rosterVersionNo": result.get("rosterVersionNo"),
        "note": "教学班当前名单版本与最新已锁定选课批次不一致，请重新执行选课名单投影后再开展考勤、考务或成绩业务",
        "details": {
            "currentBatchIds": current_batches,
            "authoritativeBatchIds": authoritative_batches,
            "currentMemberCount": len(current_students),
            "authoritativeMemberCount": len(authoritative_students),
        },
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


def sync_batch_teaching_classes(db, batch_id: int) -> dict:
    """使用保存点隔离单条投影失败，成功记录可正常提交。"""
    from app.models import AaTeachingTask

    task_ids = [
        int(value) for (value,) in db.query(AaTeachingTask.id).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id == int(batch_id),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
    ]
    projected = []
    errors = []
    for task_id in task_ids:
        try:
            with db.begin_nested():
                row = ensure_teaching_class_for_task(db, task_id)
                db.flush()
            projected.append(str(row.id))
        except Exception as exc:
            errors.append({"teachingTaskId": str(task_id), "error": str(exc)})
    return {
        "taskCount": len(task_ids),
        "projectedCount": len(projected),
        "teachingClassIds": projected,
        "errors": errors,
    }


# 基础服务和原名单模块同时替换，保证后续消费者及完整路径导入命中同一最终策略。
_base.create_roster_version = create_roster_version
_base.ensure_teaching_class_for_task = ensure_teaching_class_for_task
_base.resolve_teaching_task_roster = resolve_teaching_task_roster
_base.project_selection_batch_locked = project_selection_batch_locked
_base.sync_batch_teaching_classes = sync_batch_teaching_classes
_base._roster_base.resolve_teaching_task_roster = resolve_teaching_task_roster
