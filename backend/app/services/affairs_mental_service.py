"""13A-D 心理关注服务（强敏感红线）。

红线（权限总控 §7.3/§10.2、13A §13 心理行）：
- 心理明细(note/counselorNote)最小暴露：列表恒仅返回摘要+"需关注"标记，明细遮蔽；
- 查看明细须"授权角色 + 填写原因(≥5字)"，并写 t_security_audit_log(SENSITIVE_VIEW)；
- 数据范围=PSY_STUDENT 逐生授权（t_teacher_student_scope, scope_type=PSY_STUDENT, ref_value=学号）；
- STUDENT_AFFAIRS_ADMIN 默认不得查看心理原始明细（除非专项授权）；
- 危机升级复用风险中枢（source=MENTAL），本表 risk_id 回链；
- 系统不做任何自动诊断：等级/事由均人工登记。
业务流转 → t_affairs_audit_trail；敏感明细查看 → t_security_audit_log(SENSITIVE_VIEW)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.pagination import normalize_page
from app.services.db_service import _iso, _tid, session

# 明细可见角色（按角色）：心理老师 + 校/平台超管（超管查看仍须原因+审计）。
# STUDENT_AFFAIRS_ADMIN 不在此列（SEC-2）；辅导员/班主任须经 PSY_STUDENT 逐生授权。
_PSY_DETAIL_ROLES = {"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}
_PSY_SCOPE_ROLES = {"COUNSELOR", "CLASS_ADVISOR", "PSYCHOLOGY_TEACHER"}
L_REF = {"REFERRED": "已转介", "FOLLOWING": "回访中", "ESCALATED": "已升级危机", "CLOSED": "已关闭"}
L_LEVEL = {"GENERAL": "一般关注", "FOCUS": "重点关注", "CRISIS": "危机"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _biz_audit(db, biz_id, action, detail=""):
    """业务流转留痕 → t_affairs_audit_trail。"""
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="PSY_REFERRAL",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _sensitive_view_audit(student_id, reason: str, resource: str) -> None:
    """心理明细查看 → t_security_audit_log(SENSITIVE_VIEW)。审计绝不阻塞主流程。"""
    try:
        from app.services import audit_log
        audit_log.record("SENSITIVE_VIEW", resource,
                         detail={"domain": "MENTAL", "studentId": str(student_id),
                                 "reason": str(reason)[:200]}, result="SUCCESS")
    except Exception:  # noqa: BLE001
        pass


def psy_scope_ids(db, user):
    """PSY_STUDENT 逐生授权学生 ID 集。None=按角色全可见（校/平台超管）；set()=无授权学生。
    键派生与 resolve_teacher_scope 一致：mock u_psych01→psych01 / ctx_<login> / 姓名兜底；teacher_key 或 teacher_name 命中即生效。"""
    from app.core.permissions import is_super_admin
    from app.models import StudentProfile, TeacherStudentScope
    u = user or {}
    role = (u.get("currentRoleCode") or "")
    if is_super_admin(user) or role in ("SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"):
        return None
    uid = str(u.get("userId") or "")
    ctx = str(u.get("activeContextId") or "")
    name = u.get("realName") or ""
    keys = {k for k in (uid, uid[2:] if uid.startswith("u_") else "",
                        ctx[4:] if ctx.startswith("ctx_") else "", name) if k}
    rows = db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == _tid(),
        TeacherStudentScope.scope_type == "PSY_STUDENT",
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
        (TeacherStudentScope.teacher_key.in_(keys)) |
        (TeacherStudentScope.teacher_name.in_(keys)))).all()
    rows = [r for r in rows if not r.role_code or (r.role_code or "").upper() == role.upper()]
    nos = {r.ref_value for r in rows if r.ref_value}
    if not nos:
        return set()
    studs = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.student_no.in_(nos))).all()
    return {s.id for s in studs}


def _can_view_detail(user, student_id, scope_ids) -> bool:
    """能否查看该生心理明细：校/平台超管 + 心理老师(限授权) + PSY_STUDENT 授权者。SEC-2：学工处管理员不在此列。"""
    role = (user or {}).get("currentRoleCode") or ""
    if role in ("SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"):
        return True
    if scope_ids is None:
        return role in _PSY_DETAIL_ROLES
    return int(student_id) in scope_ids


def _load(db, ref_id):
    from app.models import PsyReferral
    x = db.get(PsyReferral, int(ref_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("心理转介记录不存在")
    return x


def _stu(db, sid):
    from app.models import StudentProfile
    return db.get(StudentProfile, int(sid)) if sid else None


def _scope_or_403(user, scope_ids, student_id):
    if scope_ids is not None and int(student_id) not in scope_ids:
        raise AppException("NO_DATA_SCOPE", "该学生不在您的心理授权范围内")


def _ref_row(x, s, reveal) -> dict:
    return {
        "referralId": str(x.id), "studentId": str(x.student_id),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "level": x.level, "levelLabel": L_LEVEL.get(x.level, x.level),
        "channel": x.channel or "", "reasonSummary": x.reason_summary or "",
        "note": (x.note or "") if reveal else "[心理明细·受限，需授权+原因查看]",
        "noteMasked": not reveal,
        "referrer": x.referrer or "", "status": x.status, "statusLabel": L_REF.get(x.status, x.status),
        "lastFollowTime": _iso(x.last_follow_time) or "", "riskId": str(x.risk_id or ""),
        "version": x.version,
    }


# ═══════════ 名单 / 摘要 ═══════════

def list_attention(user, reason=None, level=None, page=1, page_size=20):
    """心理关注名单：PSY_STUDENT 数据范围过滤；列表恒仅摘要，note 明细遮蔽（reveal 仅在明细端点带原因）。"""
    from app.models import PsyReferral, StudentProfile
    with session() as db:
        scope = psy_scope_ids(db, user)
        conds = [PsyReferral.tenant_id == _tid(), PsyReferral.is_deleted.is_(False)]
        if level:
            conds.append(PsyReferral.level == level)
        if scope is not None:
            conds.append(PsyReferral.student_id.in_(scope or {-1}))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(PsyReferral).where(*conds)) or 0)
        rows = db.scalars(select(PsyReferral).where(*conds).order_by(PsyReferral.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_({int(x.student_id) for x in rows if x.student_id})
        )).all()} if rows else {}
        return [_ref_row(x, students.get(int(x.student_id)), reveal=False) for x in rows], total


def get_referral(user, ref_id, reason=None) -> dict:
    """转介详情：授权角色 + 原因(≥5字) 方 reveal 明细，并写 SENSITIVE_VIEW。"""
    with session() as db:
        x = _load(db, ref_id)
        scope = psy_scope_ids(db, user)
        _scope_or_403(user, scope, x.student_id)
        reveal = False
        if _can_view_detail(user, x.student_id, scope) and reason and len(str(reason).strip()) >= 5:
            reveal = True
            _sensitive_view_audit(x.student_id, reason.strip(), f"psy_referral:{x.id}")
        return _ref_row(x, _stu(db, x.student_id), reveal=reveal)


def student_summary(user, student_id) -> dict:
    """心理预警摘要：仅"需关注"标记 + 风险等级摘要，不含任何明细（供非心理角色/画像消费）。
    虽无明细，仍按调用者数据范围收敛：越租户→not_found、越范围→403002（心理老师仅授权 PSY_STUDENT）。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import AffairsRiskRecord, PsyReferral
    with session() as db:
        s = build_affairs_context(user, db).require_student(db, student_id)
        refs = db.scalars(select(PsyReferral).where(
            PsyReferral.tenant_id == _tid(), PsyReferral.student_id == int(student_id),
            PsyReferral.is_deleted.is_(False))).all()
        active = [r for r in refs if r.status != "CLOSED"]
        risks = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.student_id == int(student_id),
            AffairsRiskRecord.source == "MENTAL", AffairsRiskRecord.is_deleted.is_(False))).all()
        open_risk = [r for r in risks if r.status != "CLOSED"]
        top = ""
        if active:
            _LEVEL_ORDER = {"GENERAL": 1, "FOCUS": 2, "CRISIS": 3}
            top = max(active, key=lambda r: _LEVEL_ORDER.get(r.level, 0)).level
        return {
            "studentId": str(student_id), "needAttention": bool(active),
            "attentionLevel": top, "attentionLabel": L_LEVEL.get(top, ""),
            "openReferralCount": len(active), "openCrisisRiskCount": len(open_risk),
            # 摘要绝不含 note/明细
        }


