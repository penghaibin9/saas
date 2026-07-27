"""课堂考勤统一公开 Service。

在正式考勤事务内冻结教学班名单版本，并在读取时返回名单身份快照；
其余列表、点名、提交和统计能力显式委托正式考勤 Service。
本模块不替换其它模块函数，也不依赖兼容层导入顺序。
"""
from __future__ import annotations

import importlib
import json

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    get_consumer_snapshot,
    resolve_versioned_roster,
)

_canonical = importlib.import_module(
    ".academic_affairs_attendance_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_canonical, name)


def create_session(user, body) -> dict:
    """按当前学期教学任务创建场次，并在同一事务冻结正式名单版本。"""
    from app.models import AaAttendanceSession, AaTeachingTask, AaTeachingTaskBatch, AaTerm, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    body = body or {}
    role = _canonical._role(user)
    task_id = body.get("teachingTaskId")
    session_date = str(body.get("sessionDate") or "").strip()
    if not session_date:
        raise AppException("VALIDATION_ERROR", "考勤日期必填")
    slot_no = body.get("slotNo")

    with _canonical.session() as db:
        current_term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _canonical._tid(),
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )).first()
        if not current_term:
            raise AppException("DATA_CONFLICT", "当前学校尚未设置当前学期")
        guard_term_writable(db, current_term.id)

        task = None
        official = None
        roster_identity = None
        roster_source = "ADMIN_MANUAL"
        if task_id:
            task = db.get(AaTeachingTask, int(task_id))
            if not task or task.is_deleted or task.tenant_id != _canonical._tid():
                raise not_found("教学任务不存在")
            if str(task.status or "").upper() not in _canonical._ATTENDANCE_TASK_STATUSES:
                raise AppException("DATA_CONFLICT", "教学任务须经教师确认并进入可执行状态后才能用于课堂考勤")
            batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != _canonical._tid():
                raise not_found("教学任务批次不存在")
            if int(batch.term_id or 0) != int(current_term.id):
                raise AppException("DATA_CONFLICT", "只能为当前学期教学任务创建考勤")
            if role not in _canonical._ADMIN_ROLES:
                keys = _canonical._teacher_keys(user)
                if not keys or not task.teacher_key or task.teacher_key not in keys:
                    raise AppException("NO_DATA_SCOPE", "该教学任务不属于当前教师", http_status=403)
        elif role not in _canonical._ADMIN_ROLES:
            raise AppException("VALIDATION_ERROR", "请选择当前学期本人教学任务后再点名")

        class_id = int(task.class_id) if task and task.class_id else int(body.get("classId") or 0)
        if task and body.get("classId") and int(body.get("classId")) != class_id:
            raise AppException("VALIDATION_ERROR", "教学任务与行政班不一致")

        if task:
            official = resolve_versioned_roster(db, int(task.id))
            roster_source = official["source"]
            roster = [{
                "studentId": item["studentId"],
                "studentNo": item["studentNo"],
                "realName": item["realName"],
                "status": "PRESENT",
            } for item in official["items"]]
            if not class_id:
                class_ids = {
                    int(item["classId"]) for item in official["items"]
                    if str(item.get("classId") or "").isdigit()
                }
                class_id = next(iter(class_ids)) if len(class_ids) == 1 else 0
        else:
            if not class_id:
                raise AppException("VALIDATION_ERROR", "请选择行政班或教学任务")
            students = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _canonical._tid(),
                StudentProfile.class_id == class_id,
                StudentProfile.is_deleted.is_(False),
            )).all()
            roster = [{
                "studentId": str(student.id),
                "studentNo": student.student_no,
                "realName": student.real_name,
                "status": "PRESENT",
            } for student in students]

        if not roster:
            raise not_found("该教学任务暂无可用学生名单")
        teacher_key = (
            task.teacher_key if task else
            str(body.get("teacherKey") or "").strip() or _canonical._primary_teacher_key(user)
        )
        if not teacher_key:
            raise AppException("VALIDATION_ERROR", "无法确定考勤场次教师工号")

        item = AaAttendanceSession(
            tenant_id=_canonical._tid(),
            class_id=class_id,
            course_name=(task.course_name if task else str(body.get("courseName") or "").strip() or None),
            term_code=f"{current_term.year_code}-{current_term.term_no}",
            teacher_key=teacher_key,
            session_date=session_date,
            slot_no=int(slot_no) if slot_no else None,
            session_type=(str(body.get("sessionType")).strip() or None) if body.get("sessionType") else None,
            roster_json=json.dumps(roster, ensure_ascii=False),
            total_count=len(roster),
            present_count=len(roster),
            absent_count=0,
            status="DRAFT",
        )
        db.add(item)
        db.flush()
        if task:
            roster_identity = freeze_consumer_snapshot(
                db,
                "ATTENDANCE_SESSION",
                int(item.id),
                int(task.id),
                roster=official,
            )
        _canonical._audit(
            db,
            item.id,
            "CREATE",
            (
                f"task={task.id if task else '-'};source={roster_source};course={item.course_name or ''};"
                f"date={session_date};rosterVersion={roster_identity['rosterVersionId'] if roster_identity else '-'}"
            ),
        )
        db.commit()
        db.refresh(item)
        result = _canonical._row(item)
        result["teachingTaskId"] = str(task.id) if task else None
        result["rosterIdentity"] = roster_identity
        return result


def get_session(session_id, user) -> dict:
    result = _canonical.get_session(session_id, user)
    with _canonical.session() as db:
        result["rosterIdentity"] = get_consumer_snapshot(
            db,
            "ATTENDANCE_SESSION",
            int(session_id),
        )
    return result


list_sessions = _canonical.list_sessions
attendance_stats = _canonical.attendance_stats
mark_attendance = _canonical.mark_attendance
submit_session = _canonical.submit_session
