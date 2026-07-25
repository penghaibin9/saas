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
from app.core.field_crypto import mask_id_card, mask_phone
from app.db.session import get_sessionmaker
from app.models import (SecurityAuditLog, StudentContact, StudentProfile, StudentStageEvent,
                        UnifiedMessage, UnifiedTodo, WorkflowInstance, WorkflowTask)

DEFAULT_TENANT = 1000000000000000001  # 仅文档/历史引用；写路径禁止兜底


def _tid() -> int:
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝数据库写入")
    return tid


def _as_id(v):
    """路径/入参主键安全转换（BUG-017）：非数字不再抛 ValueError → 500，而是 404 资源不存在。
    用于 db.get(Model, _as_id(x))，避免 /students/abc 之类脏 URL 打成服务端错误。"""
    try:
        return int(v)
    except (TypeError, ValueError):
        from app.core.exceptions import not_found
        raise not_found("资源不存在或标识不合法") from None


def _iso(v) -> str | None:
    from app.core.timeutil import iso_utc
    if isinstance(v, datetime):
        return iso_utc(v)
    return str(v) if v else None


# 脱敏实现统一收口到 core.field_crypto，避免多份副本行为漂移。
# 这两个别名只接受**明文**；`_encrypted` 列必须用 mask_phone_encrypted / mask_id_card_encrypted。
_mask_phone = mask_phone
_mask_id_card = mask_id_card


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
    from app.core.field_crypto import decrypt_field
    c = db.scalars(select(StudentContact).where(
        StudentContact.tenant_id == _tid(), StudentContact.student_id == student_id,
        StudentContact.contact_type == "PHONE", StudentContact.is_deleted.is_(False))).first()
    if not c:
        return None
    return decrypt_field(c.contact_value_encrypted)


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
                from app.core.field_crypto import decrypt_field
                phones.setdefault(contact.student_id, decrypt_field(contact.contact_value_encrypted))
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
        from app.core.field_crypto import decrypt_field
        phone = None
        contact_views = []
        for c in contacts:
            plain = decrypt_field(c.contact_value_encrypted)
            if c.contact_type == "PHONE" and phone is None:
                phone = plain
            if "PHONE" in (c.contact_type or ""):
                masked = _mask_phone(plain)
            elif "ID" in (c.contact_type or "").upper() or "CARD" in (c.contact_type or "").upper():
                raw = plain or ""
                masked = (raw[:4] + "**********" + raw[-2:]) if len(raw) >= 6 else "****"
            else:
                raw = plain or ""
                masked = (raw[:6] + "****") if raw else "****"
            contact_views.append({
                "contactType": c.contact_type,
                "valueMasked": masked,
                "contactName": c.contact_name or "", "verifiedStatus": c.verified_status,
                "isPrimary": bool(c.is_primary),
            })
        return {
            **_student_row(s, phone),
            "contacts": contact_views,
            "statusRecord": {"currentStage": s.current_stage, "studentStatus": s.student_status},
            "timeline": [{"eventCategory": e.source_module or "STAGE",
                          "title": f"{e.from_stage or '—'} → {e.to_stage}" if e.to_stage else (e.reason or ""),
                          "occurredAt": _iso(e.occurred_at)} for e in events],
        }


def create_student(body) -> dict:
    """建档：统一走 student_master_application_service，本函数只做请求体→命令对象的转换。

    学号产品语义（已锁定）：租户内学号永久唯一，作废后同号只能「复活」同一主档 PK，
    禁止新建第二档；uk_tenant_student_no 全表唯一（含软删行），复活复用原 id，
    保证历史关联不断档。该语义现由统一服务实现，四条建档链共用。
    """
    from sqlalchemy.exc import IntegrityError

    from app.core.student_master_contract import SOURCE_MANUAL, StudentCreateCommand
    from app.services import student_master_application_service as master

    cmd = StudentCreateCommand(
        student_no=body.studentNo, real_name=body.realName, source=SOURCE_MANUAL,
        gender=body.gender, grade=body.grade,
        college_id=body.collegeId, major_id=body.majorId, class_id=body.classId,
        phone=body.phone)
    with session() as db:
        result = master.create_student_in_session(
            db, tenant_id=_tid(), cmd=cmd, actor=get_current_user_ctx())
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AppException("DATA_CONFLICT", "学号已存在（租户内唯一）") from e
        s = db.get(StudentProfile, result.student_id)
        db.refresh(s)
        _org_names(db, [s])
        row = _student_row(s, body.phone)
        row["restored"] = result.restored
        if result.restored:
            row["message"] = "已复活原学号主档（同一 studentId），非新建档案"
        return row


