"""选课锁定名单到独立教学班版本的专用投影 Service。

通用教学班名单仍禁止空名单；只有已锁定选课结果允许生成 0 人正式版本，明确表示
当前正式名单为空，防止系统回退到旧行政班名单。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_service as teaching_class_service


def _create_empty_selection_version(db, teaching_class, *, batch_id: int, reason=""):
    from app.models import AaTeachingClass, AaTeachingClassRosterVersion, AaTeachingTask

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
    digest = teaching_class_service._roster_hash([])
    if (
        current and current.status == "LOCKED"
        and current.source_type == "SELECTION_LOCK"
        and int(current.source_id or 0) == int(batch_id)
        and current.roster_hash == digest
        and int(current.member_count or 0) == 0
    ):
        return current, False
    next_version = int(locked_class.current_roster_version_no or 0) + 1
    if current:
        current.status = "SUPERSEDED"
    version = AaTeachingClassRosterVersion(
        tenant_id=_tid(), teaching_class_id=locked_class.id,
        version_no=next_version, source_type="SELECTION_LOCK",
        source_id=int(batch_id), member_count=0, roster_hash=digest,
        status="LOCKED", reason=str(reason or "").strip() or None,
        locked_at=datetime.utcnow(), locked_by=teaching_class_service._operator(),
    )
    db.add(version)
    db.flush()
    locked_class.current_roster_version_id = version.id
    locked_class.current_roster_version_no = next_version
    locked_class.roster_status = "LOCKED"
    locked_class.class_type = "SELECTION"
    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == locked_class.teaching_task_id,
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if task:
        task.expected_students = 0
    return version, True


def project_selection_course_locked(db, selection_course_id: int, *, reason="选课锁定名单同步") -> dict:
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
    teaching_class = teaching_class_service.ensure_teaching_class_for_task(
        db, int(course.teaching_task_id), initialize_admin_roster=False,
    )
    if course.capacity is not None:
        teaching_class.capacity = int(course.capacity)
    if student_ids:
        version, created = teaching_class_service.create_roster_version(
            db, teaching_class, student_ids,
            source_type="SELECTION_LOCK", source_id=int(course.batch_id),
            member_source_ids=source_ids, reason=reason,
        )
    else:
        version, created = _create_empty_selection_version(
            db, teaching_class, batch_id=int(course.batch_id), reason=reason,
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
        if course.teaching_task_id:
            projected.append(project_selection_course_locked(
                db, int(course.id), reason=f"选课批次 {batch_id} 锁定正式名单",
            ))
    return {"batchId": str(batch_id), "projected": projected}
