"""教学任务官方名单兼容读模型。

当前代码尚未建设V2的独立教学班/名单版本表，因此本模块只统一现有事实源，不提前伪造新主表：

- 存在当前学期选课供给关系时，只有 LOCKED/ARCHIVED 选课批次中的 LOCKED 记录是正式名单；
- 选课关系存在但名单尚未锁定时 fail-closed，禁止考勤/成绩/考务悄悄退回行政班名单；
- 没有选课关系的必修行政班课程，使用教学任务行政班；合班任务按合班快照中的成员班级并集；
- 所有消费者得到同一 ``source/ready/studentIds/items`` 契约。

V2阶段02落独立教学班与名单版本后，本模块应迁移为新表的唯一读入口。
"""
from __future__ import annotations

import json
from collections import defaultdict

from app.services.db_service import _tid

_TASK_READY_STATUSES = {"READY", "APPROVED"}
_SELECTION_FINAL_STATUSES = {"LOCKED", "ARCHIVED"}
_SELECTION_ACTIVE_RECORD_STATUSES = {"SELECTED", "LOCKED", "PENDING_LOTTERY"}


def _status(value) -> str:
    return str(value or "").strip().upper()


def _profile_dto(profile) -> dict:
    return {
        "studentId": str(profile.id),
        "studentNo": profile.student_no or "",
        "realName": profile.real_name or "",
        "classId": str(profile.class_id or ""),
    }


def _task_term_id(db, task):
    from app.models import AaTeachingTaskBatch

    if not task or not getattr(task, "batch_id", None):
        return None
    batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
    if not batch or batch.is_deleted or batch.tenant_id != _tid():
        return None
    return int(batch.term_id) if batch.term_id else None


def _administrative_class_ids(db, task) -> set[int]:
    """行政班课程名单；合班 survivor 包含成员任务的班级并集。"""
    from app.models import AaTeachingTask

    class_ids = set()
    if getattr(task, "class_id", None):
        class_ids.add(int(task.class_id))
    if not bool(getattr(task, "is_merged", False)):
        return class_ids
    try:
        snapshot = json.loads(getattr(task, "merge_snapshot_json", None) or "{}")
    except (TypeError, ValueError):
        snapshot = {}
    member_ids = [int(value) for value in snapshot.get("memberTaskIds", []) if str(value).isdigit()]
    if not member_ids:
        return class_ids
    members = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.id.in_(member_ids),
        AaTeachingTask.is_deleted.is_(False),
    ).all()
    for member in members:
        if member.class_id:
            class_ids.add(int(member.class_id))
    return class_ids


