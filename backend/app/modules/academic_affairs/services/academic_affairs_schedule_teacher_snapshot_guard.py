"""C15-18 compatibility guard for ScheduleItem teacher snapshots.

Published ``AaScheduleItem.teacher_key`` is a historical schedule snapshot. Once
``AaTeachingClassTeacher`` becomes the formal execution authority, a legitimate
PRIMARY replacement or week-split/co-teaching change must not require rewriting a
published schedule item merely to keep attendance/Teacher Today consumable.

The occurrence contract remains strict on:
- schedule item teacher snapshot must still be present for audit/evidence;
- administrative class identity must still match the TeachingTask when both exist;
- course identity must still match when both exist;
- ScopeHead, PUBLISHED/EFFECTIVE, change linkage and calendar truth remain owned and
  validated by the mature occurrence consumer.

Only equality between the historical item teacher snapshot and the mutable
TeachingTask compatibility snapshot is removed. Current teacher permission is
separately enforced by TeachingClassTeacher relation guards.
"""
from __future__ import annotations

from . import academic_affairs_attendance_occurrence_consumer as occurrence


def _validate_task_item_identity(task, item) -> tuple[str, int]:
    item_teacher = str(getattr(item, "teacher_key", "") or "").strip()
    if not item_teacher:
        occurrence._conflict("正式课表缺少教师历史快照，不能消费正式课次")
    task_class = int(getattr(task, "class_id", 0) or 0)
    item_class = int(getattr(item, "class_id", 0) or 0)
    if task_class and item_class and task_class != item_class:
        occurrence._conflict("正式课表班级身份与教学任务不一致")
    task_course = int(getattr(task, "course_id", 0) or 0)
    item_course = int(getattr(item, "course_id", 0) or 0)
    if task_course and item_course and task_course != item_course:
        occurrence._conflict("正式课表课程身份与教学任务不一致")
    return item_teacher, item_class


_validate_task_item_identity._schedule_teacher_snapshot_compat = True


def install() -> None:
    current = getattr(occurrence, "_validate_task_item_identity", None)
    if getattr(current, "_schedule_teacher_snapshot_compat", False):
        return
    if not hasattr(occurrence, "_teacher_snapshot_original_identity_validator"):
        occurrence._teacher_snapshot_original_identity_validator = current
    occurrence._validate_task_item_identity = _validate_task_item_identity
