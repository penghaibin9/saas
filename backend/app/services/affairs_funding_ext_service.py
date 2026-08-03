"""13A 奖助扩展服务：勤工助学 / 助学贷款 / 减免与临时补助。

金额按角色脱敏（复用 funding 的 _amount_view）；不落银行卡全号。留痕 AuditTrail(biz_type=FUNDING_EXT)。
数据范围复用 _allowed_class_ids（辅导员限本班）。
"""

from app.core.optimistic_lock import atomic_claim_version

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.services.affairs_funding_service import _amount_view
from app.services.db_service import _iso, _tid, session


_MAX_AMOUNT = Decimal("999999999999.99")


def _money(value, label: str, *, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise AppException("VALIDATION_ERROR", f"{label}必填")
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}格式非法") from exc
    if not amount.is_finite() or amount < 0 or amount > _MAX_AMOUNT:
        raise AppException("VALIDATION_ERROR", f"{label}应在0至999999999999.99之间")
    if amount.as_tuple().exponent < -2:
        raise AppException("VALIDATION_ERROR", f"{label}最多保留2位小数")
    return amount


def _page(page=1, page_size=50):
    return max(1, int(page or 1)), max(1, min(int(page_size or 50), 200))

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
    student_ids = {int(sid_getter(row)) for row in rows if sid_getter(row)}
    students = {
        int(student.id): student
        for student in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id.in_(student_ids) if student_ids else StudentProfile.id == -1,
            StudentProfile.is_deleted.is_(False),
        )).all()
    }
    out = []
    for row in rows:
        sid = int(sid_getter(row)) if sid_getter(row) else None
        student = students.get(sid) if sid else None
        if allowed is not None and (not student or student.class_id not in allowed):
            continue
        out.append(row_fn(row, student))
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
            "salary": format(p.salary, ".2f") if p.salary is not None else None, "headcount": p.headcount,
            "requirement": p.requirement or "", "status": p.status, "version": int(p.version or 0)}


