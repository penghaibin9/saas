"""R8 独立教学班与名单版本兼容迁移最终层。

补齐锁定选课名单调整后的版本事实：
- 选课锁定名单允许形成 0 人版本，明确表示“当前正式名单为空”，旧版本只保留历史；
- 人工退课后在原事务内按剩余 LOCKED 记录生成下一版，不能只改 expected_students；
- 同批其它课程继续幂等，不产生无意义重复版本。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_lock_service as _lock


def __getattr__(name):
    return getattr(_lock, name)


def create_roster_version(db, teaching_class, student_ids, *, source_type: str, source_id=None,
                          member_source_ids=None, reason=""):
    from app.models import (
        AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingTask,
    )

    ids, _profiles = _lock._base._member_profiles(db, student_ids)
    source = str(source_type or "").strip().upper()
    if not ids and source != "SELECTION_LOCK":
        raise AppException("DATA_CONFLICT", "非选课教学班的正式名单不能为空", http_status=409)

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
    digest = _lock._base._roster_hash(ids)
    if (
        current
        and current.roster_hash == digest
        and current.source_type == source
        and int(current.source_id or 0) == int(source_id or 0)
        and current.status == "LOCKED"
    ):
        return current, False

    next_version = int(locked_class.current_roster_version_no or 0) + 1
    if current:
        current.status = "SUPERSEDED"

    version = AaTeachingClassRosterVersion(
        tenant_id=_tid(), teaching_class_id=locked_class.id, version_no=next_version,
        source_type=source, source_id=int(source_id) if source_id else None,
        member_count=len(ids), roster_hash=digest, status="LOCKED",
        reason=(reason or "").strip() or None,
        locked_at=datetime.utcnow(), locked_by=_lock._base._operator(),
    )
    db.add(version)
    db.flush()
    source_map = {int(key): int(value) for key, value in (member_source_ids or {}).items()}
    for student_id in ids:
        db.add(AaTeachingClassMember(
            tenant_id=_tid(), teaching_class_id=locked_class.id,
            roster_version_id=version.id, student_id=student_id,
            source_type=source, source_id=source_map.get(student_id), status="ACTIVE",
        ))
    locked_class.current_roster_version_id = version.id
    locked_class.current_roster_version_no = next_version
    locked_class.roster_status = "LOCKED"
    if source == "SELECTION_LOCK":
        locked_class.class_type = "SELECTION"
    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == locked_class.teaching_task_id,
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if task:
        task.expected_students = len(ids)
    return version, True


def project_selection_course_locked(db, selection_course_id: int, *, reason="选课锁定名单同步") -> dict:
    """把一个选课课程的剩余 LOCKED 记录原子投影为当前教学班版本，0 人也生成明确版本。"""
    from app.models import AaSelectionCourse, AaSelectionRecord

    course = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.id == int(selection_course_id),
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.is_deleted.is_(False),
    ).first()
    if not course:
        raise not_found("选课课程不存在")
    if not course.teaching_task_id:
        raise AppException("DATA_CONFLICT", "选课课程未绑定教学任务，无法形成正式教学班名单", http_status=409)
    records = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _tid(),
        AaSelectionRecord.batch_id == int(course.batch_id),
        AaSelectionRecord.selection_course_id == int(course.id),
        AaSelectionRecord.status == "LOCKED",
        AaSelectionRecord.is_deleted.is_(False),
    ).all()
    student_ids = sorted({int(row.student_id) for row in records})
    source_ids = {int(row.student_id): int(row.id) for row in records}
    teaching_class = _lock.ensure_teaching_class_for_task(
        db, int(course.teaching_task_id), initialize_admin_roster=False,
    )
    if course.capacity is not None:
        teaching_class.capacity = int(course.capacity)
    version, created = create_roster_version(
        db, teaching_class, student_ids,
        source_type="SELECTION_LOCK", source_id=int(course.batch_id),
        member_source_ids=source_ids, reason=reason,
    )
    return {
        "selectionCourseId": str(course.id),
        "teachingTaskId": str(course.teaching_task_id),
        "teachingClassId": str(teaching_class.id),
        "rosterVersionId": str(version.id),
        "versionNo": int(version.version_no),
        "memberCount": int(version.member_count or 0),
        "created": bool(created),
    }


def project_selection_batch_locked(db, batch_id: int) -> dict:
    from app.models import AaSelectionCourse

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
        projected.append(project_selection_course_locked(
            db, int(course.id), reason=f"选课批次 {batch_id} 锁定正式名单",
        ))
    return {"batchId": str(batch_id), "projected": projected}


# 旧迁移模块保留原导入路径和增强实现，但不得覆盖正式 Service。
