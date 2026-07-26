"""教学任务官方名单最终策略层。

修正兼容读模型的两个边界：
- 同一教学任务同一学期存在多个选课批次时，只认最新关联批次；最新批次未锁定时不得回退旧名单；
- OPEN课程零人或低于最低开班人数时不得锁定为“正式教学班”，应先取消开课或完成补选。

V2阶段02落独立教学班/名单版本后，以显式version和effective_at替代“最新批次ID”兼容规则。
"""
from __future__ import annotations

from collections import defaultdict

from app.services.db_service import _tid

from . import academic_affairs_teaching_roster_service as _base


def _status(value) -> str:
    return str(value or "").strip().upper()


def resolve_teaching_task_roster(db, teaching_task_id: int) -> dict:
    from app.models import (
        AaSelectionBatch,
        AaSelectionCourse,
        AaSelectionRecord,
        AaTeachingTask,
        StudentProfile,
    )

    task = db.get(AaTeachingTask, int(teaching_task_id))
    if not task or task.is_deleted or task.tenant_id != _tid():
        return {
            "ready": False,
            "source": "TASK_MISSING",
            "studentIds": [],
            "items": [],
            "batchIds": [],
            "note": "教学任务不存在",
        }
    task_term_id = _base._task_term_id(db, task)
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
        same_term_batch_ids = {int(batch.id) for batch in same_term_batches}
        same_term_courses = [
            course for course in offered_courses if int(course.batch_id) in same_term_batch_ids
        ]
        if same_term_courses:
            authoritative = max(same_term_batches, key=lambda batch: int(batch.id))
            authoritative_status = _status(authoritative.status)
            if authoritative_status not in _base._SELECTION_FINAL_STATUSES:
                return {
                    "ready": False,
                    "source": "SELECTION_PENDING",
                    "studentIds": [],
                    "items": [],
                    "batchIds": [str(authoritative.id)],
                    "note": (
                        f"最新选课批次状态为 {authoritative_status or 'UNKNOWN'}，"
                        "正式名单尚未锁定；旧批次名单不再作为当前事实"
                    ),
                }
            final_course_ids = {
                int(course.id) for course in same_term_courses
                if int(course.batch_id) == int(authoritative.id) and _status(course.status) == "OPEN"
            }
            if not final_course_ids:
                return {
                    "ready": False,
                    "source": "SELECTION_CANCELLED",
                    "studentIds": [],
                    "items": [],
                    "batchIds": [str(authoritative.id)],
                    "note": "最新正式批次中的该教学任务已取消或没有有效课程供给",
                }
            records = db.query(AaSelectionRecord).filter(
                AaSelectionRecord.tenant_id == _tid(),
                AaSelectionRecord.selection_course_id.in_(list(final_course_ids)),
                AaSelectionRecord.status == "LOCKED",
                AaSelectionRecord.is_deleted.is_(False),
            ).all()
            student_ids = sorted({int(record.student_id) for record in records})
            if not student_ids:
                return {
                    "ready": False,
                    "source": "SELECTION_EMPTY",
                    "studentIds": [],
                    "items": [],
                    "batchIds": [str(authoritative.id)],
                    "note": "最新选课批次虽已锁定，但该教学任务正式名单为空",
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
                    "ready": False,
                    "source": "SELECTION_INVALID",
                    "studentIds": student_ids,
                    "items": [_base._profile_dto(by_id[sid]) for sid in student_ids if sid in by_id],
                    "batchIds": [str(authoritative.id)],
                    "note": f"正式选课名单存在 {len(missing)} 个无有效学生主档的记录",
                }
            return {
                "ready": True,
                "source": "SELECTION_LOCKED",
                "studentIds": student_ids,
                "items": [_base._profile_dto(by_id[student_id]) for student_id in student_ids],
                "batchIds": [str(authoritative.id)],
                "note": "名单来自最新已锁定选课批次",
            }

    # 完全没有当前学期选课关系时，复用行政班/合班兼容逻辑。
    return _base._resolve_teaching_task_roster_legacy(db, int(task.id))


def validate_selection_lock(db, batch) -> dict:
    from app.models import AaSelectionCourse, AaSelectionRecord

    result = _base._validate_selection_lock_legacy(db, batch)
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
                "code": "EMPTY_OPEN_COURSE",
                "courseId": str(course.id),
                "message": "开放课程没有中选学生，不得生成空教学班；请先取消开课",
            })
        minimum = int(getattr(course, "min_capacity", 0) or 0)
        if minimum > 0 and selected_count < minimum:
            issues.append({
                "code": "BELOW_MIN_CAPACITY",
                "courseId": str(course.id),
                "message": f"中选人数 {selected_count} 低于最低开班人数 {minimum}，请先取消或补选",
            })
    result["issues"] = issues
    result["valid"] = not issues
    return result


# 保存原实现供本策略层复用行政班部分，避免递归。
if not hasattr(_base, "_resolve_teaching_task_roster_legacy"):
    _base._resolve_teaching_task_roster_legacy = _base.resolve_teaching_task_roster
if not hasattr(_base, "_validate_selection_lock_legacy"):
    _base._validate_selection_lock_legacy = _base.validate_selection_lock
_base.resolve_teaching_task_roster = resolve_teaching_task_roster
_base.validate_selection_lock = validate_selection_lock

apply_locked_roster_projection = _base.apply_locked_roster_projection
