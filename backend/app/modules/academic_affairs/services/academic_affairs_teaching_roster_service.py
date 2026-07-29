"""教学任务官方名单唯一读写策略入口。

- 同一教学任务同一学期只认最新关联选课批次；
- 最新批次未锁定时 fail-closed，不回退旧批次或行政班；
- 锁定前 OPEN 课程空班或低于最低开班人数必须阻断；
- 锁定后因人工调整形成 0 人名单时，正式空名单仍是有效当前事实；
- 完全没有选课关系时才回退行政班/合班兼容名单；
- 锁定成功后显式投影独立教学班名单版本。
"""
from __future__ import annotations

from collections import defaultdict

from app.services.db_service import _tid

from . import academic_affairs_selection_roster_projection_service as selection_projection
from . import academic_affairs_teaching_roster_core_service as _core

_TASK_READY_STATUSES = _core._TASK_READY_STATUSES
_SELECTION_FINAL_STATUSES = _core._SELECTION_FINAL_STATUSES
_SELECTION_ACTIVE_RECORD_STATUSES = _core._SELECTION_ACTIVE_RECORD_STATUSES
_profile_dto = _core._profile_dto
_task_term_id = _core._task_term_id
_administrative_class_ids = _core._administrative_class_ids


def _status(value) -> str:
    return str(value or "").strip().upper()


def resolve_teaching_task_roster(db, teaching_task_id: int) -> dict:
    from app.models import (
        AaSelectionBatch, AaSelectionCourse, AaSelectionRecord,
        AaTeachingTask, StudentProfile,
    )

    task = db.get(AaTeachingTask, int(teaching_task_id))
    if not task or task.is_deleted or task.tenant_id != _tid():
        return {
            "ready": False, "source": "TASK_MISSING", "studentIds": [],
            "items": [], "batchIds": [], "note": "教学任务不存在",
        }
    task_term_id = _task_term_id(db, task)
    offered_courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.teaching_task_id == task.id,
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    if offered_courses:
        batch_ids = sorted({int(course.batch_id) for course in offered_courses})
        batches = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _tid(),
            AaSelectionBatch.id.in_(batch_ids),
            AaSelectionBatch.is_deleted.is_(False),
        ).all()
        same_term_batches = [
            batch for batch in batches
            if not task_term_id or int(batch.term_id or 0) == int(task_term_id)
        ]
        same_term_ids = {int(batch.id) for batch in same_term_batches}
        same_term_courses = [
            course for course in offered_courses if int(course.batch_id) in same_term_ids
        ]
        if same_term_courses:
            authoritative = max(same_term_batches, key=lambda row: int(row.id))
            batch_status = _status(authoritative.status)
            if batch_status not in _SELECTION_FINAL_STATUSES:
                return {
                    "ready": False, "source": "SELECTION_PENDING", "studentIds": [],
                    "items": [], "batchIds": [str(authoritative.id)],
                    "note": (
                        f"最新选课批次状态为 {batch_status or 'UNKNOWN'}，正式名单尚未锁定；"
                        "旧批次名单不再作为当前事实"
                    ),
                }
            final_course_ids = {
                int(course.id) for course in same_term_courses
                if int(course.batch_id) == int(authoritative.id)
                and _status(course.status) == "OPEN"
            }
            if not final_course_ids:
                return {
                    "ready": False, "source": "SELECTION_CANCELLED", "studentIds": [],
                    "items": [], "batchIds": [str(authoritative.id)],
                    "note": "最新正式批次中的该教学任务已取消或没有有效课程供给",
                }
            records = db.query(AaSelectionRecord).filter(
                AaSelectionRecord.tenant_id == _tid(),
                AaSelectionRecord.selection_course_id.in_(sorted(final_course_ids)),
                AaSelectionRecord.status == "LOCKED",
                AaSelectionRecord.is_deleted.is_(False),
            ).all()
            student_ids = sorted({int(record.student_id) for record in records})
            if not student_ids:
                return {
                    "ready": True, "source": "SELECTION_LOCKED", "studentIds": [],
                    "items": [], "batchIds": [str(authoritative.id)],
                    "note": "最新已锁定选课批次的当前正式名单为空",
                }
            profiles = db.query(StudentProfile).filter(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_(student_ids),
                StudentProfile.is_deleted.is_(False),
            ).all()
            by_id = {int(profile.id): profile for profile in profiles}
            missing = [student_id for student_id in student_ids if student_id not in by_id]
            if missing:
                return {
                    "ready": False, "source": "SELECTION_INVALID",
                    "studentIds": student_ids,
                    "items": [_profile_dto(by_id[value]) for value in student_ids if value in by_id],
                    "batchIds": [str(authoritative.id)],
                    "note": f"正式选课名单存在 {len(missing)} 个无有效学生主档的记录",
                }
            return {
                "ready": True, "source": "SELECTION_LOCKED",
                "studentIds": student_ids,
                "items": [_profile_dto(by_id[value]) for value in student_ids],
                "batchIds": [str(authoritative.id)],
                "note": "名单来自最新已锁定选课批次",
            }
    return _core.resolve_teaching_task_roster(db, int(task.id))


def validate_selection_lock(db, batch) -> dict:
    """锁定前叠加开班人数规则；正式锁定后空名单版本由调整流程表达。"""
    from app.models import AaSelectionCourse, AaSelectionRecord

    result = _core.validate_selection_lock(db, batch)
    issues = list(result.get("issues") or [])
    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.batch_id == int(batch.id),
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    records = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _tid(),
        AaSelectionRecord.batch_id == int(batch.id),
        AaSelectionRecord.is_deleted.is_(False),
    ).all()
    by_course = defaultdict(list)
    for record in records:
        by_course[int(record.selection_course_id)].append(record)
    for course in courses:
        if _status(course.status) != "OPEN":
            continue
        selected_count = sum(
            1 for record in by_course.get(int(course.id), [])
            if _status(record.status) == "SELECTED"
        )
        if selected_count <= 0:
            issues.append({
                "code": "EMPTY_OPEN_COURSE", "courseId": str(course.id),
                "message": "开放课程没有中选学生，不得锁定为空教学班；请先取消开课",
            })
        minimum = int(getattr(course, "min_capacity", 0) or 0)
        if minimum > 0 and selected_count < minimum:
            issues.append({
                "code": "BELOW_MIN_CAPACITY", "courseId": str(course.id),
                "message": f"中选人数 {selected_count} 低于最低开班人数 {minimum}，请先取消或补选",
            })
    result["issues"] = issues
    result["valid"] = not issues
    return result


def apply_locked_roster_projection(db, validation: dict) -> None:
    """锁定时同步预计人数并生成独立教学班名单版本。"""
    _core.apply_locked_roster_projection(db, validation)
    batch_id = validation.get("batchId")
    if batch_id:
        selection_projection.project_selection_batch_locked(db, int(batch_id))