# ═══════════ 转介 → 回访 → 升级/关闭 状态闭环 ═══════════

def create_referral(user, body) -> dict:
    """登记心理转介（人工，无自动诊断）。"""
    level = (getattr(body, "level", None) or "FOCUS")
    if level not in ("GENERAL", "FOCUS", "CRISIS"):
        raise AppException("VALIDATION_ERROR", "关注等级非法")
    reason_summary = (getattr(body, "reasonSummary", None) or "").strip()
    if len(reason_summary) < 5:
        raise AppException("VALIDATION_ERROR", "转介事由摘要必填且不少于 5 字")
    with session() as db:
        from app.models import PsyReferral
        s = _stu(db, getattr(body, "studentId", None))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        scope = psy_scope_ids(db, user)
        _scope_or_403(user, scope, s.id)
        n, _r, _u = _op()
        x = PsyReferral(tenant_id=_tid(), student_id=s.id, level=level,
                        channel=(getattr(body, "channel", None) or None),
                        reason_summary=reason_summary, note=(getattr(body, "note", None) or None),
                        referrer=n, status="REFERRED")
        db.add(x); db.flush()
        _biz_audit(db, x.id, "REFER", f"level={level}")
        db.commit(); db.refresh(x)
        return _ref_row(x, s, reveal=True)  # 登记人当次可见自填明细


