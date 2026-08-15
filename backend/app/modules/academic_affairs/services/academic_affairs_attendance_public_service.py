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

# 显式保留常用测试/兼容注入点；公开实现自身只读取这些本地引用。
session = _canonical.session
_tid = _canonical._tid
_audit = _canonical._audit
_role = _canonical._role
_teacher_keys = _canonical._teacher_keys
_primary_teacher_key = _canonical._primary_teacher_key
_row = _canonical._row
_ADMIN_ROLES = _canonical._ADMIN_ROLES
_ATTENDANCE_TASK_STATUSES = _canonical._ATTENDANCE_TASK_STATUSES
_ADMIN_SPECIAL = "ADMIN_SPECIAL"


def __getattr__(name):
    return getattr(_canonical, name)


def _special_evidence_text(value) -> str:
    """把特殊补录证据压成可审计文本；本轮不新增迁移，不伪造独立 evidence Authority。"""
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = str(value).strip()
    return text[:300]


def _admin_special_contract(role: str, body: dict, *, task_id) -> tuple[bool, str, str]:
    """隔离管理员特殊考勤旁路。

    - 普通教师永远不能请求 ADMIN_SPECIAL；
    - 管理员脱离 TeachingTask 时必须显式 ADMIN_SPECIAL；
    - ADMIN_SPECIAL 必须携带原因和证据；若有关联 Task，仍消费正式 Roster 快照。

    独立模型级 source_type/reason/evidence 列属于 INT migration 范围，本函数只先把现有旁路
    fail-closed，并通过 session_type + audit 留下可区分、可追溯事实。
    """
    requested_type = str(body.get("sessionType") or "").strip().upper()
    is_special = requested_type == _ADMIN_SPECIAL

    if is_special and role not in _ADMIN_ROLES:
        raise AppException(
            "NO_PERMISSION",
            "普通教师不能创建管理员特殊考勤场次",
            http_status=403,
        )
    if role in _ADMIN_ROLES and not task_id and not is_special:
        raise AppException(
            "VALIDATION_ERROR",
            "管理员脱离教学任务补录考勤必须显式选择 ADMIN_SPECIAL",
        )
    if not is_special:
        return False, "", ""

    reason = str(body.get("specialReason") or body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "管理员特殊考勤原因必填且不少于5字")
    evidence = _special_evidence_text(body.get("specialEvidence", body.get("evidence")))
    if not evidence:
        raise AppException("VALIDATION_ERROR", "管理员特殊考勤必须提供可审计 evidence")
    return True, reason[:300], evidence


def _with_source_type(result: dict) -> dict:
    result["sourceType"] = (
        _ADMIN_SPECIAL
        if str(result.get("sessionType") or "").strip().upper() == _ADMIN_SPECIAL
        else "FORMAL_TEACHING"
    )
    return result


def create_session(user, body) -> dict:
    """按当前学期教学任务创建场次，并在同一事务冻结正式名单版本。"""
    from app.models import AaAttendanceSession, AaTeachingTask, AaTeachingTaskBatch, AaTerm, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    body = body or {}
    role = _role(user)
    task_id = body.get("teachingTaskId")
    is_admin_special, special_reason, special_evidence = _admin_special_contract(
        role,
        body,
        task_id=task_id,
    )
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
        official = None
        roster_identity = None
        roster_source = _ADMIN_SPECIAL if is_admin_special else "ADMIN_MANUAL"
        if task_id:
            task = db.get(AaTeachingTask, int(task_id))
            if not task or task.is_deleted or task.tenant_id != _tid():
                raise not_found("教学任务不存在")
            if str(task.status or "").upper() not in _ATTENDANCE_TASK_STATUSES:
                raise AppException("DATA_CONFLICT", "教学任务须经教师确认并进入可执行状态后才能用于课堂考勤")
            batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                raise not_found("教学任务批次不存在")
            if int(batch.term_id or 0) != int(current_term.id):
                raise AppException("DATA_CONFLICT", "只能为当前学期教学任务创建考勤")
            if role not in _ADMIN_ROLES:
                keys = _teacher_keys(user)
                if not keys or not task.teacher_key or task.teacher_key not in keys:
                    raise AppException("NO_DATA_SCOPE", "该教学任务不属于当前教师", http_status=403)

            official = resolve_versioned_roster(db, int(task.id))
            roster_source = _ADMIN_SPECIAL if is_admin_special else official["source"]
            roster = [{
                "studentId": item["studentId"],
                "studentNo": item["studentNo"],
                "realName": item["realName"],
                "status": "PRESENT",
            } for item in official["items"]]
        elif role not in _ADMIN_ROLES:
            raise AppException("VALIDATION_ERROR", "请选择当前学期本人教学任务后再点名")
        else:
            roster = []

        class_id = int(task.class_id) if task and task.class_id else int(body.get("classId") or 0)
        if task and body.get("classId") and int(body.get("classId")) != class_id:
            raise AppException("VALIDATION_ERROR", "教学任务与行政班不一致")

        if task:
            if not class_id:
                class_ids = {
                    int(item["classId"]) for item in official["items"]
                    if str(item.get("classId") or "").isdigit()
                }
                class_id = next(iter(class_ids)) if len(class_ids) == 1 else 0
        else:
            if not class_id:
                raise AppException("VALIDATION_ERROR", "管理员特殊考勤必须选择明确行政班")
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
            session_type=(
                _ADMIN_SPECIAL
                if is_admin_special
                else ((str(body.get("sessionType")).strip() or None) if body.get("sessionType") else None)
            ),
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
        audit_detail = (
            f"task={task.id if task else '-'};source={roster_source};course={item.course_name or ''};"
            f"date={session_date};rosterVersion={roster_identity['rosterVersionId'] if roster_identity else '-'}"
        )
        if is_admin_special:
            audit_detail += f";reason={special_reason};evidence={special_evidence}"
        _audit(db, item.id, "CREATE", audit_detail)
        db.commit()
        db.refresh(item)
        result = _with_source_type(_row(item))
        result["teachingTaskId"] = str(task.id) if task else None
        result["rosterIdentity"] = roster_identity
        return result


def get_session(session_id, user) -> dict:
    result = _with_source_type(_canonical.get_session(session_id, user))
    with session() as db:
        result["rosterIdentity"] = get_consumer_snapshot(
            db,
            "ATTENDANCE_SESSION",
            int(session_id),
        )
    return result


def list_sessions(user, page=1, page_size=20, class_id=None, term_code=None, session_type=None):
    items, total = _canonical.list_sessions(user, page, page_size, class_id, term_code, session_type)
    return [_with_source_type(item) for item in items], total


attendance_stats = _canonical.attendance_stats
mark_attendance = _canonical.mark_attendance
submit_session = _canonical.submit_session