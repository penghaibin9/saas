"""13A-P4 风险预警中枢（8 态，处置类不走审批·时效优先，全动作落 handle_record 留痕）。

多来源引用（不复制来源数据），(source, source_ref_id) 唯一防重复建单。
NEW→ASSIGNED→PROCESSING→(FOLLOWING)→CLOSED；转办/升级/接管/重开；超时扫描(分派/升级)幂等。
心理(MENTAL)来源明细仅授权角色可见，普通教师仅见"需关注"标记。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

SOURCES = ("LEAVE_OVERDUE", "ACADEMIC_WARNING", "DORM", "MENTAL", "DISCIPLINE", "INTERNSHIP",
           "GRADUATION_DESIGN", "EMPLOYMENT", "FAMILY", "MANUAL")
LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
# SEC-2 修复：学工处管理员(STUDENT_AFFAIRS_ADMIN)默认不得查看心理原始明细（权限总控 §7.3 /
# 13A §13 心理行）；需专项授权(PSY_STUDENT，见心理关注模块)方可。此处仅按角色保留心理老师与
# 校/平台超管（超管查看心理明细仍强制填写原因 + 写 SENSITIVE_VIEW 审计，见 get_risk）。
_MENTAL_ROLES = {"SCHOOL_ADMIN", "PSYCHOLOGY_TEACHER", "PLATFORM_SUPER_ADMIN", "ADMIN"}

# 风险责任人候选角色：分派后会给 owner 建待办(_todo_upsert)+发站内信(_msg)，owner 打开待办必须
# 能真正处置，即必须持有 studentAffairs.risk.*（见 app/core/permissions.py ROLE_PERMISSIONS）。
# 分派给任课教师等无该权限的账号会让待办变成点开即 403 的死信，故按角色码收敛候选集。
OWNER_ROLE_CODES = ("COUNSELOR", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN",
                    "PSYCHOLOGY_TEACHER", "COLLEGE_ADMIN", "SCHOOL_ADMIN")


def _owner_role_user_ids(db) -> set[int]:
    """持有学工风险处置角色、且角色与授权本身有效的账号 id 集合。"""
    from app.models import Role, UserRole
    rows = db.scalars(select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
        UserRole.tenant_id == _tid(), UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE",
        Role.tenant_id == _tid(), Role.is_deleted.is_(False), Role.status == "ACTIVE",
        Role.role_code.in_(OWNER_ROLE_CODES))).all()
    return {int(v) for v in rows}


def list_owner_candidates(keyword: str | None = None) -> list[dict]:
    """可分派的风险责任人（在职 + 同租户 + 持处置角色）。供前端责任人选择器远程搜索。"""
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


def _validate_owner(db, owner_id) -> int:
    """责任人校验：必须是存在、同租户、在职、且持处置角色的真实账号（历史欠账收口，见 docs）。"""
    from app.models import User
    raw = str(owner_id or "").strip()
    if not raw or not raw.isdigit():
        raise AppException("VALIDATION_ERROR", "请选择有效责任人")
    u = db.get(User, int(raw))
    if not u or u.is_deleted or u.tenant_id != _tid() or u.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "责任人不存在或已停用")
    if u.id not in _owner_role_user_ids(db):
        raise AppException("VALIDATION_ERROR", "该账号无学工风险处置角色，不能作为责任人")
    return int(u.id)

L_RISK = {
    "NEW": "新建", "ASSIGNED": "已分派", "PROCESSING": "处置中", "FOLLOWING": "持续跟进",
    "TRANSFERRED": "已转办", "ESCALATED": "已升级", "CLOSED": "已关闭", "REOPENED": "已重开",
}


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
    from app.models import UnifiedMessage
    db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(receiver_id or 0),
                          source_module="student-affairs", source_biz_id=int(risk_id),
                          title=title, content=content, message_type=mtype, status="UNREAD"))


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


def _can_view_mental(user) -> bool:
    return (user or {}).get("currentRoleCode") in _MENTAL_ROLES


def _sensitive_view_audit(x, reason: str) -> None:
    """查看心理来源风险明细 → 写 t_security_audit_log(SENSITIVE_VIEW)。审计绝不阻塞主流程。"""
    try:
        from app.services import audit_log
        audit_log.record("SENSITIVE_VIEW", f"risk:{x.id}",
                         detail={"source": x.source, "studentId": str(x.student_id),
                                 "reason": str(reason)[:200]}, result="SUCCESS")
    except Exception:  # noqa: BLE001
        pass


def _row(x, user, s=None, reveal=False) -> dict:
    # 列表恒遮蔽心理明细（仅摘要）；明细页须经授权角色 + 填写原因，get_risk 内 reveal=True 且写 SENSITIVE_VIEW。
    mental_masked = (x.source == "MENTAL" and not (reveal and _can_view_mental(user)))
    return {
        "riskId": str(x.id), "studentId": str(x.student_id),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "source": x.source, "sourceRefId": str(x.source_ref_id or ""),
        "riskLevel": x.risk_level, "title": x.title or "",
        "detail": "[心理关注·明细受限]" if mental_masked else (x.detail or ""),
        "mentalMasked": mental_masked, "ownerId": str(x.owner_id or ""),
        "status": x.status, "statusLabel": L_RISK.get(x.status, x.status),
        "isArchived": bool(x.is_archived), "version": x.version,
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
        db.refresh(x)
        return _row(x, user, s)


def assign(risk_id, user, owner_id) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("NEW", "REOPENED", "TRANSFERRED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可分派")
        valid_owner_id = _validate_owner(db, owner_id)
        frm = x.status
        x.owner_id, x.status, x.assigned_at, x.escalated_at, x.version = \
            valid_owner_id, "ASSIGNED", datetime.utcnow(), None, x.version + 1
        _handle(db, x.id, "ASSIGN", f"分派责任人 {valid_owner_id}", frm, "ASSIGNED")
        _todo_upsert(db, x.id, valid_owner_id, x.student_id, f"风险待处置：{s.real_name if s else ''}")
        _msg(db, valid_owner_id, "风险待处置", f"有一条{x.risk_level}风险待你处置", "RISK_ALERT", x.id)
        _audit(db, x.id, "ASSIGN", str(valid_owner_id))
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


# ═══════════ 处置 ═══════════

def process(risk_id, user, content="") -> dict:
    if not content or len(content.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处置记录必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("ASSIGNED", "PROCESSING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可处置")
        frm = x.status
        x.status, x.version = "PROCESSING", x.version + 1
        _handle(db, x.id, "PROCESS", content.strip(), frm, "PROCESSING")
        _audit(db, x.id, "PROCESS")
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


def follow(risk_id, user, content="") -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("PROCESSING", "FOLLOWING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可转跟进")
        frm = x.status
        x.status, x.version = "FOLLOWING", x.version + 1
        _handle(db, x.id, "FOLLOW", (content or "").strip(), frm, "FOLLOWING")
        _audit(db, x.id, "FOLLOW")
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


def transfer(risk_id, user, new_owner_id, reason="") -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("PROCESSING", "FOLLOWING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可转办")
        valid_owner_id = _validate_owner(db, new_owner_id)
        frm = x.status
        _handle(db, x.id, "TRANSFER", f"转办：{reason}", frm, "ASSIGNED")
        x.owner_id, x.status, x.assigned_at, x.version = \
            valid_owner_id, "ASSIGNED", datetime.utcnow(), x.version + 1
        _todo_upsert(db, x.id, valid_owner_id, x.student_id, f"风险转办待处置：{s.real_name if s else ''}")
        _msg(db, valid_owner_id, "风险转办", reason or "有风险转办给你", "RISK_ALERT", x.id)
        _audit(db, x.id, "TRANSFER", str(valid_owner_id))
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


_LEVEL_UP = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "CRITICAL", "CRITICAL": "CRITICAL"}


def escalate(risk_id, user, reason="") -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("PROCESSING", "FOLLOWING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可升级")
        frm = x.status
        x.risk_level = _LEVEL_UP.get(x.risk_level, x.risk_level)
        x.status, x.escalated_at, x.version = "ESCALATED", datetime.utcnow(), x.version + 1
        _handle(db, x.id, "ESCALATE", f"升级：{reason}", frm, "ESCALATED")
        _msg(db, 0, "风险升级", f"{s.real_name if s else ''} 风险升级至 {x.risk_level}", "RISK_ALERT", x.id)
        _audit(db, x.id, "ESCALATE", x.risk_level)
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


def takeover(risk_id, user, content="") -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "ESCALATED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已升级的风险可接管")
        x.status, x.version = "PROCESSING", x.version + 1
        _handle(db, x.id, "TAKEOVER", (content or "上级接管").strip(), "ESCALATED", "PROCESSING")
        _audit(db, x.id, "TAKEOVER")
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


def close(risk_id, user, conclusion="") -> dict:
    if not conclusion or len(conclusion.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭结论必填且不少于 5 字")
    with session() as db:
        from app.models import StudentStageEvent
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("PROCESSING", "FOLLOWING", "ESCALATED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可关闭")
        if _handle_count(db, x.id) == 0:
            raise AppException("DATA_CONFLICT", "关闭前须至少一条处置记录")
        frm = x.status
        x.status, x.closed_reason, x.version = "CLOSED", conclusion.strip(), x.version + 1
        _handle(db, x.id, "CLOSE", conclusion.strip(), frm, "CLOSED")
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                 to_stage="RISK_CLOSED", reason=f"风险处置关闭（{x.source}）",
                                 source_module="student-affairs"))
        _todo_done(db, x.id)
        _msg(db, x.student_id, "风险已关闭", "相关风险已处置关闭", "STATUS_CHANGED", x.id)
        _audit(db, x.id, "CLOSE")
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


def reopen(risk_id, user, reason="") -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "CLOSED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已关闭的风险可重开")
        x.status, x.version = "REOPENED", x.version + 1
        _handle(db, x.id, "REOPEN", (reason or "复发重开").strip(), "CLOSED", "REOPENED")
        _msg(db, x.owner_id, "风险重开", reason or "风险复发已重开", "RISK_ALERT", x.id)
        _audit(db, x.id, "REOPEN")
        db.commit()
        db.refresh(x)
        return _row(x, user, s)


# ═══════════ 超时扫描（幂等） ═══════════

def scan_timeout() -> dict:
    """分派超时(NEW≥4h 自动分派占位) + 处置超时(ASSIGNED≥72h 自动升级)。幂等：escalated_at 标记。"""
    from app.models import AffairsRiskRecord
    now = datetime.utcnow()
    with session() as db:
        assigned = 0
        # 处置超时：ASSIGNED ≥72h 无处置且未升级过 → ESCALATED
        rows = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.status == "ASSIGNED",
            AffairsRiskRecord.assigned_at.is_not(None), AffairsRiskRecord.escalated_at.is_(None),
            AffairsRiskRecord.is_deleted.is_(False))).all()
        escalated = 0
        for x in rows:
            if x.assigned_at + timedelta(hours=72) <= now:
                x.risk_level = _LEVEL_UP.get(x.risk_level, x.risk_level)
                x.status, x.escalated_at, x.version = "ESCALATED", now, x.version + 1
                _handle(db, x.id, "ESCALATE", "处置超时自动升级", "ASSIGNED", "ESCALATED")
                _msg(db, 0, "风险处置超时升级", f"风险 {x.id} 处置超时自动升级", "RISK_ALERT", x.id)
                _audit(db, x.id, "AUTO_ESCALATE")
                escalated += 1
        db.commit()
        return {"escalated": escalated, "assigned": assigned}


# ═══════════ 查询 ═══════════

def get_risk(risk_id, user, reason: str | None = None) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        reveal = False
        # 心理来源明细=敏感：仅授权角色 + 填写原因(≥5字) 方可查看明文，并写 SENSITIVE_VIEW 审计；
        # 无原因则返回遮蔽摘要（不报错，前端另起"查看明细"动作带原因）。
        if x.source == "MENTAL" and _can_view_mental(user):
            if reason and len(str(reason).strip()) >= 5:
                reveal = True
                _sensitive_view_audit(x, reason.strip())
        return _row(x, user, s, reveal=reveal)


def list_risks(user, source=None, status=None, risk_level=None, page=1, page_size=20):
    from app.models import AffairsRiskRecord, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.is_deleted.is_(False)]
        if source:
            conds.append(AffairsRiskRecord.source == source)
        if status:
            conds.append(AffairsRiskRecord.status == status)
        if risk_level:
            conds.append(AffairsRiskRecord.risk_level == risk_level)
        rows = db.scalars(select(AffairsRiskRecord).where(*conds).order_by(
            AffairsRiskRecord.id.desc())).all()
        # 消 N+1：一次批量取回本页涉及的学生档案，替代循环内逐行 db.get（历史欠账收口，
        # 行为等价——同样的行、同样的数据范围过滤、同样的顺序与内存分页，仅省掉 per-row 往返）。
        sids = {int(x.student_id) for x in rows if x.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        out = []
        for x in rows:
            s = students.get(int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_row(x, user, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