def resolve_teaching_task_roster(db, teaching_task_id: int) -> dict:
    """返回教学任务当前正式名单；选课名单未锁定时绝不回退行政班。"""
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
        same_term_batch_ids = {int(batch.id) for batch in same_term_batches}
        same_term_courses = [
            course for course in offered_courses if int(course.batch_id) in same_term_batch_ids
        ]
        if same_term_courses:
            final_batches = [
                batch for batch in same_term_batches
                if _status(batch.status) in _SELECTION_FINAL_STATUSES
            ]
            if not final_batches:
                return {
                    "ready": False,
                    "source": "SELECTION_PENDING",
                    "studentIds": [],
                    "items": [],
                    "batchIds": [str(batch.id) for batch in same_term_batches],
                    "note": "该教学任务已进入选课流程，但正式名单尚未锁定",
                }
            final_batch_ids = {int(batch.id) for batch in final_batches}
            final_course_ids = {
                int(course.id) for course in same_term_courses
                if int(course.batch_id) in final_batch_ids and _status(course.status) == "OPEN"
            }
            if not final_course_ids:
                return {
                    "ready": False,
                    "source": "SELECTION_CANCELLED",
                    "studentIds": [],
                    "items": [],
                    "batchIds": [str(batch.id) for batch in final_batches],
                    "note": "该教学任务对应选课课程已取消或没有有效供给",
                }
            records = db.query(AaSelectionRecord).filter(
                AaSelectionRecord.tenant_id == _tid(),
                AaSelectionRecord.selection_course_id.in_(list(final_course_ids)),
                AaSelectionRecord.status == "LOCKED",
                AaSelectionRecord.is_deleted.is_(False),
            ).all()
            student_ids = sorted({int(record.student_id) for record in records})
            profiles = db.query(StudentProfile).filter(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_(student_ids or [0]),
                StudentProfile.is_deleted.is_(False),
            ).all()
            by_id = {int(profile.id): profile for profile in profiles}
            missing = [student_id for student_id in student_ids if student_id not in by_id]
            if missing:
                return {
                    "ready": False,
                    "source": "SELECTION_INVALID",
                    "studentIds": student_ids,
                    "items": [_profile_dto(by_id[sid]) for sid in student_ids if sid in by_id],
                    "batchIds": [str(batch.id) for batch in final_batches],
                    "note": f"正式选课名单存在 {len(missing)} 个无有效学生主档的记录",
                }
            items = [_profile_dto(by_id[student_id]) for student_id in student_ids]
            return {
                "ready": True,
                "source": "SELECTION_LOCKED",
                "studentIds": student_ids,
                "items": items,
                "batchIds": [str(batch.id) for batch in final_batches],
                "note": "名单来自已锁定选课结果",
            }

    class_ids = _administrative_class_ids(db, task)
    if not class_ids:
        return {
            "ready": False,
            "source": "ADMIN_CLASS_MISSING",
            "studentIds": [],
            "items": [],
            "batchIds": [],
            "note": "教学任务未关联行政班或正式选课名单",
        }
    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.class_id.in_(sorted(class_ids)),
        StudentProfile.is_deleted.is_(False),
    ).all()
    profiles.sort(key=lambda profile: (profile.student_no or "", int(profile.id)))
    student_ids = [int(profile.id) for profile in profiles]
    return {
        "ready": bool(profiles),
        "source": "ADMIN_CLASS_MERGED" if len(class_ids) > 1 else "ADMIN_CLASS",
        "studentIds": student_ids,
        "items": [_profile_dto(profile) for profile in profiles],
        "batchIds": [],
        "note": "名单来自合并行政班" if len(class_ids) > 1 else "名单来自行政班",
    }


