"""V2-02 教学班名单版本并发安全最终层。"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_service as _base


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
        teaching_class = _base.ensure_teaching_class_for_task(
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
                row = _base.ensure_teaching_class_for_task(db, task_id)
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


# 基础服务中的ensure/backfill/apply函数运行时读取这些globals，直接替换即可覆盖所有消费者。
_base.create_roster_version = create_roster_version
_base.project_selection_batch_locked = project_selection_batch_locked
_base.sync_batch_teaching_classes = sync_batch_teaching_classes
