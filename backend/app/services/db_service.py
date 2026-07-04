"""
真实数据层（SQLite dev.db / PostgreSQL 通用，SQLAlchemy 2.x）
────────────────────────────────────────────────────────────
DB_ENABLED=true 时，students / approvals / todos / messages / audit 全部走本模块。
口径：tenant_id 过滤 + is_deleted=false；作废=逻辑删除；敏感字段只出脱敏值。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.core.context import current_tenant_id, get_current_user_ctx, get_request_meta, get_trace_id
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models import (SecurityAuditLog, StudentContact, StudentProfile, StudentStageEvent,
                        UnifiedMessage, UnifiedTodo, WorkflowInstance, WorkflowTask)

DEFAULT_TENANT = 1000000000000000001


def _tid() -> int:
    try:
        return int(current_tenant_id() or DEFAULT_TENANT)
    except (TypeError, ValueError):
        return DEFAULT_TENANT


def _iso(v) -> str | None:
    return v.isoformat(timespec="seconds") if isinstance(v, datetime) else (str(v) if v else None)


def _mask_phone(v: str | None) -> str:
    v = v or ""
    return v[:3] + "****" + v[-4:] if len(v) >= 7 else ("***" if v else "")


def _mask_id_card(v: str | None) -> str:
    v = v or ""
    return v[:3] + "*" * max(len(v) - 7, 4) + v[-4:] if len(v) >= 8 else ("***" if v else "")


def session():
    return get_sessionmaker()()


# ═══════════ 学生主档 ═══════════

def _student_row(s: StudentProfile, phone_plain: str | None = None, id_card_plain: str | None = None) -> dict:
    return {
        "id": str(s.id), "studentId": str(s.id), "tenantId": str(s.tenant_id),
        "studentNo": s.student_no, "realName": s.real_name, "gender": s.gender or "",
        "collegeId": str(s.college_id or ""), "collegeName": getattr(s, "_college_name", "") or "",
        "majorId": str(s.major_id or ""), "majorName": getattr(s, "_major_name", "") or "",
        "classId": str(s.class_id or ""), "className": getattr(s, "_class_name", "") or "",
        "grade": s.grade or "", "currentStage": s.current_stage, "studentStatus": s.student_status,
        "riskLevel": (s.remark or "NONE") if (s.remark in ("HIGH", "MEDIUM", "LOW")) else "NONE",
        # TODO(P4)：riskLevel 应来自风险信号表；冻结册第一批无该字段，暂借 remark 存放演示值
        "phoneMasked": _mask_phone(phone_plain) if phone_plain else "1**********",
        "idCardMasked": _mask_id_card(id_card_plain) if id_card_plain else "",
        "isDeleted": bool(s.is_deleted), "createdAt": _iso(s.created_at),
        "updatedAt": _iso(s.updated_at), "version": s.version,
    }


def _org_names(db, rows: list[StudentProfile]) -> None:
    from app.models import College, Major, SchoolClass
    colleges = {c.id: c.college_name for c in db.scalars(select(College)).all()}
    majors = {m.id: m.major_name for m in db.scalars(select(Major)).all()}
    classes = {k.id: k.class_name for k in db.scalars(select(SchoolClass)).all()}
    for s in rows:
        s._college_name = colleges.get(s.college_id, "")
        s._major_name = majors.get(s.major_id, "")
        s._class_name = classes.get(s.class_id, "")


def _primary_phone(db, student_id: int) -> str | None:
    c = db.scalars(select(StudentContact).where(
        StudentContact.tenant_id == _tid(), StudentContact.student_id == student_id,
        StudentContact.contact_type == "PHONE", StudentContact.is_deleted.is_(False))).first()
    # 演示环境：contact_value_encrypted 存的是演示明文占位（真实环境为密文，解密在授权服务内完成）
    return c.contact_value_encrypted if c else None


def list_students(page: int, page_size: int, keyword=None, college=None, major=None,
                  class_name=None, status=None, risk_level=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(StudentProfile).where(StudentProfile.tenant_id == _tid(),
                                         StudentProfile.is_deleted.is_(False))
        if keyword:
            like = f"%{keyword}%"
            q = q.where((StudentProfile.real_name.like(like)) | (StudentProfile.student_no.like(like)))
        if status:
            q = q.where((StudentProfile.student_status == status) | (StudentProfile.current_stage == status))
        if risk_level:
            q = q.where(StudentProfile.remark == risk_level)
        rows = db.scalars(q.order_by(StudentProfile.id)).all()
        _org_names(db, rows)
        if college:
            rows = [r for r in rows if college in (str(r.college_id), r._college_name)]
        if major:
            rows = [r for r in rows if major in (str(r.major_id), r._major_name)]
        if class_name:
            rows = [r for r in rows if class_name == r._class_name]
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        page_rows = rows[start:start + page_size]
        return [_student_row(s, _primary_phone(db, s.id)) for s in page_rows], total


def _get_profile(db, student_id) -> StudentProfile:
    row = db.get(StudentProfile, int(student_id))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("学生不存在或不在当前数据范围内")
    return row


def get_student(student_id) -> dict:
    with session() as db:
        s = _get_profile(db, student_id)
        _org_names(db, [s])
        contacts = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == s.id,
            StudentContact.is_deleted.is_(False))).all()
        events = db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.tenant_id == _tid(), StudentStageEvent.student_id == s.id
        ).order_by(StudentStageEvent.occurred_at.desc())).all()
        phone = next((c.contact_value_encrypted for c in contacts if c.contact_type == "PHONE"), None)
        return {
            **_student_row(s, phone),
            "contacts": [{
                "contactType": c.contact_type,
                "valueMasked": _mask_phone(c.contact_value_encrypted) if "PHONE" in c.contact_type
                               else ((c.contact_value_encrypted or "")[:6] + "****"),
                "contactName": c.contact_name or "", "verifiedStatus": c.verified_status,
                "isPrimary": bool(c.is_primary),
            } for c in contacts],
            "statusRecord": {"currentStage": s.current_stage, "studentStatus": s.student_status},
            "timeline": [{"eventCategory": e.source_module or "STAGE",
                          "title": f"{e.from_stage or '—'} → {e.to_stage}" if e.to_stage else (e.reason or ""),
                          "occurredAt": _iso(e.occurred_at)} for e in events],
        }


def create_student(body) -> dict:
    with session() as db:
        dup = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.student_no == body.studentNo,
            StudentProfile.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "学号已存在（租户内唯一）")
        s = StudentProfile(tenant_id=_tid(), student_no=body.studentNo, real_name=body.realName,
                           gender=body.gender, grade=body.grade,
                           college_id=int(body.collegeId) if body.collegeId else None,
                           major_id=int(body.majorId) if body.majorId else None,
                           class_id=int(body.classId) if body.classId else None,
                           current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.flush()
        if body.phone:
            db.add(StudentContact(tenant_id=_tid(), student_id=s.id, contact_type="PHONE",
                                  contact_value_encrypted=body.phone, is_primary=True,
                                  verified_status="UNVERIFIED"))
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=s.id, from_stage=None,
                                 to_stage="ORIENTATION", reason="建档", source_module="student"))
        db.commit()
        db.refresh(s)
        return _student_row(s, body.phone)


def update_student(student_id, body) -> dict:
    with session() as db:
        s = _get_profile(db, student_id)
        for src, col in [("realName", "real_name"), ("gender", "gender"), ("grade", "grade"), ("remark", "remark")]:
            v = getattr(body, src, None)
            if v is not None:
                setattr(s, col, v)
        s.version += 1
        phone = getattr(body, "phone", None)
        if phone:
            c = db.scalars(select(StudentContact).where(
                StudentContact.tenant_id == _tid(), StudentContact.student_id == s.id,
                StudentContact.contact_type == "PHONE")).first()
            if c:
                c.contact_value_encrypted = phone
            else:
                db.add(StudentContact(tenant_id=_tid(), student_id=s.id, contact_type="PHONE",
                                      contact_value_encrypted=phone, is_primary=True,
                                      verified_status="UNVERIFIED"))
        db.commit()
        db.refresh(s)
        _org_names(db, [s])
        return _student_row(s, phone or _primary_phone(db, s.id))


def void_student(student_id, reason: str) -> dict:
    with session() as db:
        s = _get_profile(db, student_id)
        s.is_deleted = True
        s.student_status = "RECYCLED"
        s.remark = f"VOID:{reason}"
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=s.id, from_stage=s.current_stage,
                                 to_stage="RECYCLED", reason=reason, source_module="student"))
        db.commit()
        return {"studentId": str(s.id), "studentStatus": "RECYCLED", "isDeleted": True, "physicalDelete": False}


def get_timeline(student_id) -> list[dict]:
    return get_student(student_id)["timeline"]


def get_risk_summary(student_id) -> dict:
    row = get_student(student_id)
    level = row["riskLevel"]
    return {"studentId": row["id"], "riskLevel": level,
            "signals": [] if level == "NONE" else [{"type": "GENERAL", "title": "存在风险信号（演示）",
                                                    "level": level, "occurredAt": row["updatedAt"]}]}


# ═══════════ 审批任务 ═══════════

def _task_row(t: WorkflowTask, inst: WorkflowInstance | None) -> dict:
    return {
        "taskId": str(t.id), "instanceId": str(t.instance_id), "tenantId": str(t.tenant_id),
        "title": (inst.title if inst else "") or "", "sourceModule": inst.source_module if inst else "",
        "sourceBizType": inst.source_biz_type if inst else "",
        "applicantName": (inst.remark or "") if inst else "",
        "nodeCode": t.node_code or "", "nodeName": t.remark or t.node_code or "",
        "status": t.status, "submittedAt": _iso(t.created_at),
        "actedAt": _iso(t.acted_at), "actionReason": t.action_reason or "",
        "urgency": "NORMAL",
    }


def _insts(db, ids) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(WorkflowInstance).where(WorkflowInstance.id.in_(ids))).all()
    return {r.id: r for r in rows}


def list_tasks(page: int, page_size: int, status: Optional[str] = None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(WorkflowTask).where(WorkflowTask.tenant_id == _tid(),
                                       WorkflowTask.is_deleted.is_(False),
                                       WorkflowTask.status == (status or "PENDING"))
        rows = db.scalars(q.order_by(WorkflowTask.id)).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        rows = rows[start:start + page_size]
        insts = _insts(db, [r.instance_id for r in rows])
        return [_task_row(t, insts.get(t.instance_id)) for t in rows], total


def get_task(task_id) -> dict:
    with session() as db:
        t = db.get(WorkflowTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("审批任务不存在")
        inst = db.get(WorkflowInstance, t.instance_id)
        return {**_task_row(t, inst),
                "history": [{"action": "SUBMIT", "by": (inst.remark if inst else "") or "-",
                             "at": _iso(t.created_at)}]}


def act_task(task_id, action: str, reason: str | None = None, target: str | None = None) -> dict:
    with session() as db:
        t = db.get(WorkflowTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("审批任务不存在")
        if t.status != "PENDING":
            raise AppException("APPROVAL_VERSION_CONFLICT", "任务已被处理，请刷新")
        t.status = action
        t.acted_at = datetime.utcnow()
        if reason:
            t.action_reason = reason
        if target:
            t.remark = f"TRANSFER_TO:{target}"
        t.version += 1
        inst = db.get(WorkflowInstance, t.instance_id)
        if inst and action in ("APPROVED", "REJECTED"):
            inst.status = action
        db.commit()
        return {"taskId": str(t.id), "status": t.status, "actedAt": _iso(t.acted_at),
                "instanceStatus": inst.status if inst else "RUNNING"}


def list_processed(page: int, page_size: int) -> tuple[list[dict], int]:
    with session() as db:
        rows = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
            WorkflowTask.status.in_(["APPROVED", "REJECTED", "TRANSFERRED"])
        ).order_by(WorkflowTask.acted_at.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        rows = rows[start:start + page_size]
        insts = _insts(db, [r.instance_id for r in rows])
        return [_task_row(t, insts.get(t.instance_id)) for t in rows], total


# ═══════════ 待办 / 消息 ═══════════

def list_todos(status=None, todo_type=None, page=1, page_size=20) -> tuple[list[dict], int, dict]:
    with session() as db:
        q = select(UnifiedTodo).where(UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False))
        if status:
            q = q.where(UnifiedTodo.status == status)
        if todo_type:
            q = q.where(UnifiedTodo.todo_type == todo_type)
        rows = db.scalars(q.order_by(UnifiedTodo.id)).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        items = [{
            "todoId": str(r.id), "todoType": r.todo_type, "title": r.title, "status": r.status,
            "sourceModule": r.source_module, "dueAt": _iso(r.due_at), "createdAt": _iso(r.created_at),
        } for r in rows[start:start + page_size]]
        by_type: dict[str, int] = {}
        for r in db.execute(select(UnifiedTodo.todo_type, func.count()).where(
                UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False)
        ).group_by(UnifiedTodo.todo_type)).all():
            by_type[r[0]] = r[1]
        return items, total, by_type


def todo_summary() -> dict:
    with session() as db:
        pending = db.scalar(select(func.count()).select_from(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.status == "PENDING")) or 0
        done = db.scalar(select(func.count()).select_from(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.status == "DONE")) or 0
        return {"pending": pending, "overdue": 0, "nearDeadline": 0, "doneToday": done}


def todo_done(todo_id) -> dict:
    with session() as db:
        r = db.get(UnifiedTodo, int(todo_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("待办不存在")
        r.status = "DONE"
        r.version += 1
        db.commit()
        return {"todoId": str(r.id), "status": "DONE"}


def list_messages(read_status=None, message_type=None, page=1, page_size=20) -> tuple[list[dict], int]:
    with session() as db:
        q = select(UnifiedMessage).where(UnifiedMessage.tenant_id == _tid(),
                                         UnifiedMessage.is_deleted.is_(False))
        if read_status:
            q = q.where(UnifiedMessage.status == read_status)
        if message_type:
            q = q.where(UnifiedMessage.message_type == message_type)
        rows = db.scalars(q.order_by(UnifiedMessage.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        return [{
            "messageId": str(r.id), "title": r.title, "content": r.content or "",
            "messageType": r.message_type or "SYSTEM", "readStatus": r.status,
            "createdAt": _iso(r.created_at), "readAt": _iso(r.read_at),
        } for r in rows[start:start + page_size]], total


def message_read(message_id) -> dict:
    with session() as db:
        r = db.get(UnifiedMessage, int(message_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("消息不存在")
        r.status = "READ"
        r.read_at = datetime.utcnow()
        r.version += 1
        db.commit()
        return {"messageId": str(r.id), "status": "READ"}


# ═══════════ 审计 ═══════════

def audit_insert(action: str, resource: str, detail: dict | None, result: str) -> None:
    user = get_current_user_ctx() or {}
    meta = get_request_meta()
    with session() as db:
        db.add(SecurityAuditLog(
            tenant_id=_tid(), operator_id=None, operator_name=user.get("realName"),
            current_role=user.get("currentRoleCode"), action=action, resource=resource,
            ip=meta.get("ip"), user_agent=meta.get("userAgent"),
            request_method=meta.get("method"), request_path=meta.get("path"),
            trace_id=get_trace_id(), result=result, detail_json=detail or {},
        ))
        db.commit()


def audit_query(page: int, page_size: int, action: str | None = None,
                operator: str | None = None, date_from: str | None = None,
                date_to: str | None = None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(SecurityAuditLog).where(SecurityAuditLog.tenant_id == _tid())
        if action:
            q = q.where(SecurityAuditLog.action == action)
        if operator:
            q = q.where(SecurityAuditLog.operator_name.like(f"%{operator}%"))
        if date_from:
            q = q.where(SecurityAuditLog.created_at >= date_from)
        if date_to:
            q = q.where(SecurityAuditLog.created_at <= date_to + " 23:59:59")
        rows = db.scalars(q.order_by(SecurityAuditLog.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        return [{
            "auditId": str(r.id), "action": r.action, "resource": r.resource or "",
            "ip": r.ip or "", "userAgent": (r.user_agent or "")[:80],
            "method": r.request_method or "", "path": r.request_path or "",
            "result": r.result or "SUCCESS", "actorId": r.operator_id, "actorName": r.operator_name,
            "tenantId": str(r.tenant_id), "requestId": r.trace_id, "detail": r.detail_json or {},
            "occurredAt": _iso(r.created_at),
        } for r in rows[start:start + page_size]], total