def validate_selection_lock(db, batch) -> dict:
    """选课CLOSED→LOCKED前验证教学任务、人数与学生主档一致性。"""
    from app.models import (
        AaSelectionCourse,
        AaSelectionRecord,
        AaTeachingTask,
        AaTeachingTaskBatch,
        StudentProfile,
    )

    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.batch_id == int(batch.id),
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    course_by_id = {int(course.id): course for course in courses}
    records = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _tid(),
        AaSelectionRecord.batch_id == int(batch.id),
        AaSelectionRecord.is_deleted.is_(False),
    ).all()
    issues = []
    if not courses:
        issues.append({"code": "NO_COURSE", "message": "批次没有课程供给"})

    pending_lottery = [record for record in records if _status(record.status) == "PENDING_LOTTERY"]
    if pending_lottery:
        issues.append({
            "code": "LOTTERY_PENDING",
            "message": f"仍有 {len(pending_lottery)} 条抽签志愿未摇号",
        })

    records_by_course = defaultdict(list)
    for record in records:
        records_by_course[int(record.selection_course_id)].append(record)
        if int(record.selection_course_id) not in course_by_id and _status(record.status) in _SELECTION_ACTIVE_RECORD_STATUSES:
            issues.append({
                "code": "ORPHAN_RECORD",
                "recordId": str(record.id),
                "message": "存在找不到课程供给的有效选课记录",
            })

    task_student_pairs = defaultdict(list)
    selected_student_ids = set()
    task_counts = defaultdict(set)
    for course in courses:
        course_status = _status(course.status)
        course_records = records_by_course.get(int(course.id), [])
        selected = [record for record in course_records if _status(record.status) == "SELECTED"]
        locked = [record for record in course_records if _status(record.status) == "LOCKED"]
        if locked:
            issues.append({
                "code": "PRELOCKED_RECORD",
                "courseId": str(course.id),
                "message": f"批次尚未锁定但课程已有 {len(locked)} 条LOCKED记录",
            })
        if course_status == "COURSE_CANCELLED":
            active = [record for record in course_records if _status(record.status) in {"SELECTED", "LOCKED", "PENDING_LOTTERY"}]
            if active:
                issues.append({
                    "code": "CANCELLED_COURSE_HAS_ROSTER",
                    "courseId": str(course.id),
                    "message": f"已取消课程仍有 {len(active)} 条有效名单记录",
                })
            continue
        if course_status != "OPEN":
            issues.append({
                "code": "UNKNOWN_COURSE_STATUS",
                "courseId": str(course.id),
                "message": f"课程供给状态 {course.status} 不可锁定",
            })
            continue
        if int(course.selected_count or 0) != len(selected):
            issues.append({
                "code": "COUNT_MISMATCH",
                "courseId": str(course.id),
                "message": f"课程已选人数计数 {int(course.selected_count or 0)} 与有效记录 {len(selected)} 不一致",
            })
        if not course.teaching_task_id:
            issues.append({
                "code": "TASK_REQUIRED",
                "courseId": str(course.id),
                "message": "课程未关联教学任务，无法形成正式教学班名单",
            })
            continue
        task = db.get(AaTeachingTask, int(course.teaching_task_id))
        if not task or task.is_deleted or task.tenant_id != _tid():
            issues.append({
                "code": "TASK_MISSING",
                "courseId": str(course.id),
                "message": "关联教学任务不存在",
            })
            continue
        task_batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
        if not task_batch or task_batch.is_deleted or task_batch.tenant_id != _tid():
            issues.append({
                "code": "TASK_BATCH_MISSING",
                "courseId": str(course.id),
                "message": "教学任务批次不存在",
            })
            continue
        if int(task_batch.term_id or 0) != int(batch.term_id or 0):
            issues.append({
                "code": "TERM_MISMATCH",
                "courseId": str(course.id),
                "message": "选课批次与教学任务不属于同一学期",
            })
        if _status(task_batch.status) not in {"APPROVED", "ARCHIVED"} or _status(task.status) not in _TASK_READY_STATUSES:
            issues.append({
                "code": "TASK_NOT_READY",
                "courseId": str(course.id),
                "message": f"教学任务尚未终审就绪（批次={task_batch.status}，任务={task.status}）",
            })
        for record in selected:
            selected_student_ids.add(int(record.student_id))
            task_student_pairs[(int(task.id), int(record.student_id))].append(record)
            task_counts[int(task.id)].add(int(record.student_id))

    duplicate_pairs = [pair for pair, pair_records in task_student_pairs.items() if len(pair_records) > 1]
    for task_id, student_id in duplicate_pairs:
        issues.append({
            "code": "DUPLICATE_TASK_STUDENT",
            "taskId": str(task_id),
            "studentId": str(student_id),
            "message": "同一学生在同一教学任务下出现重复选课记录",
        })

    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id.in_(sorted(selected_student_ids) or [0]),
        StudentProfile.is_deleted.is_(False),
    ).all()
    valid_student_ids = {int(profile.id) for profile in profiles}
    missing_students = sorted(selected_student_ids - valid_student_ids)
    for student_id in missing_students:
        issues.append({
            "code": "STUDENT_MISSING",
            "studentId": str(student_id),
            "message": "选课记录对应学生主档不存在或已作废",
        })

    return {
        "valid": not issues,
        "issues": issues,
        "courseCount": len(courses),
        "selectedRecordCount": sum(
            1 for record in records if _status(record.status) == "SELECTED"
        ),
        "taskStudentCounts": {str(task_id): len(student_ids) for task_id, student_ids in task_counts.items()},
    }


def apply_locked_roster_projection(db, validation: dict) -> None:
    """锁定时只回写教学任务预计人数；正式成员关系仍以LOCKED选课记录为事实源。"""
    from app.models import AaTeachingTask

    for task_id, count in (validation.get("taskStudentCounts") or {}).items():
        task = db.get(AaTeachingTask, int(task_id))
        if task and not task.is_deleted and task.tenant_id == _tid():
            task.expected_students = int(count)