def update_student(student_id, body) -> dict:
    """更正身份字段：统一走应用服务（含 expectedVersion 原子乐观锁）。

    组织归属（学院/专业/班级）不在此处理——那必须走学籍异动，见补充审计 §4.3。
    此前 Schema 声明允许传这三个字段但 Service 静默忽略，用户以为改了实际没改；
    现在改为显式拒绝并指路，不再假装成功。
    """
    from app.core.student_master_contract import SOURCE_MANUAL, StudentIdentityUpdateCommand
    from app.services import student_master_application_service as master

    for f, label in (("collegeId", "学院"), ("majorId", "专业"), ("classId", "班级")):
        if getattr(body, f, None):
            raise AppException(
                "VALIDATION_ERROR",
                f"{label}调整不能在主档编辑里直接改，请走 教务中心 › 学籍异动"
                "（转专业/转班需审批留痕）")

    cmd = StudentIdentityUpdateCommand(
        expected_version=getattr(body, "expectedVersion", None),
        real_name=getattr(body, "realName", None),
        gender=getattr(body, "gender", None),
        grade=getattr(body, "grade", None),
        phone=getattr(body, "phone", None),
        remark=getattr(body, "remark", None),
        source=SOURCE_MANUAL)
    with session() as db:
        s = master.update_identity_in_session(
            db, tenant_id=_tid(), student_id=_as_id(student_id), cmd=cmd,
            actor=get_current_user_ctx())
        db.commit()
        db.refresh(s)
        _org_names(db, [s])
        return _student_row(s, cmd.phone or _primary_phone(db, s.id))


def void_student(student_id, reason: str) -> dict:
    with session() as db:
        s = _get_profile(db, student_id)
        s.is_deleted = True
        s.student_status = "RECYCLED"
        s.remark = f"VOID:{reason}"
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=s.id, from_stage=s.current_stage,
                                 to_stage="RECYCLED", reason=reason, source_module="student"))
        # 高危审计同事务：失败则回滚作废
        audit_insert_in_session(
            db, "作废学生", "student",
            {"reason": reason, "studentNo": s.student_no}, "SUCCESS",
            resource_id=str(s.id))
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
        "assigneeId": str(t.assignee_id), "version": int(t.version or 0),
        "title": (inst.title if inst else "") or "", "sourceModule": inst.source_module if inst else "",
        "sourceBizType": inst.source_biz_type if inst else "",
        "applicantName": (inst.remark or "") if inst else "",
        "nodeCode": t.node_code or "", "nodeName": t.remark or t.node_code or "",
        "status": t.status, "submittedAt": _iso(t.created_at),
        "actedAt": _iso(t.acted_at), "actionReason": t.action_reason or "",
        "urgency": "NORMAL",
    }


def _approval_actor_id(user: dict | None) -> int:
    from app.core.context import get_current_user_ctx
    from app.services.message_identity import resolve_message_user_id
    return resolve_message_user_id(user or get_current_user_ctx() or {})


def _can_manage_all_approvals(user: dict | None) -> bool:
    from app.core.context import get_current_user_ctx
    from app.core.permissions import has_permission
    u = user or get_current_user_ctx() or {}
    return has_permission(u, "*") or has_permission(u, "approval.manage")


def _assert_task_assignee(t: WorkflowTask, user: dict | None) -> None:
    if _can_manage_all_approvals(user):
        return
    uid = _approval_actor_id(user)
    if not uid or int(t.assignee_id) != int(uid):
        raise not_found("审批任务不存在")


def _insts(db, ids) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(WorkflowInstance).where(
        WorkflowInstance.id.in_(ids), WorkflowInstance.tenant_id == _tid(),
        WorkflowInstance.is_deleted.is_(False))).all()
    return {r.id: r for r in rows}


def list_tasks(page: int, page_size: int, status: Optional[str] = None,
               user: dict | None = None) -> tuple[list[dict], int]:
    with session() as db:
        cond = [WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
                WorkflowTask.status == (status or "PENDING")]
        if not _can_manage_all_approvals(user):
            cond.append(WorkflowTask.assignee_id == _approval_actor_id(user))
        total = db.scalar(select(func.count()).select_from(WorkflowTask).where(*cond)) or 0
        rows = db.scalars(select(WorkflowTask).where(*cond).order_by(WorkflowTask.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        insts = _insts(db, [r.instance_id for r in rows])
        return [_task_row(t, insts.get(t.instance_id)) for t in rows], total


def tasks_by_biz_type(user: dict | None = None) -> list[dict]:
    with session() as db:
        cond = [WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
                WorkflowTask.status == "PENDING", WorkflowInstance.tenant_id == _tid(),
                WorkflowInstance.is_deleted.is_(False)]
        if not _can_manage_all_approvals(user):
            cond.append(WorkflowTask.assignee_id == _approval_actor_id(user))
        rows = db.execute(
            select(WorkflowInstance.source_biz_type, func.count(WorkflowTask.id),
                   func.min(WorkflowTask.created_at))
            .select_from(WorkflowTask)
            .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
            .where(*cond)
            .group_by(WorkflowInstance.source_biz_type)
        ).all()
        return [{"bizType": r[0] or "GENERAL", "count": r[1], "earliest": _iso(r[2])} for r in rows]


def get_task(task_id, user: dict | None = None) -> dict:
    with session() as db:
        t = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id), WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False))).first()
        if not t:
            raise not_found("审批任务不存在")
        _assert_task_assignee(t, user)
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == t.instance_id, WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False))).first()
        return {**_task_row(t, inst),
                "history": [{"action": "SUBMIT", "by": (inst.remark if inst else "") or "-",
                             "at": _iso(t.created_at)}]}


