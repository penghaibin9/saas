"""13A 奖助扩展服务：勤工助学 / 助学贷款 / 减免与临时补助。

金额按角色脱敏（复用 funding 的 _amount_view）；不落银行卡全号。留痕 AuditTrail(biz_type=FUNDING_EXT)。
数据范围复用 _allowed_class_ids（辅导员限本班）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.affairs_funding_service import _amount_view
from app.services.db_service import _iso, _tid, session


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), u.get("userId")


def _uid(user):
    try:
        return int((user or {}).get("userId") or 0) or None
    except (TypeError, ValueError):
        return None


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, _ = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="FUNDING_EXT",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _scoped_out(db, rows, user, sid_getter, row_fn):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    out = []
    for x in rows:
        s = db.get(StudentProfile, int(sid_getter(x))) if sid_getter(x) else None
        if allowed is not None and (not s or s.class_id not in allowed):
            continue
        out.append(row_fn(x, s))
    return out


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该学生不在您的数据范围内")


def _require_student(db, sid):
    from app.models import StudentProfile
    s = db.get(StudentProfile, int(sid)) if sid else None
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("学生不存在")
    return s


# ═══════════ 勤工助学 ═══════════

_L_WS = {"APPLIED": "待审核", "APPROVED": "已录用", "ONBOARD": "在岗", "REJECTED": "未录用", "TERMINATED": "已终止"}


def _post_row(p) -> dict:
    return {"postId": str(p.id), "deptName": p.dept_name, "postName": p.post_name,
            "salary": float(p.salary) if p.salary is not None else None, "headcount": p.headcount,
            "requirement": p.requirement or "", "status": p.status}


def list_posts(user, status=None):
    from app.models import WorkStudyPost
    with session() as db:
        conds = [WorkStudyPost.tenant_id == _tid(), WorkStudyPost.is_deleted.is_(False)]
        if status:
            conds.append(WorkStudyPost.status == status)
        rows = db.scalars(select(WorkStudyPost).where(*conds).order_by(WorkStudyPost.id.desc())).all()
        return [_post_row(p) for p in rows]


def create_post(body, user) -> dict:
    from app.models import WorkStudyPost
    dept = (getattr(body, "deptName", "") or "").strip()
    name = (getattr(body, "postName", "") or "").strip()
    if not dept or not name:
        raise AppException("VALIDATION_ERROR", "部门与岗位名称必填")
    with session() as db:
        p = WorkStudyPost(tenant_id=_tid(), dept_name=dept, post_name=name,
                          salary=getattr(body, "salary", None), headcount=getattr(body, "headcount", None),
                          requirement=getattr(body, "requirement", None), status="ENABLED", created_by=_uid(user))
        db.add(p); db.flush()
        _audit(db, p.id, "WS_POST_CREATE", name)
        db.commit(); db.refresh(p)
        return _post_row(p)


def _ws_row(r, s=None, user=None) -> dict:
    return {"recordId": str(r.id), "postId": str(r.post_id), "studentId": str(r.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "status": r.status, "statusLabel": _L_WS.get(r.status, r.status),
            "onboardAt": _iso(r.onboard_at), "subsidyTotal": _amount_view(r.subsidy_total, user or {}),
            "remark": r.remark or ""}


def list_ws_records(user, post_id=None, status=None):
    from app.models import WorkStudyRecord
    with session() as db:
        conds = [WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False)]
        if post_id:
            conds.append(WorkStudyRecord.post_id == int(post_id))
        if status:
            conds.append(WorkStudyRecord.status == status)
        rows = db.scalars(select(WorkStudyRecord).where(*conds).order_by(WorkStudyRecord.id.desc())).all()
        return _scoped_out(db, rows, user, lambda x: x.student_id, lambda x, s: _ws_row(x, s, user))


def apply_work_study(post_id, body, user) -> dict:
    from app.models import WorkStudyPost, WorkStudyRecord
    sid = int(getattr(body, "studentId", 0) or 0)
    with session() as db:
        p = db.get(WorkStudyPost, int(post_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("岗位不存在")
        if p.status != "ENABLED":
            raise AppException("DATA_CONFLICT", "岗位未开放")
        s = _require_student(db, sid)
        _scope_or_403(db, sid, user)
        dup = db.scalars(select(WorkStudyRecord).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.post_id == int(post_id),
            WorkStudyRecord.student_id == sid,
            WorkStudyRecord.status.in_(("APPLIED", "APPROVED", "ONBOARD")),
            WorkStudyRecord.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生已申请/在岗此岗位")
        r = WorkStudyRecord(tenant_id=_tid(), post_id=int(post_id), student_id=sid, status="APPLIED",
                            created_by=_uid(user))
        db.add(r); db.flush()
        _audit(db, r.id, "WS_APPLY", f"student={sid}")
        db.commit(); db.refresh(r)
        return _ws_row(r, s, user)


def _load_ws(db, rid):
    from app.models import WorkStudyRecord
    r = db.get(WorkStudyRecord, int(rid))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("上岗记录不存在")
    return r


def act_work_study(record_id, action, user, reason="") -> dict:
    """状态流转：APPROVE(APPLIED→APPROVED)/REJECT(APPLIED→REJECTED)/ONBOARD(APPROVED→ONBOARD)/
    TERMINATE(APPROVED|ONBOARD→TERMINATED)。"""
    from app.models import StudentProfile
    action = (action or "").upper()
    with session() as db:
        r = _load_ws(db, record_id)
        _scope_or_403(db, r.student_id, user)
        if action == "APPROVE":
            if r.status != "APPLIED":
                raise AppException("DATA_CONFLICT", "仅待审核可录用")
            r.status = "APPROVED"
        elif action == "REJECT":
            if r.status != "APPLIED":
                raise AppException("DATA_CONFLICT", "仅待审核可拒绝")
            r.status = "REJECTED"
        elif action == "ONBOARD":
            if r.status != "APPROVED":
                raise AppException("DATA_CONFLICT", "仅已录用可上岗")
            r.status, r.onboard_at = "ONBOARD", datetime.utcnow()
        elif action == "TERMINATE":
            if r.status not in ("APPROVED", "ONBOARD"):
                raise AppException("DATA_CONFLICT", "该记录不可终止")
            if len((reason or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "终止原因至少 5 字")
            r.status, r.terminated_at, r.remark = "TERMINATED", datetime.utcnow(), reason.strip()
        else:
            raise AppException("VALIDATION_ERROR", "动作非法")
        r.version += 1
        _audit(db, r.id, "WS_" + action, "")
        db.commit(); db.refresh(r)
        s = db.get(StudentProfile, int(r.student_id))
        return _ws_row(r, s, user)


# ═══════════ 助学贷款 ═══════════

_L_LOAN = {"REGISTERED": "已登记", "RECEIPT": "回执已传", "VERIFIED": "已核对", "CONFIRMED": "已确认"}
_LOAN_NEXT = {"REGISTERED": "RECEIPT", "RECEIPT": "VERIFIED", "VERIFIED": "CONFIRMED"}


def _loan_row(x, s=None, user=None) -> dict:
    return {"loanId": str(x.id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "loanType": x.loan_type, "bankName": x.bank_name or "",
            "bankLast4": x.bank_last4 or "", "yearCode": x.year_code or "",
            "amount": _amount_view(x.amount, user or {}), "status": x.status,
            "statusLabel": _L_LOAN.get(x.status, x.status), "remark": x.remark or ""}


def list_loans(user, status=None):
    from app.models import StudentLoan
    with session() as db:
        conds = [StudentLoan.tenant_id == _tid(), StudentLoan.is_deleted.is_(False)]
        if status:
            conds.append(StudentLoan.status == status)
        rows = db.scalars(select(StudentLoan).where(*conds).order_by(StudentLoan.id.desc())).all()
        return _scoped_out(db, rows, user, lambda x: x.student_id, lambda x, s: _loan_row(x, s, user))


def register_loan(body, user) -> dict:
    from app.models import StudentLoan
    sid = int(getattr(body, "studentId", 0) or 0)
    ltype = getattr(body, "loanType", "ORIGIN") or "ORIGIN"
    if ltype not in ("ORIGIN", "CAMPUS"):
        raise AppException("VALIDATION_ERROR", "贷款类型非法")
    with session() as db:
        s = _require_student(db, sid)
        _scope_or_403(db, sid, user)
        last4 = getattr(body, "bankLast4", None)
        x = StudentLoan(tenant_id=_tid(), student_id=sid, loan_type=ltype,
                        bank_name=getattr(body, "bankName", None),
                        bank_last4=(str(last4)[-4:] if last4 else None),
                        year_code=getattr(body, "yearCode", None), amount=getattr(body, "amount", None),
                        status="REGISTERED", remark=getattr(body, "remark", None), created_by=_uid(user))
        db.add(x); db.flush()
        _audit(db, x.id, "LOAN_REGISTER", ltype)
        db.commit(); db.refresh(x)
        return _loan_row(x, s, user)


def advance_loan(loan_id, user) -> dict:
    """按 登记→回执→核对→确认 顺序推进一步。"""
    from app.models import StudentLoan, StudentProfile
    with session() as db:
        x = db.get(StudentLoan, int(loan_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("贷款记录不存在")
        _scope_or_403(db, x.student_id, user)
        nxt = _LOAN_NEXT.get(x.status)
        if not nxt:
            raise AppException("DATA_CONFLICT", "已确认，无需再推进")
        x.status, x.version = nxt, x.version + 1
        _audit(db, x.id, "LOAN_ADVANCE", nxt)
        db.commit(); db.refresh(x)
        s = db.get(StudentProfile, int(x.student_id))
        return _loan_row(x, s, user)


# ═══════════ 减免与临时补助 ═══════════

_L_FEE = {"SUBMITTED": "待审核", "APPROVED": "已批准", "REJECTED": "已驳回", "ISSUED": "已发放"}


def _fee_row(x, s=None, user=None) -> dict:
    return {"feeId": str(x.id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "itemType": x.item_type, "amount": _amount_view(x.amount, user or {}),
            "reason": x.reason or "", "status": x.status, "statusLabel": _L_FEE.get(x.status, x.status),
            "reviewOpinion": x.review_opinion or "", "reviewer": x.reviewer or "",
            "issuedAt": _iso(x.issued_at)}


def list_reductions(user, itemType=None, status=None):
    from app.models import FeeReduction
    with session() as db:
        conds = [FeeReduction.tenant_id == _tid(), FeeReduction.is_deleted.is_(False)]
        if itemType:
            conds.append(FeeReduction.item_type == itemType)
        if status:
            conds.append(FeeReduction.status == status)
        rows = db.scalars(select(FeeReduction).where(*conds).order_by(FeeReduction.id.desc())).all()
        return _scoped_out(db, rows, user, lambda x: x.student_id, lambda x, s: _fee_row(x, s, user))


def submit_reduction(body, user) -> dict:
    from app.models import FeeReduction
    sid = int(getattr(body, "studentId", 0) or 0)
    itype = getattr(body, "itemType", "REDUCTION") or "REDUCTION"
    if itype not in ("REDUCTION", "TEMP_AID"):
        raise AppException("VALIDATION_ERROR", "类型非法")
    reason = (getattr(body, "reason", "") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申请理由至少 5 字")
    with session() as db:
        s = _require_student(db, sid)
        _scope_or_403(db, sid, user)
        x = FeeReduction(tenant_id=_tid(), student_id=sid, item_type=itype,
                         amount=getattr(body, "amount", None), reason=reason, status="SUBMITTED",
                         created_by=_uid(user))
        db.add(x); db.flush()
        _audit(db, x.id, "FEE_SUBMIT", itype)
        db.commit(); db.refresh(x)
        return _fee_row(x, s, user)


def review_reduction(fee_id, body, user) -> dict:
    """审核：APPROVE→APPROVED；REJECT→REJECTED(意见≥5)。"""
    from app.models import FeeReduction, StudentProfile
    action = (getattr(body, "action", "") or "").upper()
    opinion = (getattr(body, "opinion", "") or "").strip()
    with session() as db:
        x = db.get(FeeReduction, int(fee_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("记录不存在")
        _scope_or_403(db, x.student_id, user)
        if x.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅待审核可处理")
        if action == "APPROVE":
            x.status = "APPROVED"
        elif action == "REJECT":
            if len(opinion) < 5:
                raise AppException("VALIDATION_ERROR", "驳回意见至少 5 字")
            x.status = "REJECTED"
        else:
            raise AppException("VALIDATION_ERROR", "动作非法")
        x.review_opinion, x.reviewer, x.version = opinion, _op()[0], x.version + 1
        _audit(db, x.id, "FEE_" + action, "")
        db.commit(); db.refresh(x)
        s = db.get(StudentProfile, int(x.student_id))
        return _fee_row(x, s, user)


def issue_reduction(fee_id, user) -> dict:
    from app.models import FeeReduction, StudentProfile
    with session() as db:
        x = db.get(FeeReduction, int(fee_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("记录不存在")
        _scope_or_403(db, x.student_id, user)
        if x.status != "APPROVED":
            raise AppException("DATA_CONFLICT", "仅已批准可发放")
        x.status, x.issued_at, x.version = "ISSUED", datetime.utcnow(), x.version + 1
        _audit(db, x.id, "FEE_ISSUE", "")
        db.commit(); db.refresh(x)
        s = db.get(StudentProfile, int(x.student_id))
        return _fee_row(x, s, user)


# ═══════════ 勤工月度考核（月度考核→累计补贴）═══════════

_L_RATING = {"GOOD": "优", "PASS": "合格", "FAIL": "不合格"}


def _monthly_row(m, user=None) -> dict:
    return {"monthlyId": str(m.id), "recordId": str(m.record_id), "studentId": str(m.student_id),
            "monthCode": m.month_code, "workHours": float(m.work_hours) if m.work_hours is not None else None,
            "rating": m.rating, "ratingLabel": _L_RATING.get(m.rating, m.rating),
            "subsidyAmount": _amount_view(m.subsidy_amount, user or {}), "remark": m.remark or ""}


def add_monthly(record_id, body, user) -> dict:
    """录一条月度考核（仅在岗记录；同月唯一）。FAIL 不计补贴；否则按 subsidyAmount 累计到 subsidy_total。"""
    from app.models import WorkStudyMonthly
    month = (getattr(body, "monthCode", "") or "").strip()
    rating = getattr(body, "rating", "PASS") or "PASS"
    if not month:
        raise AppException("VALIDATION_ERROR", "考核月必填")
    if rating not in ("GOOD", "PASS", "FAIL"):
        raise AppException("VALIDATION_ERROR", "考核等级非法")
    with session() as db:
        r = _load_ws(db, record_id)
        if r.status != "ONBOARD":
            raise AppException("DATA_CONFLICT", "仅在岗记录可录月度考核")
        dup = db.scalars(select(WorkStudyMonthly).where(
            WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.record_id == int(record_id),
            WorkStudyMonthly.month_code == month, WorkStudyMonthly.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该月已考核")
        amt = float(getattr(body, "subsidyAmount", 0) or 0)
        if rating == "FAIL":
            amt = 0.0
        m = WorkStudyMonthly(tenant_id=_tid(), record_id=int(record_id), student_id=r.student_id,
                             month_code=month, work_hours=getattr(body, "workHours", None),
                             rating=rating, subsidy_amount=amt, remark=getattr(body, "remark", None),
                             created_by=_uid(user))
        db.add(m); db.flush()
        r.subsidy_total = round(float(r.subsidy_total or 0) + amt, 2)
        r.version += 1
        _audit(db, r.id, "WS_MONTHLY", f"{month}:{rating}:{amt}")
        db.commit(); db.refresh(m)
        return _monthly_row(m, user)


def list_monthly(record_id, user):
    from app.models import WorkStudyMonthly
    with session() as db:
        _load_ws(db, record_id)
        rows = db.scalars(select(WorkStudyMonthly).where(
            WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.record_id == int(record_id),
            WorkStudyMonthly.is_deleted.is_(False)).order_by(WorkStudyMonthly.month_code.desc())).all()
        return [_monthly_row(m, user) for m in rows]
