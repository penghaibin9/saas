"""
真实数据层（SQLite dev.db / PostgreSQL 通用，SQLAlchemy 2.x）
────────────────────────────────────────────────────────────
DB_ENABLED=true 时，students / approvals / todos / messages / audit 全部走本模块。
口径：tenant_id 过滤 + is_deleted=false；作废=逻辑删除；敏感字段只出脱敏值。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, select

from app.core.context import current_tenant_id, get_current_user_ctx, get_request_meta, get_trace_id
from app.core.exceptions import AppException, not_found
from app.core.student_lifecycle import ADMITTED
from app.db.session import get_sessionmaker
from app.models import (SecurityAuditLog, StudentContact, StudentProfile, StudentStageEvent,
                        UnifiedMessage, UnifiedTodo, WorkflowInstance, WorkflowTask)

DEFAULT_TENANT = 1000000000000000001


def _tid() -> int:
    try:
        return int(current_tenant_id() or DEFAULT_TENANT)
    except (TypeError, ValueError):
        return DEFAULT_TENANT


def _as_id(v):
    """路径/入参主键安全转换（BUG-017）：非数字不再抛 ValueError → 500，而是 404 资源不存在。
    用于 db.get(Model, _as_id(x))，避免 /students/abc 之类脏 URL 打成服务端错误。"""
    try:
        return int(v)
    except (TypeError, ValueError):
        from app.core.exceptions import not_found
        raise not_found("资源不存在或标识不合法") from None


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
    tenant_id = _tid()
    college_ids = {s.college_id for s in rows if s.college_id is not None}
    major_ids = {s.major_id for s in rows if s.major_id is not None}
    class_ids = {s.class_id for s in rows if s.class_id is not None}
    colleges = ({c.id: c.college_name for c in db.scalars(select(College).where(
        College.tenant_id == tenant_id, College.id.in_(college_ids),
        College.is_deleted.is_(False))).all()} if college_ids else {})
    majors = ({m.id: m.major_name for m in db.scalars(select(Major).where(
        Major.tenant_id == tenant_id, Major.id.in_(major_ids),
        Major.is_deleted.is_(False))).all()} if major_ids else {})
    classes = ({k.id: k.class_name for k in db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == tenant_id, SchoolClass.id.in_(class_ids),
        SchoolClass.is_deleted.is_(False))).all()} if class_ids else {})
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
                  class_name=None, status=None, risk_level=None,
                  class_ids=None, student_ids=None, *, count_total: bool = True) -> tuple[list[dict], int]:
    # 数据范围收敛（SEC 口径）：class_ids/student_ids 由 API 层按角色解析；空集合 = fail-closed
    if class_ids is not None and not class_ids:
        return [], 0
    if student_ids is not None and not student_ids:
        return [], 0
    with session() as db:
        from app.models import College, Major, SchoolClass
        tenant_id = _tid()
        q = (select(StudentProfile, College.college_name, Major.major_name, SchoolClass.class_name)
             .outerjoin(College, and_(College.id == StudentProfile.college_id,
                                     College.tenant_id == tenant_id,
                                     College.is_deleted.is_(False)))
             .outerjoin(Major, and_(Major.id == StudentProfile.major_id,
                                   Major.tenant_id == tenant_id,
                                   Major.is_deleted.is_(False)))
             .outerjoin(SchoolClass, and_(SchoolClass.id == StudentProfile.class_id,
                                         SchoolClass.tenant_id == tenant_id,
                                         SchoolClass.is_deleted.is_(False)))
             .where(StudentProfile.tenant_id == tenant_id,
                    StudentProfile.is_deleted.is_(False)))
        if class_ids is not None:
            q = q.where(StudentProfile.class_id.in_(list(class_ids)))
        if student_ids is not None:
            q = q.where(StudentProfile.id.in_(list(student_ids)))
        if keyword:
            like = f"%{keyword}%"
            q = q.where((StudentProfile.real_name.like(like)) | (StudentProfile.student_no.like(like)))
        if status:
            q = q.where((StudentProfile.student_status == status) | (StudentProfile.current_stage == status))
        if risk_level:
            q = q.where(StudentProfile.remark == risk_level)
        if college:
            value = str(college).strip()
            q = q.where(StudentProfile.college_id == int(value)) if value.isdigit() else q.where(
                College.college_name.like(f"%{value}%"))
        if major:
            value = str(major).strip()
            q = q.where(StudentProfile.major_id == int(value)) if value.isdigit() else q.where(
                Major.major_name.like(f"%{value}%"))
        if class_name:
            q = q.where(SchoolClass.class_name == class_name)

        total = (db.scalar(select(func.count()).select_from(q.order_by(None).subquery())) or 0
                 if count_total else 0)
        result_rows = db.execute(q.order_by(StudentProfile.id)
                                 .offset((max(1, page) - 1) * page_size)
                                 .limit(page_size)).all()
        page_rows: list[StudentProfile] = []
        for student, college_name, major_name, school_class_name in result_rows:
            student._college_name = college_name or ""
            student._major_name = major_name or ""
            student._class_name = school_class_name or ""
            page_rows.append(student)

        phones: dict[int, str | None] = {}
        if page_rows:
            contacts = db.scalars(select(StudentContact).where(
                StudentContact.tenant_id == tenant_id,
                StudentContact.student_id.in_([s.id for s in page_rows]),
                StudentContact.contact_type == "PHONE",
                StudentContact.is_deleted.is_(False),
            ).order_by(StudentContact.is_primary.desc(), StudentContact.id)).all()
            for contact in contacts:
                phones.setdefault(contact.student_id, contact.contact_value_encrypted)
        return [_student_row(s, phones.get(s.id)) for s in page_rows], total


def _get_profile(db, student_id) -> StudentProfile:
    row = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(student_id), StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False))).first()
    if not row:
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


def _as_optional_id(v, field_label: str):
    """建档可选外键（学院/专业/班级 ID）安全转换：非数字入参返回 400 校验错误，不再让 int() 打成 500。"""
    if not v:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{field_label}格式非法：{v}") from None


def create_student(body) -> dict:
    with session() as db:
        dup = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.student_no == body.studentNo,
            StudentProfile.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "学号已存在（租户内唯一）")
        s = StudentProfile(tenant_id=_tid(), student_no=body.studentNo, real_name=body.realName,
                           gender=body.gender, grade=body.grade,
                           college_id=_as_optional_id(body.collegeId, "学院ID"),
                           major_id=_as_optional_id(body.majorId, "专业ID"),
                           class_id=_as_optional_id(body.classId, "班级ID"),
                           current_stage=ADMITTED, student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.flush()
        if body.phone:
            db.add(StudentContact(tenant_id=_tid(), student_id=s.id, contact_type="PHONE",
                                  contact_value_encrypted=body.phone, is_primary=True,
                                  verified_status="UNVERIFIED"))
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=s.id, from_stage=None,
                                 to_stage=ADMITTED, reason="建档", source_module="student"))
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
    rows = db.scalars(select(WorkflowInstance).where(
        WorkflowInstance.id.in_(ids), WorkflowInstance.tenant_id == _tid(),
        WorkflowInstance.is_deleted.is_(False))).all()
    return {r.id: r for r in rows}


def list_tasks(page: int, page_size: int, status: Optional[str] = None) -> tuple[list[dict], int]:
    with session() as db:
        cond = (WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
                WorkflowTask.status == (status or "PENDING"))
        total = db.scalar(select(func.count()).select_from(WorkflowTask).where(*cond)) or 0
        rows = db.scalars(select(WorkflowTask).where(*cond).order_by(WorkflowTask.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        insts = _insts(db, [r.instance_id for r in rows])
        return [_task_row(t, insts.get(t.instance_id)) for t in rows], total


def tasks_by_biz_type() -> list[dict]:
    with session() as db:
        rows = db.execute(
            select(WorkflowInstance.source_biz_type, func.count(WorkflowTask.id),
                   func.min(WorkflowTask.created_at))
            .select_from(WorkflowTask)
            .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
            .where(WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
                   WorkflowTask.status == "PENDING", WorkflowInstance.tenant_id == _tid(),
                   WorkflowInstance.is_deleted.is_(False))
            .group_by(WorkflowInstance.source_biz_type)
        ).all()
        return [{"bizType": r[0] or "GENERAL", "count": r[1], "earliest": _iso(r[2])} for r in rows]


def get_task(task_id) -> dict:
    with session() as db:
        t = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id), WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False))).first()
        if not t:
            raise not_found("审批任务不存在")
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == t.instance_id, WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False))).first()
        return {**_task_row(t, inst),
                "history": [{"action": "SUBMIT", "by": (inst.remark if inst else "") or "-",
                             "at": _iso(t.created_at)}]}


def act_task(task_id, action: str, reason: str | None = None, target: str | None = None) -> dict:
    with session() as db:
        t = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id), WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False))).first()
        if not t:
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
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == t.instance_id, WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False))).first()
        if inst and action in ("APPROVED", "REJECTED"):
            inst.status = action
        msg_campaign_id = None
        if inst and (inst.source_biz_type or "") == "MESSAGE_CAMPAIGN" and action in ("APPROVED", "REJECTED"):
            msg_campaign_id = int(inst.source_biz_id or 0)
        db.commit()
        result = {"taskId": str(t.id), "status": t.status, "actedAt": _iso(t.acted_at),
                  "instanceStatus": inst.status if inst else "RUNNING"}
    if msg_campaign_id:
        try:
            from app.core.context import get_current_user_ctx
            from app.services import message_campaign_service as camp_svc
            actor = dict(get_current_user_ctx() or {})
            if not actor.get("userId"):
                actor["userId"] = "0"
            if not actor.get("realName"):
                actor["realName"] = "审批中心"
            camp_svc.apply_workflow_decision(
                actor, campaign_id=msg_campaign_id,
                approved=(action == "APPROVED"), comment=reason)
            result["messageCampaignId"] = str(msg_campaign_id)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger("app.approval").exception(
                "MESSAGE_CAMPAIGN workflow side-effect failed campaign=%s", msg_campaign_id)
    return result


def list_processed(page: int, page_size: int) -> tuple[list[dict], int]:
    with session() as db:
        cond = (WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
                WorkflowTask.status.in_(["APPROVED", "REJECTED", "TRANSFERRED"]))
        total = db.scalar(select(func.count()).select_from(WorkflowTask).where(*cond)) or 0
        rows = db.scalars(select(WorkflowTask).where(*cond).order_by(WorkflowTask.acted_at.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
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
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(UnifiedTodo.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [{
            "todoId": str(r.id), "todoType": r.todo_type, "title": r.title, "status": r.status,
            "sourceModule": r.source_module, "dueAt": _iso(r.due_at), "createdAt": _iso(r.created_at),
        } for r in rows]
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
        r = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.is_deleted.is_(False))).first()
        if not r:
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
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(UnifiedMessage.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [{
            "messageId": str(r.id), "title": r.title, "content": r.content or "",
            "messageType": r.message_type or "SYSTEM", "readStatus": r.status,
            "createdAt": _iso(r.created_at), "readAt": _iso(r.read_at),
        } for r in rows], total


def message_read(message_id) -> dict:
    with session() as db:
        r = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.id == int(message_id), UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.is_deleted.is_(False))).first()
        if not r:
            raise not_found("消息不存在")
        r.status = "READ"
        r.read_at = datetime.utcnow()
        r.version += 1
        db.commit()
        return {"messageId": str(r.id), "status": "READ"}


# ═══════════ 审计 ═══════════

def audit_insert(action: str, resource: str, detail: dict | None, result: str,
                 *, tenant_id: int | None = None, resource_id: str | None = None) -> None:
    """写一条安全审计。
    tenant_id：显式指定审计归属租户（平台超管跨租户操作时传"被操作学校"，
               使该校自身审计可见平台侧动作；默认沿用请求上下文租户）。
    operator_id：从上下文 userId（db-<id>）解析真实操作人主键，不再恒为 None。"""
    user = get_current_user_ctx() or {}
    meta = get_request_meta()
    raw_uid = str(user.get("userId") or "")
    operator_id = int(raw_uid[3:]) if raw_uid.startswith("db-") and raw_uid[3:].isdigit() else None
    with session() as db:
        db.add(SecurityAuditLog(
            tenant_id=tenant_id if tenant_id is not None else _tid(),
            operator_id=operator_id, operator_name=user.get("realName"),
            current_role=user.get("currentRoleCode"), action=action, resource=resource,
            resource_id=resource_id,
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
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(SecurityAuditLog.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [{
            "auditId": str(r.id), "action": r.action, "resource": r.resource or "",
            "ip": r.ip or "", "userAgent": (r.user_agent or "")[:80],
            "method": r.request_method or "", "path": r.request_path or "",
            "result": r.result or "SUCCESS", "actorId": r.operator_id, "actorName": r.operator_name,
            "tenantId": str(r.tenant_id), "requestId": r.trace_id, "detail": r.detail_json or {},
            "occurredAt": _iso(r.created_at),
        } for r in rows], total
