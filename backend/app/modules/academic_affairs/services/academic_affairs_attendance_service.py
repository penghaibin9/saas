"""课堂考勤正式 Service。

普通教师创建场次必须绑定当前学期本人已确认教学任务，名单统一使用教学任务正式名单；
管理员可在明确行政班上代建。教师归属只认稳定工号族标识，姓名仅用于展示。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

from .academic_affairs_teaching_roster_service import resolve_teaching_task_roster

_STATUS_OK = ("PRESENT", "LATE", "ABSENT", "LEAVE")
_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}
_ATTENDANCE_TASK_STATUSES = {"TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY"}


def _op():
    user = get_current_user_ctx() or {}
    return (user.get("realName") or "系统"), str(user.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail

    name, uid = _op()
    db.add(AffairsAuditTrail(
        tenant_id=_tid(),
        biz_type="AA_ATTENDANCE",
        biz_id=int(biz_id) if biz_id else None,
        action=action,
        operator=name or uid,
        detail=(detail or "")[:990],
        occurred_at=datetime.utcnow(),
    ))


def _role(user) -> str:
    return str((user or {}).get("currentRoleCode") or "").upper()


def _teacher_keys(user) -> set[str]:
    """工号族标识；不包含 realName，避免同名教师互相命中。"""
    return set(_derive_keys(user or {}))


def _primary_teacher_key(user) -> str | None:
    """稳定、确定性的当前教师键，仅供管理员代建时兜底。"""
    user = user or {}
    login = str(user.get("loginName") or "").strip()
    if login:
        return login
    context_id = str(user.get("activeContextId") or "").strip()
    if context_id.startswith("ctx_") and len(context_id) > 4:
        return context_id[4:]
    uid = str(user.get("userId") or "").strip()
    if uid.startswith("u_") and len(uid) > 2:
        return uid[2:]
    return uid or None


def _check_owner(attendance_session, user):
    if _role(user) in _ADMIN_ROLES:
        return
    if not attendance_session.teacher_key:
        raise AppException(
            "NO_DATA_SCOPE",
            "该历史考勤场次缺少稳定教师工号，归属待教务处修复",
            http_status=403,
        )
    keys = _teacher_keys(user)
    if not keys or attendance_session.teacher_key not in keys:
        raise AppException("NO_DATA_SCOPE", "该考勤场次不在您的授课范围内", http_status=403)


def _row(item) -> dict:
    return {
        "sessionId": str(item.id),
        "classId": str(item.class_id or ""),
        "courseName": item.course_name or "",
        "termCode": item.term_code or "",
        "sessionDate": item.session_date,
        "slotNo": item.slot_no,
        "sessionType": item.session_type or "常规",
        "totalCount": item.total_count,
        "presentCount": item.present_count,
        "absentCount": item.absent_count,
        "status": item.status,
        "createdAt": _iso(item.created_at),
    }


def create_session(user, body) -> dict:
    """按当前学期真实教学任务创建考勤；普通教师不得按任意行政班绕过授课关系。"""
    from app.models import (
        AaAttendanceSession,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        StudentProfile,
    )
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    body = body or {}
    role = _role(user)
    task_id = body.get("teachingTaskId")
    session_date = str(body.get("sessionDate") or "").strip()
    if not session_date:
        raise AppException("VALIDATION_ERROR", "考勤日期必填")
    slot_no = body.get("slotNo")

    with session() as db:
        current_term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(),
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )).first()
        if not current_term:
            raise AppException("DATA_CONFLICT", "当前学校尚未设置当前学期")
        guard_term_writable(db, current_term.id)

        task = None
        roster_source = "ADMIN_MANUAL"
        if task_id:
            task = db.get(AaTeachingTask, int(task_id))
            if not task or task.is_deleted or task.tenant_id != _tid():
                raise not_found("教学任务不存在")
            if str(task.status or "").upper() not in _ATTENDANCE_TASK_STATUSES:
                raise AppException(
                    "DATA_CONFLICT",
                    "教学任务须经教师确认并进入可执行状态后才能用于课堂考勤",
                )
            batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                raise not_found("教学任务批次不存在")
            if int(batch.term_id or 0) != int(current_term.id):
                raise AppException("DATA_CONFLICT", "只能为当前学期教学任务创建考勤")
            if role not in _ADMIN_ROLES:
                keys = _teacher_keys(user)
                if not keys or not task.teacher_key or task.teacher_key not in keys:
                    raise AppException("NO_DATA_SCOPE", "该教学任务不属于当前教师", http_status=403)
        elif role not in _ADMIN_ROLES:
            raise AppException("VALIDATION_ERROR", "请选择当前学期本人教学任务后再点名")

        class_id = int(task.class_id) if task and task.class_id else int(body.get("classId") or 0)
        if task and body.get("classId") and int(body.get("classId")) != class_id:
            raise AppException("VALIDATION_ERROR", "教学任务与行政班不一致")

        if task:
            official = resolve_teaching_task_roster(db, task.id)
            if not official["ready"]:
                raise AppException(
                    "DATA_CONFLICT",
                    f"教学任务名单尚不可用：{official['note']}",
                    details=official,
                    http_status=409,
                )
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
                StudentProfile.tenant_id == _tid(),
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
            str(body.get("teacherKey") or "").strip() or _primary_teacher_key(user)
        )
        if not teacher_key:
            raise AppException("VALIDATION_ERROR", "无法确定考勤场次教师工号")

        item = AaAttendanceSession(
            tenant_id=_tid(),
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
        _audit(
            db,
            item.id,
            "CREATE",
            f"task={task.id if task else '-'};source={roster_source};course={item.course_name or ''};date={session_date}",
        )
        db.commit()
        db.refresh(item)
        return _row(item)


def list_sessions(user, page=1, page_size=20, class_id=None, term_code=None, session_type=None):
    """教师仅查看本人稳定工号场次；教务处/学校管理员查看全部。"""
    from app.models import AaAttendanceSession

    role = _role(user)
    with session() as db:
        conds = [
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.is_deleted.is_(False),
        ]
        if role not in _ADMIN_ROLES:
            keys = _teacher_keys(user)
            if not keys:
                return [], 0
            conds.append(AaAttendanceSession.teacher_key.in_(sorted(keys)))
        if class_id:
            conds.append(AaAttendanceSession.class_id == int(class_id))
        if term_code:
            conds.append(AaAttendanceSession.term_code == term_code)
        if session_type:
            conds.append(AaAttendanceSession.session_type == session_type)
        rows = db.scalars(select(AaAttendanceSession).where(*conds)
                          .order_by(AaAttendanceSession.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        return [_row(item) for item in rows[start:start + page_size]], total


def attendance_stats(user, class_id=None, term_code=None, session_type=None):
    """仅统计已提交场次；数据范围与场次列表一致。"""
    from app.models import AaAttendanceSession

    role = _role(user)
    with session() as db:
        conds = [
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.is_deleted.is_(False),
            AaAttendanceSession.status == "SUBMITTED",
        ]
        if role not in _ADMIN_ROLES:
            keys = _teacher_keys(user)
            if not keys:
                return {"sessionCount": 0, "students": []}
            conds.append(AaAttendanceSession.teacher_key.in_(sorted(keys)))
        if class_id:
            conds.append(AaAttendanceSession.class_id == int(class_id))
        if term_code:
            conds.append(AaAttendanceSession.term_code == term_code)
        if session_type:
            conds.append(AaAttendanceSession.session_type == session_type)

        rows = db.scalars(select(AaAttendanceSession).where(*conds)).all()
        aggregate: dict[str, dict] = {}
        for attendance_session in rows:
            for roster_item in (json.loads(attendance_session.roster_json) if attendance_session.roster_json else []):
                student_id = roster_item.get("studentId")
                if not student_id:
                    continue
                row = aggregate.setdefault(student_id, {
                    "studentId": student_id,
                    "studentNo": roster_item.get("studentNo") or "",
                    "realName": roster_item.get("realName") or "",
                    "present": 0,
                    "late": 0,
                    "absent": 0,
                    "leave": 0,
                    "sessions": 0,
                })
                status = str(roster_item.get("status") or "PRESENT").upper()
                key = {
                    "PRESENT": "present",
                    "LATE": "late",
                    "ABSENT": "absent",
                    "LEAVE": "leave",
                }.get(status)
                if key:
                    row[key] += 1
                    row["sessions"] += 1

        students = []
        for row in aggregate.values():
            row["absentRate"] = round(row["absent"] / row["sessions"], 3) if row["sessions"] else 0.0
            students.append(row)
        students.sort(key=lambda row: (-row["absent"], -row["late"], row["studentNo"]))
        return {"sessionCount": len(rows), "students": students}


def get_session(session_id, user) -> dict:
    from app.models import AaAttendanceSession

    with session() as db:
        item = db.get(AaAttendanceSession, int(session_id))
        if not item or item.is_deleted or item.tenant_id != _tid():
            raise not_found("考勤场次不存在")
        _check_owner(item, user)
        items = json.loads(item.roster_json) if item.roster_json else []
        return {**_row(item), "items": items}


def mark_attendance(session_id, user, body) -> dict:
    """标记单生考勤状态，仅 DRAFT 可改。"""
    from app.models import AaAttendanceSession

    with session() as db:
        item = db.get(AaAttendanceSession, int(session_id))
        if not item or item.is_deleted or item.tenant_id != _tid():
            raise not_found("考勤场次不存在")
        _check_owner(item, user)
        if item.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "已提交的考勤不可再修改")

        body = body or {}
        student_id = str(body.get("studentId") or "")
        status = str(body.get("status") or "").upper()
        if status not in _STATUS_OK:
            raise AppException("VALIDATION_ERROR", "考勤状态非法")

        roster = json.loads(item.roster_json) if item.roster_json else []
        found = False
        for roster_item in roster:
            if str(roster_item.get("studentId") or "") == student_id:
                roster_item["status"] = status
                found = True
                break
        if not found:
            raise not_found("该生不在本场次名单内")

        item.roster_json = json.dumps(roster, ensure_ascii=False)
        item.present_count = sum(1 for row in roster if row.get("status") == "PRESENT")
        item.absent_count = sum(1 for row in roster if row.get("status") == "ABSENT")
        db.flush()
        db.commit()
        db.refresh(item)
        return {**_row(item), "items": roster}


def submit_session(session_id, user) -> dict:
    from app.models import AaAttendanceSession

    with session() as db:
        item = db.get(AaAttendanceSession, int(session_id))
        if not item or item.is_deleted or item.tenant_id != _tid():
            raise not_found("考勤场次不存在")
        _check_owner(item, user)
        if item.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "该场次已提交")
        item.status = "SUBMITTED"
        _audit(db, item.id, "SUBMIT", f"present={item.present_count}/{item.total_count}")
        db.commit()
        db.refresh(item)
        row = _row(item)

    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_attendance_warnings
        scan_attendance_warnings(user)
    except Exception:
        logging.getLogger(__name__).exception("attendance submit → scan_attendance_warnings failed")
    return row