def follow_referral(user, ref_id, content="", expected_version=None) -> dict:
    """回访（→FOLLOWING，记录回访时间）。"""
    if not content or len(content.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "回访记录必填且不少于 5 字")
    with session() as db:
        x = _load(db, ref_id)
        _scope_or_403(user, psy_scope_ids(db, user), x.student_id)
        if x.status not in ("REFERRED", "FOLLOWING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可回访")
        check_version(x.version, expected_version)
        x.status, x.last_follow_time, x.version = "FOLLOWING", datetime.utcnow(), x.version + 1
        _biz_audit(db, x.id, "FOLLOW", content.strip()[:100])
        db.commit(); db.refresh(x)
        return _ref_row(x, _stu(db, x.student_id), reveal=True)


def escalate_crisis(user, ref_id, content="", expected_version=None) -> dict:
    """危机升级 → 接入风险中枢（建 source=MENTAL 风险记录，去重于 (MENTAL, referral_id)），回链 risk_id。"""
    with session() as db:
        from app.models import AffairsRiskRecord
        x = _load(db, ref_id)
        _scope_or_403(user, psy_scope_ids(db, user), x.student_id)
        if x.status == "CLOSED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "已关闭的转介不可升级")
        # 幂等：同一转介只挂一条危机风险
        if x.risk_id:
            db.refresh(x)
            return _ref_row(x, _stu(db, x.student_id), reveal=True)
        check_version(x.version, expected_version)
        r = AffairsRiskRecord(tenant_id=_tid(), student_id=int(x.student_id), source="MENTAL",
                              source_ref_id=int(x.id), risk_level="CRITICAL",
                              title="心理危机升级", detail="[心理危机·明细受限]", status="NEW")
        db.add(r); db.flush()
        x.status, x.level, x.risk_id, x.version = "ESCALATED", "CRISIS", r.id, x.version + 1
        _biz_audit(db, x.id, "ESCALATE_CRISIS", f"risk_id={r.id}; {content.strip()[:80]}")
        db.commit(); db.refresh(x)
        return _ref_row(x, _stu(db, x.student_id), reveal=True)


def close_referral(user, ref_id, conclusion="", expected_version=None) -> dict:
    """关闭（结论≥5字）。"""
    if not conclusion or len(conclusion.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭结论必填且不少于 5 字")
    with session() as db:
        x = _load(db, ref_id)
        _scope_or_403(user, psy_scope_ids(db, user), x.student_id)
        if x.status == "CLOSED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该转介已关闭")
        check_version(x.version, expected_version)
        x.status, x.closed_reason, x.version = "CLOSED", conclusion.strip(), x.version + 1
        _biz_audit(db, x.id, "CLOSE", conclusion.strip()[:100])
        db.commit(); db.refresh(x)
        return _ref_row(x, _stu(db, x.student_id), reveal=True)


# ═══════════ 统计（仅聚合，禁个体明细外泄） ═══════════

def stats(user) -> dict:
    from app.models import PsyReferral
    with session() as db:
        scope = psy_scope_ids(db, user)
        rows = db.scalars(select(PsyReferral).where(
            PsyReferral.tenant_id == _tid(), PsyReferral.is_deleted.is_(False))).all()
        if scope is not None:
            rows = [r for r in rows if int(r.student_id) in scope]
        by_status, by_level = {}, {}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_level[r.level] = by_level.get(r.level, 0) + 1
        return {"total": len(rows), "byStatus": by_status, "byLevel": by_level,
                "openCrisis": sum(1 for r in rows if r.level == "CRISIS" and r.status != "CLOSED")}
