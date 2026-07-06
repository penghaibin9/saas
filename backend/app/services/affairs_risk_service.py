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
_MENTAL_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "PSYCHOLOGY_TEACHER", "ADMIN"}

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


def _row(x, user, s=None) -> dict:
    mental_masked = (x.source == "MENTAL" and not _can_view_mental(user))
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
    with session() as db:
        from app.models import AffairsRiskRecord, StudentProfile
        s = db.get(StudentProfile, int(body.studentId))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        _scope_or_403(db, s.id, user)
        ref = getattr(body, "sourceRefId", None)
        # (source, source_ref_id) 唯一防重复建单 → 409
        if ref:
            dup = db.scalars(select(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.source == body.source,
                AffairsRiskRecord.source_ref_id == int(ref),
                AffairsRiskRecord.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", "该来源单据已建风险记录，不可重复")
        x = AffairsRiskRecord(tenant_id=_tid(), student_id=s.id, source=body.source,
                              source_ref_id=(int(ref) if ref else None),
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
        frm = x.status
        x.owner_id, x.status, x.assigned_at, x.escalated_at, x.version = \
            int(owner_id or 0), "ASSIGNED", datetime.utcnow(), None, x.version + 1
        _handle(db, x.id, "ASSIGN", f"分派责任人 {owner_id}", frm, "ASSIGNED")
        _todo_upsert(db, x.id, owner_id, x.student_id, f"风险待处置：{s.real_name if s else ''}")
        _msg(db, owner_id, "风险待处置", f"有一条{x.risk_level}风险待你处置", "RISK_ALERT", x.id)
        _audit(db, x.id, "ASSIGN", str(owner_id))
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
        frm = x.status
        _handle(db, x.id, "TRANSFER", f"转办：{reason}", frm, "ASSIGNED")
        x.owner_id, x.status, x.assigned_at, x.version = \
            int(new_owner_id or 0), "ASSIGNED", datetime.utcnow(), x.version + 1
        _todo_upsert(db, x.id, new_owner_id, x.student_id, f"风险转办待处置：{s.real_name if s else ''}")
        _msg(db, new_owner_id, "风险转办", reason or "有风险转办给你", "RISK_ALERT", x.id)
        _audit(db, x.id, "TRANSFER", str(new_owner_id))
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

def get_risk(risk_id, user) -> dict:
    with session() as db:
        x, s = _load(db, risk_id)
        _scope_or_403(db, x.student_id, user)
        return _row(x, user, s)


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
        out = []
        for x in rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_row(x, user, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
