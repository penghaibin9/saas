"""13A-P4 风险预警中枢（8 态，处置类不走审批·时效优先，全动作落 handle_record 留痕）。

多来源引用（不复制来源数据），(source, source_ref_id) 唯一防重复建单。
NEW→ASSIGNED→PROCESSING→(FOLLOWING)→CLOSED；转办/升级/接管/重开；超时扫描(分派/升级)幂等。
心理(MENTAL)来源明细仅授权角色可见，普通教师仅见"需关注"标记。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.permissions import has_permission
from app.services.db_service import _iso, _tid, session
from app.services.affairs_sla import get_risk_sla, risk_due_at, risk_is_overdue

SOURCES = ("LEAVE_OVERDUE", "ACADEMIC_WARNING", "DORM", "MENTAL", "DISCIPLINE", "INTERNSHIP",
           "GRADUATION_DESIGN", "EMPLOYMENT", "FAMILY", "MANUAL")
LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
# 兼容既有内部调用；实际时限一律由 affairs_sla 的等级配置决定。
def _risk_new_assign_hours(level: str | None = None) -> float:
    return get_risk_sla(level)["assignHours"]


def _risk_assigned_process_hours(level: str | None = None) -> float:
    return get_risk_sla(level)["processHours"]


def _owner_role_user_ids(db) -> set[int]:
    """同租户在职且任一激活角色可处置风险的账号 id 集合。"""
    from app.models import Role, User, UserRole

    rows = db.execute(select(UserRole.user_id, Role).join(
        Role, Role.id == UserRole.role_id
    ).join(
        User, User.id == UserRole.user_id
    ).where(
        UserRole.tenant_id == _tid(), UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE",
        Role.tenant_id == _tid(), Role.is_deleted.is_(False), Role.status == "ACTIVE",
        User.tenant_id == _tid(), User.is_deleted.is_(False), User.status == "ACTIVE",
    )).all()
    eligible: set[int] = set()
    tenant_id = str(_tid())
    for user_id, role in rows:
        fake_user_ctx = {
            "userId": str(user_id),
            "currentRoleCode": role.role_code,
            "tenantId": tenant_id,
            "activeContextId": f"role:{role.id}",
        }
        if has_permission(fake_user_ctx, "studentAffairs.risk.handle"):
            eligible.add(int(user_id))
    return eligible


def list_owner_candidates(keyword: str | None = None) -> list[dict]:
    """可分派的风险责任人（在职 + 同租户 + 可处置风险）。供前端责任人选择器远程搜索。"""
    from app.models import User
    with session() as db:
        eligible = _owner_role_user_ids(db)
        if not eligible:
            return []
        q = select(User).where(User.tenant_id == _tid(), User.is_deleted.is_(False),
                               User.status == "ACTIVE", User.id.in_(eligible))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where((User.real_name.like(like)) | (User.login_name.like(like)))
        rows = db.scalars(q.order_by(User.real_name, User.id).limit(200)).all()
        return [{"id": str(u.id), "name": u.real_name, "loginName": u.login_name,
                 "userType": u.user_type} for u in rows]


def _validate_owner(db, owner_id, student_id=None) -> int:
    """责任人校验：必须是存在、同租户、在职、且可处置风险的真实账号。"""
    from app.models import User
    raw = str(owner_id or "").strip()
    if not raw or not raw.isdigit():
        raise AppException("VALIDATION_ERROR", "请选择有效责任人")
    u = db.get(User, int(raw))
    if not u or u.is_deleted or u.tenant_id != _tid() or u.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "责任人不存在或已停用")
    if u.id not in _owner_role_user_ids(db):
        raise AppException("VALIDATION_ERROR", "该账号无学工风险处置权限，不能作为责任人")
    if student_id is not None:
        from app.core.affairs_security import build_affairs_context
        from app.models import Role, UserRole
        roles = db.scalars(select(Role).join(UserRole, UserRole.role_id == Role.id).where(
            UserRole.tenant_id == _tid(), UserRole.user_id == u.id,
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
            Role.tenant_id == _tid(), Role.status == "ACTIVE", Role.is_deleted.is_(False),
        )).all()
        covered = False
        for role in roles:
            candidate = {
                "userId": str(u.id), "loginName": u.login_name,
                "currentRoleCode": role.role_code, "tenantId": str(_tid()),
                "activeContextId": f"role:{role.id}",
            }
            if not has_permission(candidate, "studentAffairs.risk.handle"):
                continue
            try:
                build_affairs_context(candidate, db).require_student(db, student_id)
                covered = True
                break
            except AppException:
                continue
        if not covered:
            raise AppException("VALIDATION_ERROR", "责任人的数据范围不覆盖该学生，不能分派")
    return int(u.id)

L_RISK = {
    "NEW": "新建", "ASSIGNED": "已分派", "PROCESSING": "处置中", "FOLLOWING": "持续跟进",
    "TRANSFERRED": "已转办", "ESCALATED": "已升级", "CLOSED": "已关闭", "REOPENED": "已重开",
}

# 风险状态机唯一注册表：写操作和详情可用动作必须共同读取本表，禁止两处规则漂移。
RISK_TRANSITIONS = {
    "ASSIGN": {"from": {"NEW", "REOPENED", "TRANSFERRED"}, "to": "ASSIGNED",
               "permission": "studentAffairs.risk.assign"},
    "PROCESS": {"from": {"ASSIGNED", "PROCESSING"}, "to": "PROCESSING",
                "permission": "studentAffairs.risk.handle", "relationship": "OWNER_OR_ADMIN"},
    "FOLLOW": {"from": {"PROCESSING", "FOLLOWING"}, "to": "FOLLOWING",
               "permission": "studentAffairs.risk.handle", "relationship": "OWNER_OR_ADMIN"},
    "TRANSFER": {"from": {"PROCESSING", "FOLLOWING"}, "to": "TRANSFERRED",
                 "permission": "studentAffairs.risk.transfer", "relationship": "OWNER_OR_ADMIN"},
    "ESCALATE": {"from": {"PROCESSING", "FOLLOWING"}, "to": "ESCALATED",
                 "permission": "studentAffairs.risk.escalate", "relationship": "OWNER_OR_ADMIN"},
    "TAKEOVER": {"from": {"ESCALATED"}, "to": "PROCESSING",
                 "permission": "studentAffairs.risk.handle", "relationship": "SUPERIOR"},
    "CLOSE": {"from": {"PROCESSING", "FOLLOWING", "ESCALATED"}, "to": "CLOSED",
              "permission": "studentAffairs.risk.close", "relationship": "OWNER_OR_ADMIN"},
    "REOPEN": {"from": {"CLOSED"}, "to": "REOPENED",
               "permission": "studentAffairs.risk.reopen", "relationship": "SUPERIOR"},
}


def _uid_norm(user_or_id) -> str:
    """将 db-123、123 和 int 统一为可比较的数字字符串。"""
    value = (user_or_id or {}).get("userId") if isinstance(user_or_id, dict) else user_or_id
    raw = str(value or "").strip()
    if raw.startswith("db-"):
        raw = raw[3:]
    try:
        return str(int(raw)) if raw else ""
    except (TypeError, ValueError):
        return ""


def _transition_or_conflict(x, action: str) -> str:
    rule = RISK_TRANSITIONS[action]
    if x.status not in rule["from"]:
        raise AppException("APPROVAL_VERSION_CONFLICT", f"当前状态不可{action.lower()}")
    return rule["to"]


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="RISK", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _handle(db, risk_id, action, content, frm, to):
    from app.models import AffairsRiskHandle
    n, _r, _u = _op()
    db.add(AffairsRiskHandle(tenant_id=_tid(), risk_id=int(risk_id), action=action, content=content,
                            operator=n, from_status=frm, to_status=to))


def _msg(db, receiver_id, title, content, mtype, risk_id):
    from app.services.message_event_outbox_service import emit_receiver_notice
    if (mtype or "").upper() == "RISK_ALERT":
        emit_receiver_notice(
            db,
            event_code="RISK.ALERT",
            source_module="student-affairs",
            source_biz_type="risk",
            source_biz_id=int(risk_id),
            receiver_id=receiver_id,
            title=title,
            content=content,
            receiver_as="user",
            dedup_extra=mtype,
        )
    else:
        emit_receiver_notice(
            db,
            event_code="RISK.STATUS",
            source_module="student-affairs",
            source_biz_type="risk",
            source_biz_id=int(risk_id),
            receiver_id=receiver_id,
            title=title,
            content=content,
            receiver_as="student",
            dedup_extra=mtype,
        )



def _drain_message_outbox():
    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="risk-inline")


def _sa_admin_user_ids(db) -> set[int]:
    """学工处管理员账号（升级/超时通知收件人）。"""
    from app.models import Role, UserRole
    role_ids = db.scalars(select(Role.id).where(
        Role.tenant_id == _tid(), Role.role_code == "STUDENT_AFFAIRS_ADMIN",
        Role.is_deleted.is_(False), Role.status == "ACTIVE")).all()
    if not role_ids:
        return set()
    return set(int(v) for v in db.scalars(select(UserRole.user_id).where(
        UserRole.tenant_id == _tid(), UserRole.role_id.in_(role_ids),
        UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE")).all())


def _notify_risk_handlers(db, x, title, content):
    """风险处置通知：责任人 + 学工处管理员；绝不写 receiver_id=0。"""
    targets = set(_sa_admin_user_ids(db))
    if x.owner_id:
        targets.add(int(x.owner_id))
    for uid in targets:
        _msg(db, uid, title, content, "RISK_ALERT", x.id)


def _todo_upsert(db, risk_id, assignee_id, student_id, title):
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(risk_id), UnifiedTodo.todo_type == "RISK_HANDLE",
        UnifiedTodo.assignee_id == int(assignee_id or 0),
        UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="student-affairs", source_biz_type="RISK",
                           source_biz_id=int(risk_id), todo_type="RISK_HANDLE",
                           assignee_id=int(assignee_id or 0), student_id=student_id, title=title,
                           status="PENDING"))


def _todo_done(db, risk_id):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_id == int(risk_id), UnifiedTodo.todo_type == "RISK_HANDLE",
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该风险不在您的数据范围内")


def _uid_int(user) -> int:
    raw = _uid_norm(user)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _require_owner_or_admin(db, x, user, *, label: str = "处置") -> None:
    """处置类动作：租户全域可代办；否则必须是当前责任人。防同班辅导员互动他人的单。"""
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return
    uid = _uid_int(user)
    if x.owner_id and uid and _uid_norm(x.owner_id) == _uid_norm(uid):
        return
    raise AppException("NO_PERMISSION", f"仅风险责任人或学工管理员可{label}")


def _require_takeover_authority(db, user) -> None:
    """升级后接管：仅租户全域或学院/学工管理角色（同班辅导员不可互抢）。"""
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return
    role = (user or {}).get("currentRoleCode") or ""
    if role in ("COLLEGE_ADMIN", "COLLEGE_SA", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SCHOOL_ADMIN"):
        return
    raise AppException("NO_PERMISSION", "仅上级/学工管理员可接管已升级风险")


def _can_view_mental(user) -> bool:
    return has_permission(user or {}, "studentAffairs.risk.psyDetail.view")


def _sensitive_view_audit(x, reason: str) -> None:
    """查看心理来源风险明细 → 写 t_security_audit_log(SENSITIVE_VIEW)。

    强敏感：审计失败不得静默放行明文（调用方须在审计成功后再 reveal）。
    """
    from app.services import audit_log
    audit_log.record(
        "SENSITIVE_VIEW",
        f"risk:{x.id}",
        detail={"source": x.source, "studentId": str(x.student_id),
                "reason": str(reason)[:200]},
        result="SUCCESS",
    )


def _row(x, user, s=None, reveal=False, owner=None) -> dict:
    # 列表恒遮蔽心理明细（仅摘要）；明细页须经授权角色 + 填写原因，get_risk 内 reveal=True 且写 SENSITIVE_VIEW。
    mental_masked = (x.source == "MENTAL" and not (reveal and _can_view_mental(user)))
    owner_name = (owner.real_name if owner else "") or ""
    owner_login = (owner.login_name if owner else "") or ""
    sla = get_risk_sla(getattr(x, "risk_level", None))
    due_at = risk_due_at(x)
    return {
        "riskId": str(x.id), "studentId": str(x.student_id),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "source": x.source, "sourceRefId": str(x.source_ref_id or ""),
        "riskLevel": x.risk_level, "title": x.title or "",
        "detail": "[心理关注·明细受限]" if mental_masked else (x.detail or ""),
        "mentalMasked": mental_masked, "ownerId": str(x.owner_id or ""),
        "ownerName": owner_name, "ownerLoginName": owner_login,
        "status": x.status, "statusLabel": L_RISK.get(x.status, x.status),
        "isArchived": bool(x.is_archived), "version": x.version,
        "assignedAt": _iso(getattr(x, "assigned_at", None)),
        "createdAt": _iso(getattr(x, "created_at", None)),
        "sla": {
            **sla, "overdue": risk_is_overdue(x),
            "dueAt": _iso(due_at) if due_at else None,
        },
    }


def _load(db, risk_id):
    from app.models import AffairsRiskRecord, StudentProfile
    x = db.get(AffairsRiskRecord, int(risk_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("风险记录不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def _handle_count(db, risk_id) -> int:
    from app.models import AffairsRiskHandle
    return db.scalar(select(func.count()).select_from(AffairsRiskHandle).where(
        AffairsRiskHandle.tenant_id == _tid(), AffairsRiskHandle.risk_id == int(risk_id),
        AffairsRiskHandle.is_deleted.is_(False))) or 0


# ═══════════ 建单 / 分派 ═══════════

def create_risk(body, user) -> dict:
    if (body.source or "") not in SOURCES:
        raise AppException("VALIDATION_ERROR", "风险来源非法")
    if (body.riskLevel or "MEDIUM") not in LEVELS:
        raise AppException("VALIDATION_ERROR", "风险等级非法")
    raw_sid = str(getattr(body, "studentId", None) or "").strip()
    if not raw_sid.isdigit():
        raise AppException("VALIDATION_ERROR", "请选择有效学生")
    with session() as db:
        from app.models import AffairsRiskRecord, StudentProfile
        s = db.get(StudentProfile, int(raw_sid))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        _scope_or_403(db, s.id, user)
        # sourceRefId 合法性：非数字直接 422（修复 manual-<ts> → int() 抛 500）。
        # MANUAL 人工建单无来源单据，忽略 sourceRefId、不参与去重。
        ref = getattr(body, "sourceRefId", None)
        ref_int = None
        if body.source != "MANUAL" and ref is not None and str(ref).strip() != "":
            rs = str(ref).strip()
            if not rs.isdigit():
                raise AppException("VALIDATION_ERROR", "sourceRefId 非法：须为来源单据的数字ID")
            ref_int = int(rs)
        # (source, source_ref_id) 唯一防重复建单 → 409（来源幂等）
        if ref_int is not None:
            dup = db.scalars(select(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.source == body.source,
                AffairsRiskRecord.source_ref_id == ref_int,
                AffairsRiskRecord.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", "该来源单据已建风险记录，不可重复")
        x = AffairsRiskRecord(tenant_id=_tid(), student_id=s.id, source=body.source,
                              source_ref_id=ref_int,
                              risk_level=(body.riskLevel or "MEDIUM"), title=getattr(body, "title", None),
                              detail=getattr(body, "detail", None), status="NEW")
        db.add(x)
        db.flush()
        _audit(db, x.id, "CREATE", body.source)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


def assign(risk_id, user, owner_id, expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        to_status = _transition_or_conflict(x, "ASSIGN")
        atomic_claim_version(db, x, expected_version)
        valid_owner_id = _validate_owner(db, owner_id, x.student_id)
        frm = x.status
        x.owner_id, x.status, x.assigned_at, x.escalated_at, x.version = \
            valid_owner_id, to_status, datetime.utcnow(), None, x.version + 1
        _handle(db, x.id, "ASSIGN", f"分派责任人 {valid_owner_id}", frm, to_status)
        _todo_upsert(db, x.id, valid_owner_id, x.student_id, f"风险待处置：{s.real_name if s else ''}")
        _msg(db, valid_owner_id, "风险待处置", f"有一条{x.risk_level}风险待你处置", "RISK_ALERT", x.id)
        _audit(db, x.id, "ASSIGN", str(valid_owner_id))
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        from app.models import User
        owner = db.get(User, int(x.owner_id)) if x.owner_id else None
        return _row(x, user, s, owner=owner)


# ═══════════ 处置 ═══════════

def process(risk_id, user, content="", expected_version=None) -> dict:
    if not content or len(content.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处置记录必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_owner_or_admin(db, x, user, label="填写处置")
        to_status = _transition_or_conflict(x, "PROCESS")
        atomic_claim_version(db, x, expected_version)
        frm = x.status
        x.status, x.version = to_status, x.version + 1
        _handle(db, x.id, "PROCESS", content.strip(), frm, to_status)
        _audit(db, x.id, "PROCESS")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


def follow(risk_id, user, content="", expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_owner_or_admin(db, x, user, label="转跟进")
        to_status = _transition_or_conflict(x, "FOLLOW")
        atomic_claim_version(db, x, expected_version)
        frm = x.status
        x.status, x.version = to_status, x.version + 1
        _handle(db, x.id, "FOLLOW", (content or "").strip(), frm, to_status)
        _audit(db, x.id, "FOLLOW")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


def transfer(risk_id, user, new_owner_id, reason="", expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_owner_or_admin(db, x, user, label="转办")
        to_status = _transition_or_conflict(x, "TRANSFER")
        atomic_claim_version(db, x, expected_version)
        valid_owner_id = _validate_owner(db, new_owner_id, x.student_id)
        frm = x.status
        _handle(db, x.id, "TRANSFER", f"转办：{reason}", frm, to_status)
        x.owner_id, x.status, x.assigned_at, x.version = \
            valid_owner_id, to_status, datetime.utcnow(), x.version + 1
        _todo_upsert(db, x.id, valid_owner_id, x.student_id, f"风险转办待处置：{s.real_name if s else ''}")
        _msg(db, valid_owner_id, "风险转办", reason or "有风险转办给你", "RISK_ALERT", x.id)
        _audit(db, x.id, "TRANSFER", str(valid_owner_id))
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


_LEVEL_UP = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "CRITICAL", "CRITICAL": "CRITICAL"}


def escalate(risk_id, user, reason="", expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_owner_or_admin(db, x, user, label="升级")
        to_status = _transition_or_conflict(x, "ESCALATE")
        atomic_claim_version(db, x, expected_version)
        frm = x.status
        x.risk_level = _LEVEL_UP.get(x.risk_level, x.risk_level)
        x.status, x.escalated_at, x.version = to_status, datetime.utcnow(), x.version + 1
        _handle(db, x.id, "ESCALATE", f"升级：{reason}", frm, to_status)
        _notify_risk_handlers(db, x, "风险升级",
                              f"风险#{x.id} 已升级至 {x.risk_level}" + (f"：{reason}" if reason else ""))
        _audit(db, x.id, "ESCALATE", x.risk_level)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


def takeover(risk_id, user, content="", expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_takeover_authority(db, user)
        to_status = _transition_or_conflict(x, "TAKEOVER")
        atomic_claim_version(db, x, expected_version)
        frm = x.status
        uid = _uid_int(user)
        x.status, x.version = to_status, x.version + 1
        if uid:
            x.owner_id = uid  # 接管后责任人改为接管人
            _todo_upsert(db, x.id, uid, x.student_id, f"风险已接管待处置：{s.real_name if s else ''}")
        _handle(db, x.id, "TAKEOVER", (content or "上级接管").strip(), frm, to_status)
        _audit(db, x.id, "TAKEOVER")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


def close(risk_id, user, conclusion="", expected_version=None) -> dict:
    if not conclusion or len(conclusion.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭结论必填且不少于 5 字")
    with session() as db:
        from app.models import StudentStageEvent
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_owner_or_admin(db, x, user, label="关闭")
        to_status = _transition_or_conflict(x, "CLOSE")
        atomic_claim_version(db, x, expected_version)
        if _handle_count(db, x.id) == 0:
            raise AppException("DATA_CONFLICT", "关闭前须至少一条处置记录")
        frm = x.status
        x.status, x.closed_reason, x.version = to_status, conclusion.strip(), x.version + 1
        _handle(db, x.id, "CLOSE", conclusion.strip(), frm, to_status)
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                 to_stage="RISK_CLOSED", reason=f"风险处置关闭（{x.source}）",
                                 source_module="student-affairs"))
        _todo_done(db, x.id)
        _msg(db, x.student_id, "风险已关闭", "相关风险已处置关闭", "STATUS_CHANGED", x.id)
        _audit(db, x.id, "CLOSE")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


def reopen(risk_id, user, reason="", expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        _require_takeover_authority(db, user)  # 重开属上级动作，防同班互改
        to_status = _transition_or_conflict(x, "REOPEN")
        atomic_claim_version(db, x, expected_version)
        x.status, x.version = to_status, x.version + 1
        _handle(db, x.id, "REOPEN", (reason or "复发重开").strip(), "CLOSED", to_status)
        _msg(db, x.owner_id, "风险重开", reason or "风险复发已重开", "RISK_ALERT", x.id)
        _audit(db, x.id, "REOPEN")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, user, s)


# ═══════════ 超时扫描（幂等） ═══════════

def scan_timeout() -> dict:
    """按当前配置自动分派 NEW 风险，并升级超时未处置的 ASSIGNED 风险。"""
    from app.models import AffairsRiskRecord, SchoolClass, StudentProfile
    now = datetime.utcnow()
    with session() as db:
        assigned = 0
        # NEW 超过分派时限未分派 → 尝试分给班级辅导员
        new_rows = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.status == "NEW",
            AffairsRiskRecord.created_at.is_not(None),
            AffairsRiskRecord.is_deleted.is_(False))).all()
        eligible_owners = _owner_role_user_ids(db)
        for x in new_rows:
            if not x.created_at or not risk_is_overdue(x, now):
                continue
            counselor_id = None
            if x.student_id:
                s = db.get(StudentProfile, int(x.student_id))
                if s and s.class_id:
                    c = db.get(SchoolClass, int(s.class_id))
                    if c and c.counselor_id and int(c.counselor_id) in eligible_owners:
                        counselor_id = int(c.counselor_id)
            if not counselor_id:
                continue
            x.owner_id, x.status, x.assigned_at, x.version = \
                counselor_id, "ASSIGNED", now, x.version + 1
            _handle(db, x.id, "ASSIGN", f"超时自动分派辅导员 {counselor_id}", "NEW", "ASSIGNED")
            _todo_upsert(db, x.id, counselor_id, x.student_id, "风险待处置（超时自动分派）")
            _msg(db, counselor_id, "风险待处置", f"风险#{x.id} 已超时自动分派给你", "RISK_ALERT", x.id)
            _audit(db, x.id, "AUTO_ASSIGN", str(counselor_id))
            assigned += 1

        # 处置/跟进超时：ASSIGNED/PROCESSING/FOLLOWING 超阶段时限且未升级过 → ESCALATED
        rows = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(),
            AffairsRiskRecord.status.in_(("ASSIGNED", "PROCESSING", "FOLLOWING")),
            AffairsRiskRecord.escalated_at.is_(None),
            AffairsRiskRecord.is_deleted.is_(False))).all()
        escalated = 0
        for x in rows:
            if risk_is_overdue(x, now):
                frm = x.status
                x.risk_level = _LEVEL_UP.get(x.risk_level, x.risk_level)
                x.status, x.escalated_at, x.version = "ESCALATED", now, x.version + 1
                _handle(db, x.id, "ESCALATE", "处置/跟进超时自动升级", frm, "ESCALATED")
                _notify_risk_handlers(db, x, "风险处置超时升级",
                                      f"风险#{x.id} 处置超时已自动升级至 {x.risk_level}")
                _audit(db, x.id, "AUTO_ESCALATE")
                escalated += 1
        db.commit()
        _drain_message_outbox()
        return {"escalated": escalated, "assigned": assigned}


# ═══════════ 查询 ═══════════

def _allowed_risk_actions(x, user) -> list[str]:
    """严格按状态机、权限和责任关系计算；不得比写服务更宽。"""
    from app.core.affairs_security import build_affairs_context

    is_owner = bool(x.owner_id) and _uid_norm(x.owner_id) == _uid_norm(user)
    ctx = build_affairs_context(user, None)
    is_admin = ctx.scope_type == "TENANT_ALL"
    role = (user or {}).get("currentRoleCode") or ""
    is_superior = is_admin or role in (
        "COLLEGE_ADMIN", "COLLEGE_SA", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SCHOOL_ADMIN"
    )
    actions: list[str] = []
    for action, rule in RISK_TRANSITIONS.items():
        if x.status not in rule["from"] or not has_permission(user, rule["permission"]):
            continue
        relationship = rule.get("relationship")
        if relationship == "OWNER_OR_ADMIN" and not (is_owner or is_admin):
            continue
        if relationship == "SUPERIOR" and not is_superior:
            continue
        actions.append(action)
    return actions


def list_handles(risk_id, user) -> list[dict]:
    """真实处置留痕（append-only）。心理来源内容按角色脱敏。"""
    from app.models import AffairsRiskHandle
    with session() as db:
        x, _s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        rows = db.scalars(select(AffairsRiskHandle).where(
            AffairsRiskHandle.tenant_id == _tid(),
            AffairsRiskHandle.risk_id == int(risk_id),
            AffairsRiskHandle.is_deleted.is_(False),
        ).order_by(AffairsRiskHandle.id.asc())).all()
        mental_mask = x.source == "MENTAL" and not _can_view_mental(user)
        out = []
        for h in rows:
            content = h.content or ""
            if mental_mask and content:
                content = "[心理关注·处置内容已脱敏]"
            out.append({
                "handleId": str(h.id),
                "action": h.action,
                "operator": h.operator or "",
                "fromStatus": h.from_status or "",
                "toStatus": h.to_status or "",
                "content": content,
                "occurredAt": _iso(getattr(h, "created_at", None)),
            })
        return out


def get_risk(risk_id, user, reason: str | None = None) -> dict:
    with session() as db:
        from app.models import User
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        reveal = False
        # 心理来源明细=敏感：仅授权角色 + 填写原因(≥5字) 方可查看明文，并写 SENSITIVE_VIEW 审计；
        # 审计必须先成功，再 reveal（强敏感不可吞异常后仍返明文）。
        if x.source == "MENTAL" and _can_view_mental(user):
            if reason and len(str(reason).strip()) >= 5:
                _sensitive_view_audit(x, reason.strip())
                reveal = True
        owner = db.get(User, int(x.owner_id)) if x.owner_id else None
        row = _row(x, user, s, reveal=reveal, owner=owner)
        row["allowedActions"] = _allowed_risk_actions(x, user)
    # 独立会话拉 handles，避免与详情会话交叉
    row["handles"] = list_handles(risk_id, user)
    return row


def _risk_filter_conds(source=None, status=None, risk_level=None, student_id=None):
    """列表 / count / 聚合共用过滤条件（不含数据范围）。"""
    from app.models import AffairsRiskRecord
    conds = [AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.is_deleted.is_(False)]
    if source:
        conds.append(AffairsRiskRecord.source == source)
    if status == "OPEN":
        conds.append(AffairsRiskRecord.status.notin_(["CLOSED"]))
    elif status == "PENDING":
        conds.append(AffairsRiskRecord.status.in_(
            ["NEW", "ASSIGNED", "REOPENED", "TRANSFERRED"]))
    elif status:
        conds.append(AffairsRiskRecord.status == status)
    if risk_level:
        conds.append(AffairsRiskRecord.risk_level == risk_level)
    if student_id:
        conds.append(AffairsRiskRecord.student_id == int(student_id))
    return conds


def _risk_scope_join(stmt, allowed):
    """按班级数据范围 join 学生表。allowed=None 表示 TENANT_ALL。"""
    from app.models import AffairsRiskRecord, StudentProfile
    stmt = stmt.join(StudentProfile, StudentProfile.id == AffairsRiskRecord.student_id)
    if allowed is not None:
        stmt = stmt.where(StudentProfile.class_id.in_(allowed or {-1}))
    return stmt


def _risk_stats_sql(db, base_conds, allowed) -> dict:
    """与列表同过滤/同范围的单次 SQL 条件聚合；超时阈值与 scan_timeout 共用配置。"""
    from sqlalchemy import case
    from app.models import AffairsRiskRecord

    now = datetime.utcnow()
    overdue_pred = AffairsRiskRecord.status == "ESCALATED"
    for level in LEVELS:
        sla = get_risk_sla(level)
        overdue_pred |= (
            (AffairsRiskRecord.risk_level == level)
            & (
                ((AffairsRiskRecord.status == "NEW")
                 & AffairsRiskRecord.created_at.is_not(None)
                 & (AffairsRiskRecord.created_at <= now - timedelta(hours=sla["assignHours"])))
                | ((AffairsRiskRecord.status == "ASSIGNED")
                   & AffairsRiskRecord.assigned_at.is_not(None)
                   & (AffairsRiskRecord.assigned_at <= now - timedelta(hours=sla["processHours"])))
                | ((AffairsRiskRecord.status.in_(("PROCESSING", "FOLLOWING")))
                   & (
                       (AffairsRiskRecord.updated_at.is_not(None)
                        & (AffairsRiskRecord.updated_at
                           <= now - timedelta(hours=sla["followHours"])))
                       | (AffairsRiskRecord.updated_at.is_(None)
                          & AffairsRiskRecord.assigned_at.is_not(None)
                          & (AffairsRiskRecord.assigned_at
                             <= now - timedelta(hours=sla["followHours"])))
                   ))
            )
        )
    stmt = _risk_scope_join(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(case(
                (AffairsRiskRecord.risk_level.in_(["HIGH", "CRITICAL"]), 1), else_=0)), 0).label("high_critical"),
            func.coalesce(func.sum(case(
                (AffairsRiskRecord.status.notin_(["CLOSED"]), 1), else_=0)), 0).label("open_n"),
            func.coalesce(func.sum(case(
                (AffairsRiskRecord.owner_id.is_(None), 1), else_=0)), 0).label("unassigned"),
            func.coalesce(func.sum(case((overdue_pred, 1), else_=0)), 0).label("overdue"),
        ).select_from(AffairsRiskRecord).where(*base_conds),
        allowed,
    )
    row = db.execute(stmt).one()
    return {
        "total": int(row.total or 0),
        "highCritical": int(row.high_critical or 0),
        "open": int(row.open_n or 0),
        "unassigned": int(row.unassigned or 0),
        "overdue": int(row.overdue or 0),
    }


def list_risks(user, source=None, status=None, risk_level=None, student_id=None,
               page=1, page_size=20):
    from app.core.pagination import normalize_page
    from app.models import AffairsRiskRecord, StudentProfile, User
    from app.services.affairs_dashboard_service import _allowed_class_ids
    page, page_size = normalize_page(page, page_size)
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = _risk_filter_conds(source, status, risk_level, student_id)
        stats = _risk_stats_sql(db, base_conds, allowed)
        total = stats["total"]
        id_stmt = _risk_scope_join(
            select(AffairsRiskRecord.id).where(*base_conds), allowed
        ).order_by(AffairsRiskRecord.id.desc()).offset((page - 1) * page_size).limit(page_size)
        page_ids = list(db.scalars(id_stmt).all())
        if not page_ids:
            return [], total, stats
        rows = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.id.in_(page_ids)).order_by(AffairsRiskRecord.id.desc())).all()
        # 消 N+1：仅对本页批量取学生 / 责任人
        sids = {int(x.student_id) for x in rows if x.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        oids = {int(x.owner_id) for x in rows if x.owner_id}
        owners = {u.id: u for u in db.scalars(select(User).where(
            User.id.in_(oids))).all()} if oids else {}
        out = [
            _row(x, user, students.get(int(x.student_id)) if x.student_id else None,
                 owner=owners.get(int(x.owner_id)) if x.owner_id else None)
            for x in rows
        ]
        return out, total, stats


_SCAN_ROLES = {"SCHOOL_ADMIN", "SCHOOL_LEADER", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN",
               "PLATFORM_SUPER_ADMIN"}


def require_scan_authority(user) -> None:
    """超时扫描仅校级/学工管理角色；普通辅导员不可触发。"""
    role = ((user or {}).get("currentRoleCode") or "").upper()
    if role not in _SCAN_ROLES:
        raise AppException("NO_PERMISSION", "仅学工管理员或校级管理可执行超时扫描")