def list_posts(user, status=None, page=1, page_size=50):
    from app.models import WorkStudyPost
    page, page_size = _page(page, page_size)
    with session() as db:
        conds = [WorkStudyPost.tenant_id == _tid(), WorkStudyPost.is_deleted.is_(False)]
        if status:
            conds.append(WorkStudyPost.status == status)
        total = int(db.scalar(select(func.count()).select_from(WorkStudyPost).where(*conds)) or 0)
        rows = db.scalars(select(WorkStudyPost).where(*conds).order_by(
            WorkStudyPost.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return [_post_row(p) for p in rows], total


def create_post(body, user) -> dict:
    from app.models import WorkStudyPost
    dept = (getattr(body, "deptName", "") or "").strip()
    name = (getattr(body, "postName", "") or "").strip()
    if not dept or not name:
        raise AppException("VALIDATION_ERROR", "部门与岗位名称必填")
    salary = _money(getattr(body, "salary", None), "岗位薪酬")
    headcount = getattr(body, "headcount", None)
    if headcount not in (None, ""):
        try:
            headcount = int(headcount)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "需求人数必须为整数") from exc
        if headcount < 1 or headcount > 10000:
            raise AppException("VALIDATION_ERROR", "需求人数应为1-10000")
    with session() as db:
        p = WorkStudyPost(
            tenant_id=_tid(), dept_name=dept, post_name=name, salary=salary,
            headcount=headcount, requirement=getattr(body, "requirement", None),
            status="ENABLED", created_by=_uid(user),
        )
        db.add(p); db.flush()
        _audit(db, p.id, "WS_POST_CREATE", name)
        db.commit(); db.refresh(p)
        return _post_row(p)


def _ws_row(r, s=None, user=None) -> dict:
    return {"recordId": str(r.id), "postId": str(r.post_id), "studentId": str(r.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "status": r.status, "statusLabel": _L_WS.get(r.status, r.status),
            "onboardAt": _iso(r.onboard_at), "subsidyTotal": _amount_view(r.subsidy_total, user or {}),
            "remark": r.remark or "", "version": int(r.version or 0),
            "allowedActions": {
                "APPLIED": ["APPROVE", "REJECT"],
                "APPROVED": ["ONBOARD", "TERMINATE"],
                "ONBOARD": ["TERMINATE"],
            }.get(r.status, [])}


def list_ws_records(user, post_id=None, status=None, page=1, page_size=50):
    from app.models import StudentProfile, WorkStudyRecord
    from app.services.affairs_dashboard_service import _allowed_class_ids
    page, page_size = _page(page, page_size)
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        scope_conds = [
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        ]
        if allowed is not None:
            scope_conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        status_rows = db.execute(select(WorkStudyRecord.status, func.count(WorkStudyRecord.id)).join(
            StudentProfile, StudentProfile.id == WorkStudyRecord.student_id
        ).where(*scope_conds).group_by(WorkStudyRecord.status)).all()
        status_counts = {str(key): int(count or 0) for key, count in status_rows}
        status_counts["ALL"] = sum(status_counts.values())
        conds = list(scope_conds)
        if post_id:
            conds.append(WorkStudyRecord.post_id == int(post_id))
        if status:
            conds.append(WorkStudyRecord.status == status)
        total = int(db.scalar(select(func.count(WorkStudyRecord.id)).select_from(WorkStudyRecord).join(
            StudentProfile, StudentProfile.id == WorkStudyRecord.student_id
        ).where(*conds)) or 0)
        rows = db.execute(select(WorkStudyRecord, StudentProfile).join(
            StudentProfile, StudentProfile.id == WorkStudyRecord.student_id
        ).where(*conds).order_by(WorkStudyRecord.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_ws_row(row, student, user) for row, student in rows], total, status_counts


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


def act_work_study(record_id, action, user, reason="", *, expected_version=None) -> dict:
    """并发安全的勤工流转；录用时锁定岗位并校验剩余名额。"""
    from app.models import StudentProfile, WorkStudyPost, WorkStudyRecord
    action = str(action or "").upper()
    with session() as db:
        record = db.scalars(select(WorkStudyRecord).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.id == int(record_id),
            WorkStudyRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not record:
            raise not_found("上岗记录不存在")
        _scope_or_403(db, record.student_id, user)
        atomic_claim_version(db, record, expected_version)
        before = record.status
        if action == "APPROVE":
            if before != "APPLIED":
                raise AppException("DATA_CONFLICT", "仅待审核可录用")
            post = db.scalars(select(WorkStudyPost).where(
                WorkStudyPost.tenant_id == _tid(), WorkStudyPost.id == int(record.post_id),
                WorkStudyPost.is_deleted.is_(False),
            ).with_for_update()).first()
            if not post or post.status != "ENABLED":
                raise AppException("DATA_CONFLICT", "岗位已停用或不存在")
            occupied = int(db.scalar(select(func.count()).select_from(WorkStudyRecord).where(
                WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.post_id == post.id,
                WorkStudyRecord.status.in_(("APPROVED", "ONBOARD")),
                WorkStudyRecord.is_deleted.is_(False),
            )) or 0)
            if post.headcount is not None and occupied >= int(post.headcount):
                raise AppException("DATA_CONFLICT", "岗位录用人数已满")
            record.status = "APPROVED"
        elif action == "REJECT":
            if before != "APPLIED":
                raise AppException("DATA_CONFLICT", "仅待审核可拒绝")
            record.status = "REJECTED"
        elif action == "ONBOARD":
            if before != "APPROVED":
                raise AppException("DATA_CONFLICT", "仅已录用可上岗")
            record.status, record.onboard_at = "ONBOARD", datetime.utcnow()
        elif action == "TERMINATE":
            if before not in ("APPROVED", "ONBOARD"):
                raise AppException("DATA_CONFLICT", "该记录不可终止")
            text = str(reason or "").strip()
            if not 5 <= len(text) <= 500:
                raise AppException("VALIDATION_ERROR", "终止原因需5-500字")
            record.status, record.terminated_at, record.remark = "TERMINATED", datetime.utcnow(), text
        else:
            raise AppException("VALIDATION_ERROR", "动作非法")
        record.version = int(record.version or 0) + 1
        _audit(db, record.id, "WS_" + action, f"{before}->{record.status}")
        db.commit(); db.refresh(record)
        student = db.get(StudentProfile, int(record.student_id))
        return _ws_row(record, student, user)


def _loan_row(x, s=None, user=None) -> dict:
    return {"loanId": str(x.id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "loanType": x.loan_type, "bankName": x.bank_name or "",
            "bankLast4": x.bank_last4 or "", "yearCode": x.year_code or "",
            "amount": _amount_view(x.amount, user or {}), "status": x.status,
            "statusLabel": _L_LOAN.get(x.status, x.status), "remark": x.remark or "",
            "version": int(x.version or 0),
            "allowedActions": ["ADVANCE"] if x.status in _LOAN_NEXT else []}


def list_loans(user, status=None, page=1, page_size=50):
    from app.models import StudentLoan, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    page, page_size = _page(page, page_size)
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        scope_conds = [
            StudentLoan.tenant_id == _tid(), StudentLoan.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        ]
        if allowed is not None:
            scope_conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        status_rows = db.execute(select(StudentLoan.status, func.count(StudentLoan.id)).join(
            StudentProfile, StudentProfile.id == StudentLoan.student_id
        ).where(*scope_conds).group_by(StudentLoan.status)).all()
        status_counts = {str(key): int(count or 0) for key, count in status_rows}
        status_counts["ALL"] = sum(status_counts.values())
        conds = list(scope_conds)
        if status:
            conds.append(StudentLoan.status == status)
        total = int(db.scalar(select(func.count(StudentLoan.id)).select_from(StudentLoan).join(
            StudentProfile, StudentProfile.id == StudentLoan.student_id
        ).where(*conds)) or 0)
        rows = db.execute(select(StudentLoan, StudentProfile).join(
            StudentProfile, StudentProfile.id == StudentLoan.student_id
        ).where(*conds).order_by(StudentLoan.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_loan_row(row, student, user) for row, student in rows], total, status_counts


def register_loan(body, user) -> dict:
    from app.models import StudentLoan
    sid = int(getattr(body, "studentId", 0) or 0)
    ltype = getattr(body, "loanType", "ORIGIN") or "ORIGIN"
    if ltype not in ("ORIGIN", "CAMPUS"):
        raise AppException("VALIDATION_ERROR", "贷款类型非法")
    amount = _money(getattr(body, "amount", None), "贷款金额", required=True)
    last4 = str(getattr(body, "bankLast4", None) or "").strip()
    if last4 and not re.fullmatch(r"\d{4}", last4):
        raise AppException("VALIDATION_ERROR", "银行卡后4位必须为4位数字")
    with session() as db:
        student = _require_student(db, sid)
        _scope_or_403(db, sid, user)
        row = StudentLoan(
            tenant_id=_tid(), student_id=sid, loan_type=ltype,
            bank_name=getattr(body, "bankName", None), bank_last4=last4 or None,
            year_code=getattr(body, "yearCode", None), amount=amount,
            status="REGISTERED", remark=getattr(body, "remark", None), created_by=_uid(user),
        )
        db.add(row); db.flush()
        _audit(db, row.id, "LOAN_REGISTER", ltype)
        db.commit(); db.refresh(row)
        return _loan_row(row, student, user)


def advance_loan(loan_id, user, *, expected_version=None) -> dict:
    """按 登记→回执→核对→确认 顺序推进一步。"""
    from app.models import StudentLoan, StudentProfile
    with session() as db:
        x = db.get(StudentLoan, int(loan_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("贷款记录不存在")
        _scope_or_403(db, x.student_id, user)
        atomic_claim_version(db, x, expected_version)
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
            "issuedAt": _iso(x.issued_at), "version": int(x.version or 0),
            "allowedActions": {"SUBMITTED": ["APPROVE", "REJECT"], "APPROVED": ["ISSUE"]}.get(x.status, [])}


def list_reductions(user, itemType=None, status=None, page=1, page_size=50):
    from app.models import FeeReduction, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    page, page_size = _page(page, page_size)
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        scope_conds = [
            FeeReduction.tenant_id == _tid(), FeeReduction.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        ]
        if allowed is not None:
            scope_conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        status_rows = db.execute(select(FeeReduction.status, func.count(FeeReduction.id)).join(
            StudentProfile, StudentProfile.id == FeeReduction.student_id
        ).where(*scope_conds).group_by(FeeReduction.status)).all()
        status_counts = {str(key): int(count or 0) for key, count in status_rows}
        status_counts["ALL"] = sum(status_counts.values())
        conds = list(scope_conds)
        if itemType:
            conds.append(FeeReduction.item_type == itemType)
        if status:
            conds.append(FeeReduction.status == status)
        total = int(db.scalar(select(func.count(FeeReduction.id)).select_from(FeeReduction).join(
            StudentProfile, StudentProfile.id == FeeReduction.student_id
        ).where(*conds)) or 0)
        rows = db.execute(select(FeeReduction, StudentProfile).join(
            StudentProfile, StudentProfile.id == FeeReduction.student_id
        ).where(*conds).order_by(FeeReduction.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_fee_row(row, student, user) for row, student in rows], total, status_counts


def submit_reduction(body, user) -> dict:
    from app.models import FeeReduction
    sid = int(getattr(body, "studentId", 0) or 0)
    item_type = getattr(body, "itemType", "REDUCTION") or "REDUCTION"
    if item_type not in ("REDUCTION", "TEMP_AID"):
        raise AppException("VALIDATION_ERROR", "类型非法")
    reason = (getattr(body, "reason", "") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申请理由至少 5 字")
    amount = _money(getattr(body, "amount", None), "减免/补助金额", required=True)
    if amount <= 0:
        raise AppException("VALIDATION_ERROR", "减免/补助金额必须大于0")
    with session() as db:
        student = _require_student(db, sid)
        _scope_or_403(db, sid, user)
        row = FeeReduction(
            tenant_id=_tid(), student_id=sid, item_type=item_type,
            amount=amount, reason=reason, status="SUBMITTED", created_by=_uid(user),
        )
        db.add(row); db.flush()
        _audit(db, row.id, "FEE_SUBMIT", item_type)
        db.commit(); db.refresh(row)
        return _fee_row(row, student, user)


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
        atomic_claim_version(db, x, getattr(body, "version", None))
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


def issue_reduction(fee_id, user, *, expected_version=None) -> dict:
    from app.models import FeeReduction, StudentProfile
    with session() as db:
        x = db.get(FeeReduction, int(fee_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("记录不存在")
        _scope_or_403(db, x.student_id, user)
        atomic_claim_version(db, x, expected_version)
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
    """仅在岗记录可写入；同月唯一，金额与累计值均采用锁和定点数。"""
    from app.models import WorkStudyMonthly, WorkStudyRecord
    month = str(getattr(body, "monthCode", None) or "").strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise AppException("VALIDATION_ERROR", "考核月格式应为YYYY-MM")
    rating = str(getattr(body, "rating", None) or "PASS").upper()
    if rating not in ("GOOD", "PASS", "FAIL"):
        raise AppException("VALIDATION_ERROR", "考核等级非法")
    try:
        hours = Decimal(str(getattr(body, "workHours", None)))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "工时必须为数字") from exc
    if hours < 0 or hours > Decimal("9999.99") or hours.as_tuple().exponent < -2:
        raise AppException("VALIDATION_ERROR", "工时应为0-9999.99且最多2位小数")
    amount = _money(getattr(body, "subsidyAmount", None), "当月补贴", required=True)
    if rating == "FAIL":
        amount = Decimal("0.00")
    with session() as db:
        record = db.scalars(select(WorkStudyRecord).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.id == int(record_id),
            WorkStudyRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not record:
            raise not_found("上岗记录不存在")
        _scope_or_403(db, record.student_id, user)
        if record.status != "ONBOARD":
            raise AppException("DATA_CONFLICT", "仅在岗记录可录月度考核")
        duplicate = db.scalars(select(WorkStudyMonthly.id).where(
            WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.record_id == record.id,
            WorkStudyMonthly.month_code == month, WorkStudyMonthly.is_deleted.is_(False),
        )).first()
        if duplicate:
            raise AppException("DATA_CONFLICT", "该月已考核")
        monthly = WorkStudyMonthly(
            tenant_id=_tid(), record_id=record.id, student_id=record.student_id,
            month_code=month, work_hours=hours, rating=rating, subsidy_amount=amount,
            remark=(str(getattr(body, "remark", None) or "").strip() or None),
            created_by=_uid(user),
        )
        db.add(monthly)
        record.subsidy_total = (Decimal(str(record.subsidy_total or 0)) + amount).quantize(Decimal("0.01"))
        if record.subsidy_total > _MAX_AMOUNT:
            raise AppException("DATA_CONFLICT", "累计补贴超过金额上限")
        record.version = int(record.version or 0) + 1
        _audit(db, record.id, "WS_MONTHLY", f"{month}:{rating}:{amount}")
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppException("DATA_CONFLICT", "该月已考核") from exc
        db.refresh(monthly)
        return _monthly_row(monthly, user)


def list_monthly(record_id, user):
    from app.models import WorkStudyMonthly
    with session() as db:
        record = _load_ws(db, record_id)
        _scope_or_403(db, record.student_id, user)
        rows = db.scalars(select(WorkStudyMonthly).where(
            WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.record_id == int(record_id),
            WorkStudyMonthly.is_deleted.is_(False),
        ).order_by(WorkStudyMonthly.month_code.desc())).all()
        return [_monthly_row(row, user) for row in rows]
