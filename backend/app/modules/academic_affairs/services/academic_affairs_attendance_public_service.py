"""课堂考勤统一公开 Service。

在正式考勤事务内冻结教学班名单版本，并在读取时返回名单身份快照；
其余列表、点名、提交和统计能力显式委托正式考勤 Service。
本模块不替换其它模块函数，也不依赖兼容层导入顺序。
"""
from __future__ import annotations

import importlib
import json

from sqlalchemy import or_, select

from app.core.exceptions import AppException, not_found

from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    get_consumer_snapshot,
    resolve_versioned_roster,
)
from .academic_affairs_attendance_occurrence_consumer import resolve_formal_occurrence

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
attendance_task_executable = _canonical.attendance_task_executable
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
    is_special = str(result.get("sessionType") or "").strip().upper() == _ADMIN_SPECIAL
    result["sourceType"] = _ADMIN_SPECIAL if is_special else "FORMAL_TEACHING"
    result["sourceLabel"] = "管理员特殊补录" if is_special else "正式课堂"
    result["sessionTypeLabel"] = (
        "管理员特殊补录" if is_special else str(result.get("sessionType") or "常规")
    )
    return result


def _stats_session_type_condition(model, session_type=None):
    """默认课堂统计排除 ADMIN_SPECIAL；只有显式筛选时才进入特殊补录统计。"""
    requested = str(session_type or "").strip()
    if requested:
        return model.session_type == requested
    return or_(
        model.session_type.is_(None),
        model.session_type != _ADMIN_SPECIAL,
    )


def _guard_no_duplicate_formal_session(
    db,
    model,
    *,
    class_id: int,
    teacher_key: str,
    session_date: str,
    slot_no: int,
    occurrence: dict,
):
    """Application-level duplicate guard while INT still owns the DB occurrence identity.

    ``resolve_formal_occurrence(..., lock=True)`` already holds the current schedule authority
    locks. This locking read is deliberately performed after that authority check so MySQL
    REPEATABLE READ observes a concurrent winner that committed while this request waited.
    ADMIN_SPECIAL remains a separate audit source and never blocks a formal classroom fact.
    """
    existing = db.query(model).filter(
        model.tenant_id == _tid(),
        model.class_id == int(class_id or 0),
        model.teacher_key == str(teacher_key or ""),
        model.session_date == str(session_date),
        model.slot_no == int(slot_no),
        model.is_deleted.is_(False),
        _stats_session_type_condition(model),
    ).with_for_update().first()
    if existing:
        raise AppException(
            "DATA_CONFLICT",
            "该正式课次已创建课堂考勤场次，请勿重复点名",
            details={
                "existingSessionId": str(existing.id),
                "teachingTaskId": str(occurrence.get("teachingTaskId") or ""),
                "scheduleItemId": str(occurrence.get("scheduleItemId") or ""),
                "sessionDate": str(session_date),
                "slotNo": int(slot_no),
            },
            http_status=409,
        )


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
        occurrence = None
        roster_identity = None
        roster_source = _ADMIN_SPECIAL if is_admin_special else "ADMIN_MANUAL"
        if task_id:
            task = db.get(AaTeachingTask, int(task_id))
            if not task or task.is_deleted or task.tenant_id != _tid():
                raise not_found("教学任务不存在")
            if not attendance_task_executable(task.status):
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

            requested_class_id = int(body.get("classId") or 0)
            task_class_id = int(task.class_id or 0)
            if requested_class_id and task_class_id and requested_class_id != task_class_id:
                raise AppException("VALIDATION_ERROR", "教学任务与行政班不一致")

            if not is_admin_special:
                occurrence = resolve_formal_occurrence(
                    db,
                    task,
                    batch,
                    current_term,
                    session_date=session_date,
                    slot_no=slot_no,
                    expected_schedule_item_id=body.get("scheduleItemId"),
                    lock=True,
                )

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

        if occurrence:
            _guard_no_duplicate_formal_session(
                db,
                AaAttendanceSession,
                class_id=class_id,
                teacher_key=teacher_key,
                session_date=occurrence["sessionDate"],
                slot_no=int(occurrence["slotNo"]),
                occurrence=occurrence,
            )

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
        if occurrence:
            audit_detail += (
                f";scheduleItem={occurrence['scheduleItemId']}"
                f";activeBatch={occurrence['activeBatchId']}"
                f";scope={occurrence['scopeType']}:{occurrence['scopeId']}"
            )
        if is_admin_special:
            audit_detail += f";reason={special_reason};evidence={special_evidence}"
        _audit(db, item.id, "CREATE", audit_detail)
        db.commit()
        db.refresh(item)
        result = _with_source_type(_row(item))
        result["teachingTaskId"] = str(task.id) if task else None
        result["rosterIdentity"] = roster_identity
        result["occurrenceEvidence"] = occurrence
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


def attendance_stats(user, class_id=None, term_code=None, session_type=None):
    """默认只统计正式教学场次；ADMIN_SPECIAL 必须显式筛选，禁止污染课堂指标。"""
    from app.models import AaAttendanceSession

    role = _role(user)
    with session() as db:
        conds = [
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.is_deleted.is_(False),
            AaAttendanceSession.status == "SUBMITTED",
            _stats_session_type_condition(AaAttendanceSession, session_type),
        ]
        if role not in _ADMIN_ROLES:
            keys = _teacher_keys(user)
            if not keys:
                return {
                    "sessionCount": 0,
                    "students": [],
                    "sourceScope": "FORMAL_TEACHING",
                    "sourceScopeLabel": "正式课堂",
                }
            conds.append(AaAttendanceSession.teacher_key.in_(sorted(keys)))
        if class_id:
            conds.append(AaAttendanceSession.class_id == int(class_id))
        if term_code:
            conds.append(AaAttendanceSession.term_code == term_code)

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
        is_special_scope = str(session_type or "").strip().upper() == _ADMIN_SPECIAL
        return {
            "sessionCount": len(rows),
            "students": students,
            "sourceScope": _ADMIN_SPECIAL if is_special_scope else "FORMAL_TEACHING",
            "sourceScopeLabel": "管理员特殊补录" if is_special_scope else "正式课堂",
        }


mark_attendance = _canonical.mark_attendance
submit_session = _canonical.submit_session