def act_task(task_id, action: str, reason: str | None = None, target: str | None = None,
             user: dict | None = None, version=None) -> dict:
    """审批动作与消息副作用、高危审计同事务；副作用失败则整体回滚，禁止假成功。"""
    from app.core.optimistic_lock import atomic_versioned_update, require_expected_version
    from app.services import mock_audit_service as audit
    require_expected_version(version)
    msg_campaign_id = None
    delivery_hint = None
    result = {}
    with session() as db:
        t = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id), WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False))).first()
        if not t:
            raise not_found("审批任务不存在")
        _assert_task_assignee(t, user)
        values = {
            "status": action,
            "acted_at": datetime.utcnow(),
        }
        if reason:
            values["action_reason"] = reason
        if target:
            values["remark"] = f"TRANSFER_TO:{target}"
        atomic_versioned_update(
            db, WorkflowTask, entity_id=int(task_id), tenant_id=_tid(),
            expected_version=version, values=values, expected_status="PENDING")
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == t.instance_id, WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False))).first()
        if inst and action in ("APPROVED", "REJECTED"):
            inst.status = action
        if inst and (inst.source_biz_type or "") == "MESSAGE_CAMPAIGN" and action in ("APPROVED", "REJECTED"):
            msg_campaign_id = int(inst.source_biz_id or 0)
            from app.core.context import get_current_user_ctx
            from app.services import message_campaign_service as camp_svc
            actor = dict(user or get_current_user_ctx() or {})
            if not actor.get("userId"):
                actor["userId"] = "0"
            if not actor.get("realName"):
                actor["realName"] = "审批中心"
            # 同事务副作用：失败即抛错，外层不 commit
            delivery_hint = camp_svc.apply_workflow_decision_in_db(
                db, actor, campaign_id=msg_campaign_id,
                approved=(action == "APPROVED"), comment=reason,
                skip_workflow_close=True)
        if action in ("APPROVED", "REJECTED"):
            audit.record_critical(
                "审批通过" if action == "APPROVED" else "审批驳回",
                method="POST",
                path=f"/api/v1/approvals/tasks/{task_id}/"
                     f"{'approve' if action == 'APPROVED' else 'reject'}",
                status_code=200, target_type="approval", target_id=str(task_id),
                detail={"action": action, "reason": reason,
                        "messageCampaignId": str(msg_campaign_id) if msg_campaign_id else None},
                db=db)
        db.commit()
        result = {"taskId": str(task_id), "status": action, "actedAt": _iso(datetime.utcnow()),
                  "instanceStatus": inst.status if inst else "RUNNING",
                  "version": int(version) + 1}
        if msg_campaign_id:
            result["messageCampaignId"] = str(msg_campaign_id)
    # 提交后尽力内联消费作业；作业已落库，失败不回滚审批
    if (delivery_hint and isinstance(delivery_hint, dict)
            and delivery_hint.get("alreadyEnqueued") and msg_campaign_id):
        try:
            from app.services import message_delivery_service as delivery_svc
            delivery_svc.accept_and_deliver(
                int(msg_campaign_id), delivery_hint.get("userIds") or [],
                force_async=True, already_enqueued=True)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger("app.approval").exception(
                "MESSAGE_CAMPAIGN post-commit claim failed campaign=%s", msg_campaign_id)
    return result


def list_processed(page: int, page_size: int, user: dict | None = None) -> tuple[list[dict], int]:
    with session() as db:
        cond = [WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
                WorkflowTask.status.in_(["APPROVED", "REJECTED", "TRANSFERRED"])]
        if not _can_manage_all_approvals(user):
            cond.append(WorkflowTask.assignee_id == _approval_actor_id(user))
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

def audit_insert_in_session(db, action: str, resource: str, detail: dict | None, result: str,
                            *, tenant_id: int | None = None, resource_id: str | None = None) -> None:
    """高危审计：写入调用方会话，随业务事务提交。"""
    user = get_current_user_ctx() or {}
    meta = get_request_meta()
    raw_uid = str(user.get("userId") or "")
    operator_id = int(raw_uid[3:]) if raw_uid.startswith("db-") and raw_uid[3:].isdigit() else None
    db.add(SecurityAuditLog(
        tenant_id=tenant_id if tenant_id is not None else _tid(),
        operator_id=operator_id, operator_name=user.get("realName"),
        current_role=user.get("currentRoleCode"), action=action, resource=resource,
        resource_id=resource_id,
        ip=meta.get("ip"), user_agent=meta.get("userAgent"),
        request_method=meta.get("method"), request_path=meta.get("path"),
        trace_id=get_trace_id(), result=result, detail_json=detail or {},
    ))


def audit_insert(action: str, resource: str, detail: dict | None, result: str,
                 *, tenant_id: int | None = None, resource_id: str | None = None) -> None:
    """写一条安全审计（独立会话提交）。高危场景优先用 audit_insert_in_session。"""
    with session() as db:
        audit_insert_in_session(db, action, resource, detail, result,
                                tenant_id=tenant_id, resource_id=resource_id)
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
