"""13A 奖助扩展服务：勤工助学 / 助学贷款 / 减免与临时补助。

金额按角色脱敏（复用 funding 的 _amount_view）；不落银行卡全号。留痕 AuditTrail(biz_type=FUNDING_EXT)。
数据范围复用 _allowed_class_ids（辅导员限本班）。
"""

from app.core.optimistic_lock import atomic_claim_version

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.field_crypto import decrypt_field, encrypt_field, hash_sensitive
from app.services.affairs_funding_service import _amount_view
from app.services.db_service import _iso, _tid, session


_MAX_AMOUNT = Decimal("999999999999.99")
_L_LOAN = {
    "REGISTERED": "待补回执", "RECEIPT": "待学校核验", "RETURNED": "已退回修改",
    "VERIFIED": "已核验", "CONFIRMED": "已确认", "WITHDRAWN": "已撤回",
}
_LOAN_STAFF_ACTIONS = {
    "REGISTERED": ["SUBMIT_RECEIPT"], "RETURNED": ["SUBMIT_RECEIPT"],
    "RECEIPT": ["VERIFY", "RETURN"], "VERIFIED": ["CONFIRM", "RETURN"],
}
_LOAN_STUDENT_ACTIONS = {
    "REGISTERED": ["SUBMIT_RECEIPT"], "RETURNED": ["RESUBMIT"], "RECEIPT": ["WITHDRAW"],
}
_LOAN_MIN_AMOUNT = Decimal("1000.00")
_LOAN_MAX_AMOUNT = Decimal("20000.00")


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

_L_WS = {"APPLIED": "待审核", "APPROVED": "已录用", "ONBOARD": "在岗", "REJECTED": "未录用",
         "TERMINATED": "已终止", "WITHDRAWN": "已撤回"}


def _datetime_or_none(value, label: str):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}格式非法") from exc


def _decimal_limit(value, label: str, *, maximum: Decimal) -> Decimal:
    amount = _money(value, label, required=True)
    if amount is None or amount <= 0 or amount > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}应大于0且不超过{maximum}")
    return amount


def _post_open(p, now=None) -> bool:
    now = now or datetime.utcnow()
    return p.status == "ENABLED" and (p.apply_end is None or p.apply_end >= now)


def _post_row(p, *, counts=None, my_record=None) -> dict:
    counts = counts or {}
    return {"postId": str(p.id), "deptName": p.dept_name, "postName": p.post_name,
            "salary": format(p.salary, ".2f") if p.salary is not None else None, "headcount": p.headcount,
            "requirement": p.requirement or "", "employmentType": p.employment_type or "FIXED",
            "workLocation": p.work_location or "", "scheduleText": p.schedule_text or "",
            "applyEnd": _iso(p.apply_end), "monthlyHoursLimit": format(
                Decimal(str(p.monthly_hours_limit or 40)), ".2f"),
            "agreementRequired": bool(p.agreement_required), "status": p.status,
            "openForApplication": _post_open(p), "appliedCount": int(counts.get("APPLIED", 0)),
            "approvedCount": int(counts.get("APPROVED", 0)), "onboardCount": int(counts.get("ONBOARD", 0)),
            "remainingHeadcount": None if p.headcount is None else max(
                0, int(p.headcount) - int(counts.get("APPROVED", 0)) - int(counts.get("ONBOARD", 0))),
            "myRecord": my_record, "version": int(p.version or 0)}


def list_posts(user, status=None, page=1, page_size=50, keyword=""):
    from app.models import WorkStudyPost, WorkStudyRecord
    page, page_size = _page(page, page_size)
    with session() as db:
        conds = [WorkStudyPost.tenant_id == _tid(), WorkStudyPost.is_deleted.is_(False)]
        if status:
            conds.append(WorkStudyPost.status == status)
        term = str(keyword or "").strip()
        if term:
            conds.append(or_(WorkStudyPost.post_name.contains(term, autoescape=True),
                             WorkStudyPost.dept_name.contains(term, autoescape=True),
                             WorkStudyPost.work_location.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(WorkStudyPost).where(*conds)) or 0)
        rows = db.scalars(select(WorkStudyPost).where(*conds).order_by(
            WorkStudyPost.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        post_ids = [int(p.id) for p in rows]
        count_rows = db.execute(select(WorkStudyRecord.post_id, WorkStudyRecord.status,
            func.count(WorkStudyRecord.id)).where(
                WorkStudyRecord.tenant_id == _tid(),
                WorkStudyRecord.post_id.in_(post_ids or [-1]),
                WorkStudyRecord.is_deleted.is_(False),
            ).group_by(WorkStudyRecord.post_id, WorkStudyRecord.status)).all()
        counts = {}
        for post_id, record_status, count in count_rows:
            counts.setdefault(int(post_id), {})[str(record_status)] = int(count or 0)
        return [_post_row(p, counts=counts.get(int(p.id))) for p in rows], total


def create_post(body, user) -> dict:
    from app.models import WorkStudyPost
    dept = (getattr(body, "deptName", "") or "").strip()
    name = (getattr(body, "postName", "") or "").strip()
    if not dept or not name:
        raise AppException("VALIDATION_ERROR", "部门与岗位名称必填")
    salary = _money(getattr(body, "salary", None), "岗位薪酬")
    employment_type = str(getattr(body, "employmentType", None) or "FIXED").upper()
    if employment_type not in ("FIXED", "TEMPORARY"):
        raise AppException("VALIDATION_ERROR", "岗位类型应为固定岗位或临时岗位")
    apply_end = _datetime_or_none(getattr(body, "applyEnd", None), "申请截止时间")
    if apply_end is not None and apply_end <= datetime.utcnow():
        raise AppException("VALIDATION_ERROR", "申请截止时间必须晚于当前时间")
    monthly_hours_limit = _decimal_limit(
        getattr(body, "monthlyHoursLimit", None) or "40", "月工时上限", maximum=Decimal("40")
    )
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
            employment_type=employment_type,
            work_location=(str(getattr(body, "workLocation", None) or "").strip() or None),
            schedule_text=(str(getattr(body, "scheduleText", None) or "").strip() or None),
            apply_end=apply_end, monthly_hours_limit=monthly_hours_limit,
            agreement_required=bool(getattr(body, "agreementRequired", True)),
            status="ENABLED", created_by=_uid(user),
        )
        db.add(p); db.flush()
        _audit(db, p.id, "WS_POST_CREATE", name)
        db.commit(); db.refresh(p)
        return _post_row(p)


def set_post_status(post_id, action, user, *, expected_version=None) -> dict:
    from app.models import WorkStudyPost
    action = str(action or "").upper()
    target = {"ENABLE": "ENABLED", "DISABLE": "DISABLED"}.get(action)
    if not target:
        raise AppException("VALIDATION_ERROR", "岗位动作非法")
    with session() as db:
        post = db.scalars(select(WorkStudyPost).where(
            WorkStudyPost.tenant_id == _tid(), WorkStudyPost.id == int(post_id),
            WorkStudyPost.is_deleted.is_(False),
        ).with_for_update()).first()
        if not post:
            raise not_found("岗位不存在")
        atomic_claim_version(db, post, expected_version)
        if post.status == target:
            raise AppException("DATA_CONFLICT", "岗位已经处于目标状态")
        before = post.status
        post.status = target
        post.version = int(post.version or 0) + 1
        _audit(db, post.id, f"WS_POST_{action}", f"{before}->{target}")
        db.commit(); db.refresh(post)
        return _post_row(post)


def _ws_row(r, s=None, user=None, *, exact_amount: bool = False) -> dict:
    subsidy_total = (format(r.subsidy_total, ".2f") if exact_amount and r.subsidy_total is not None
                     else _amount_view(r.subsidy_total, user or {}))
    return {"recordId": str(r.id), "postId": str(r.post_id), "studentId": str(r.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "status": r.status, "statusLabel": _L_WS.get(r.status, r.status),
            "onboardAt": _iso(r.onboard_at), "subsidyTotal": subsidy_total,
            "terminatedAt": _iso(r.terminated_at), "applyStatement": r.apply_statement or "",
            "availability": r.availability or "", "agreementConfirmed": bool(r.agreement_confirmed),
            "agreementConfirmedAt": _iso(r.agreement_confirmed_at),
            "remark": r.remark or "", "version": int(r.version or 0),
            "allowedActions": {
                "APPLIED": ["APPROVE", "REJECT"],
                "APPROVED": ["ONBOARD", "TERMINATE"],
                "ONBOARD": ["MONTHLY", "TERMINATE"],
            }.get(r.status, [])}


def list_ws_records(user, post_id=None, status=None, page=1, page_size=50, keyword="", record_id=None):
    from app.models import StudentProfile, WorkStudyPost, WorkStudyRecord
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
        if record_id is not None:
            conds.append(WorkStudyRecord.id == int(record_id))
        if post_id:
            conds.append(WorkStudyRecord.post_id == int(post_id))
        if status:
            conds.append(WorkStudyRecord.status == status)
        term = str(keyword or "").strip()
        if term:
            conds.append(or_(StudentProfile.real_name.contains(term, autoescape=True),
                             StudentProfile.student_no.contains(term, autoescape=True),
                             WorkStudyPost.post_name.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count(WorkStudyRecord.id)).select_from(WorkStudyRecord).join(
            StudentProfile, StudentProfile.id == WorkStudyRecord.student_id).join(
            WorkStudyPost, WorkStudyPost.id == WorkStudyRecord.post_id
        ).where(*conds)) or 0)
        rows = db.execute(select(WorkStudyRecord, StudentProfile, WorkStudyPost).join(
            StudentProfile, StudentProfile.id == WorkStudyRecord.student_id).join(
            WorkStudyPost, WorkStudyPost.id == WorkStudyRecord.post_id
        ).where(*conds).order_by(WorkStudyRecord.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [{**_ws_row(row, student, user), "post": _post_row(post)}
                for row, student, post in rows], total, status_counts


def apply_work_study(post_id, body, user, *, skip_scope_check=False) -> dict:
    from app.models import WorkStudyPost, WorkStudyRecord
    sid = int(getattr(body, "studentId", 0) or 0)
    with session() as db:
        p = db.scalars(select(WorkStudyPost).where(
            WorkStudyPost.tenant_id == _tid(), WorkStudyPost.id == int(post_id),
            WorkStudyPost.is_deleted.is_(False),
        ).with_for_update()).first()
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("岗位不存在")
        if not _post_open(p):
            raise AppException("DATA_CONFLICT", "岗位未开放或申请已截止")
        s = _require_student(db, sid)
        if not skip_scope_check:
            _scope_or_403(db, sid, user)
        dup = db.scalars(select(WorkStudyRecord).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.post_id == int(post_id),
            WorkStudyRecord.student_id == sid,
            WorkStudyRecord.status.in_(("APPLIED", "APPROVED", "ONBOARD")),
            WorkStudyRecord.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生已申请/在岗此岗位")
        statement = str(getattr(body, "statement", None) or "").strip()
        availability = str(getattr(body, "availability", None) or "").strip()
        r = WorkStudyRecord(tenant_id=_tid(), post_id=int(post_id), student_id=sid, status="APPLIED",
                            apply_statement=statement or None, availability=availability or None,
                            created_by=_uid(user))
        db.add(r); db.flush()
        _audit(db, r.id, "WS_APPLY", f"student={sid}")
        from app.services.affairs_funding_todo_service import sync_work_study_todos
        sync_work_study_todos(db, r)
        db.commit(); db.refresh(r)
        return _ws_row(r, s, user)


def student_posts(user, keyword="", page=1, page_size=20) -> dict:
    from app.models import WorkStudyPost, WorkStudyRecord
    from app.services.mobile_affairs_service import _me
    page, page_size = _page(page, page_size)
    with session() as db:
        student = _me(db, user)
        now = datetime.utcnow()
        conds = [WorkStudyPost.tenant_id == _tid(), WorkStudyPost.is_deleted.is_(False),
                 WorkStudyPost.status == "ENABLED",
                 or_(WorkStudyPost.apply_end.is_(None), WorkStudyPost.apply_end >= now)]
        term = str(keyword or "").strip()
        if term:
            conds.append(or_(WorkStudyPost.post_name.contains(term, autoescape=True),
                             WorkStudyPost.dept_name.contains(term, autoescape=True),
                             WorkStudyPost.work_location.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(WorkStudyPost).where(*conds)) or 0)
        posts = db.scalars(select(WorkStudyPost).where(*conds).order_by(
            WorkStudyPost.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        post_ids = [int(post.id) for post in posts]
        records = db.scalars(select(WorkStudyRecord).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.student_id == student.id,
            WorkStudyRecord.post_id.in_(post_ids or [-1]), WorkStudyRecord.is_deleted.is_(False),
        ).order_by(WorkStudyRecord.id.desc())).all()
        mine = {}
        for record in records:
            row = _ws_row(record, student, user)
            row["allowedActions"] = ["WITHDRAW"] if record.status == "APPLIED" else []
            mine.setdefault(int(record.post_id), row)
        count_rows = db.execute(select(WorkStudyRecord.post_id, WorkStudyRecord.status,
            func.count(WorkStudyRecord.id)).where(
                WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.post_id.in_(post_ids or [-1]),
                WorkStudyRecord.is_deleted.is_(False),
            ).group_by(WorkStudyRecord.post_id, WorkStudyRecord.status)).all()
        counts = {}
        for post_id, record_status, count in count_rows:
            counts.setdefault(int(post_id), {})[str(record_status)] = int(count or 0)
        items = [_post_row(post, counts=counts.get(int(post.id)), my_record=mine.get(int(post.id)))
                 for post in posts]
        return {"items": items, "total": total, "page": page, "pageSize": page_size}


def student_records(user) -> dict:
    from app.models import WorkStudyMonthly, WorkStudyPost, WorkStudyRecord
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        rows = db.execute(select(WorkStudyRecord, WorkStudyPost).join(
            WorkStudyPost, WorkStudyPost.id == WorkStudyRecord.post_id).where(
                WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.student_id == student.id,
                WorkStudyRecord.is_deleted.is_(False), WorkStudyPost.tenant_id == _tid(),
                WorkStudyPost.is_deleted.is_(False),
            ).order_by(WorkStudyRecord.id.desc())).all()
        record_ids = [int(record.id) for record, _post in rows]
        monthlies = db.scalars(select(WorkStudyMonthly).where(
            WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.record_id.in_(record_ids or [-1]),
            WorkStudyMonthly.is_deleted.is_(False),
        ).order_by(WorkStudyMonthly.month_code.desc())).all()
        monthly_by_record = {}
        for monthly in monthlies:
            monthly_by_record.setdefault(int(monthly.record_id), []).append(
                _monthly_row(monthly, user, exact_amount=True))
        return {"items": [{**_ws_row(record, student, user, exact_amount=True), "post": _post_row(post),
                            "monthly": monthly_by_record.get(int(record.id), []),
                            "allowedActions": ["WITHDRAW"] if record.status == "APPLIED" else []}
                           for record, post in rows]}


def apply_work_study_self(post_id, body, user) -> dict:
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        student_id = int(student.id)
    statement = str((body or {}).get("statement") or "").strip()
    availability = str((body or {}).get("availability") or "").strip()
    if not 5 <= len(statement) <= 1000:
        raise AppException("VALIDATION_ERROR", "申请说明需5-1000字")
    if not 2 <= len(availability) <= 500:
        raise AppException("VALIDATION_ERROR", "请填写2-500字可工作时段")
    if not bool((body or {}).get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先确认申请信息真实且不影响正常学习")
    from types import SimpleNamespace
    return apply_work_study(post_id, SimpleNamespace(
        studentId=student_id, statement=statement, availability=availability), user,
        skip_scope_check=True)


def withdraw_work_study_self(record_id, body, user) -> dict:
    from app.models import StudentProfile, WorkStudyRecord
    from app.services.mobile_affairs_service import _me
    expected_version = (body or {}).get("version")
    with session() as db:
        student = _me(db, user)
        record = db.scalars(select(WorkStudyRecord).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.id == int(record_id),
            WorkStudyRecord.student_id == student.id, WorkStudyRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not record:
            raise not_found("勤工申请不存在或不属于本人")
        atomic_claim_version(db, record, expected_version)
        if record.status != "APPLIED":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        record.status = "WITHDRAWN"
        record.remark = "学生本人撤回"
        record.version = int(record.version or 0) + 1
        _audit(db, record.id, "WS_WITHDRAW", "APPLIED->WITHDRAWN")
        from app.services.affairs_funding_todo_service import sync_work_study_todos
        sync_work_study_todos(db, record)
        db.commit(); db.refresh(record)
        return _ws_row(record, db.get(StudentProfile, int(record.student_id)), user)


def _load_ws(db, rid):
    from app.models import WorkStudyRecord
    r = db.get(WorkStudyRecord, int(rid))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("上岗记录不存在")
    return r


def act_work_study(record_id, action, user, reason="", *, expected_version=None,
                   agreement_confirmed=False) -> dict:
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
            text = str(reason or "").strip()
            if not 5 <= len(text) <= 500:
                raise AppException("VALIDATION_ERROR", "未录用原因需5-500字")
            record.remark = text
            record.status = "REJECTED"
        elif action == "ONBOARD":
            if before != "APPROVED":
                raise AppException("DATA_CONFLICT", "仅已录用可上岗")
            post = db.scalars(select(WorkStudyPost).where(
                WorkStudyPost.tenant_id == _tid(), WorkStudyPost.id == int(record.post_id),
                WorkStudyPost.is_deleted.is_(False),
            ).with_for_update()).first()
            if not post:
                raise AppException("DATA_CONFLICT", "岗位不存在")
            if post.agreement_required and not bool(agreement_confirmed):
                raise AppException("DATA_CONFLICT", "请先核验学生已签署勤工助学协议")
            record.agreement_confirmed = bool(agreement_confirmed) or not post.agreement_required
            record.agreement_confirmed_at = datetime.utcnow() if record.agreement_confirmed else None
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
        from app.services.affairs_funding_todo_service import sync_work_study_todos
        sync_work_study_todos(db, record)
        db.commit(); db.refresh(record)
        student = db.get(StudentProfile, int(record.student_id))
        return _ws_row(record, student, user)


def _loan_body(body, key, default=None):
    if isinstance(body, dict):
        return body.get(key, default)
    return getattr(body, key, default)


def _loan_year(value) -> str:
    year = str(value or "").strip()
    match = re.fullmatch(r"(\d{4})-(\d{4})", year)
    if not match or int(match.group(2)) != int(match.group(1)) + 1:
        raise AppException("VALIDATION_ERROR", "贷款学年格式应为连续的 YYYY-YYYY")
    return year


def _loan_amount(value) -> Decimal:
    amount = _money(value, "贷款金额", required=True)
    if amount is None or amount < _LOAN_MIN_AMOUNT or amount > _LOAN_MAX_AMOUNT:
        raise AppException("VALIDATION_ERROR", "高职学生年度贷款金额应在1000至20000元之间")
    return amount


def _receipt_code(value, *, required: bool) -> str | None:
    code = re.sub(r"\s+", "", str(value or "")).upper()
    if not code:
        if required:
            raise AppException("VALIDATION_ERROR", "电子回执编号必填")
        return None
    if not re.fullmatch(r"[A-Z0-9-]{6,64}", code):
        raise AppException("VALIDATION_ERROR", "电子回执编号应为6-64位字母、数字或短横线")
    return code


def _receipt_mask(stored) -> str:
    plain = decrypt_field(stored) if stored else ""
    return f"•••• {plain[-6:]}" if plain else ""


def _loan_file_view(x):
    if not x.receipt_file_id:
        return None
    from app.services import file_service
    return file_service.attachment_view(str(x.receipt_file_id))


def _loan_row(x, s=None, user=None, *, student_view: bool = False) -> dict:
    amount = format(x.amount, ".2f") if student_view and x.amount is not None else _amount_view(x.amount, user or {})
    return {"loanId": str(x.id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "loanType": x.loan_type, "bankName": x.bank_name or "",
            "bankLast4": x.bank_last4 or "", "yearCode": x.year_code or "",
            "amount": amount, "status": x.status,
            "statusLabel": _L_LOAN.get(x.status, x.status), "remark": x.remark or "",
            "receiptCodeMasked": _receipt_mask(x.receipt_code_encrypted),
            "receiptFile": _loan_file_view(x), "reviewOpinion": x.review_opinion or "",
            "reviewer": x.reviewer or "", "submittedAt": _iso(x.submitted_at),
            "returnedAt": _iso(x.returned_at), "verifiedAt": _iso(x.verified_at),
            "confirmedAt": _iso(x.confirmed_at), "withdrawnAt": _iso(x.withdrawn_at),
            "version": int(x.version or 0),
            "allowedActions": (_LOAN_STUDENT_ACTIONS if student_view else _LOAN_STAFF_ACTIONS).get(x.status, [])}


def _loan_policy() -> dict:
    return {"minAmount": "1000.00", "maxAmount": "20000.00", "audience": "全日制高职学生",
            "basis": "2024年秋季起国家助学贷款本专科年度额度政策"}


def loan_policy() -> dict:
    return _loan_policy()


def list_loans(user, status=None, page=1, page_size=50, keyword="", year_code="", loan_type="", record_id=None):
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
        if record_id is not None:
            conds.append(StudentLoan.id == int(record_id))
        if status:
            conds.append(StudentLoan.status == status)
        if year_code:
            conds.append(StudentLoan.year_code == str(year_code).strip())
        if loan_type:
            normalized_type = str(loan_type).upper().strip()
            if normalized_type not in ("ORIGIN", "CAMPUS"):
                raise AppException("VALIDATION_ERROR", "贷款类型非法")
            conds.append(StudentLoan.loan_type == normalized_type)
        term = str(keyword or "").strip()
        if term:
            conds.append(or_(StudentProfile.real_name.contains(term, autoescape=True),
                             StudentProfile.student_no.contains(term, autoescape=True),
                             StudentLoan.bank_name.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count(StudentLoan.id)).select_from(StudentLoan).join(
            StudentProfile, StudentProfile.id == StudentLoan.student_id
        ).where(*conds)) or 0)
        rows = db.execute(select(StudentLoan, StudentProfile).join(
            StudentProfile, StudentProfile.id == StudentLoan.student_id
        ).where(*conds).order_by(StudentLoan.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_loan_row(row, student, user) for row, student in rows], total, status_counts


def _assert_loan_unique(db, student_id: int, year_code: str, *, exclude_id: int | None = None):
    from app.models import StudentLoan
    conds = [StudentLoan.tenant_id == _tid(), StudentLoan.student_id == student_id,
             StudentLoan.year_code == year_code, StudentLoan.is_deleted.is_(False),
             StudentLoan.status != "WITHDRAWN"]
    if exclude_id:
        conds.append(StudentLoan.id != int(exclude_id))
    if db.scalars(select(StudentLoan.id).where(*conds).limit(1)).first():
        raise AppException("DATA_CONFLICT", "该学生本学年已登记国家助学贷款，不能重复或同时登记两种贷款")


def _assert_receipt_unique(db, receipt_hash: str | None, *, exclude_id: int | None = None):
    from app.models import StudentLoan
    if not receipt_hash:
        return
    conds = [StudentLoan.tenant_id == _tid(), StudentLoan.receipt_code_hash == receipt_hash,
             StudentLoan.is_deleted.is_(False), StudentLoan.status != "WITHDRAWN"]
    if exclude_id:
        conds.append(StudentLoan.id != int(exclude_id))
    if db.scalars(select(StudentLoan.id).where(*conds).limit(1)).first():
        raise AppException("DATA_CONFLICT", "该电子回执编号已被使用，请核对后重试")


def _bind_loan_receipt(db, row, file_id, user):
    if file_id in (None, ""):
        return
    normalized = str(file_id).strip()
    if not normalized.isdigit():
        raise AppException("VALIDATION_ERROR", "回执附件编号非法")
    from app.services import file_service
    file_service.bind_file_biz(normalized, "LOAN", str(row.id), user=user, db=db)
    row.receipt_file_id = int(normalized)


def register_loan(body, user, *, student_self: bool = False) -> dict:
    from app.models import StudentLoan, StudentProfile
    sid = int(_loan_body(body, "studentId", 0) or 0)
    ltype = str(_loan_body(body, "loanType", "ORIGIN") or "ORIGIN").upper()
    if ltype not in ("ORIGIN", "CAMPUS"):
        raise AppException("VALIDATION_ERROR", "贷款类型非法")
    amount = _loan_amount(_loan_body(body, "amount"))
    year_code = _loan_year(_loan_body(body, "yearCode"))
    last4 = str(_loan_body(body, "bankLast4") or "").strip()
    if last4 and not re.fullmatch(r"\d{4}", last4):
        raise AppException("VALIDATION_ERROR", "银行卡后4位必须为4位数字")
    bank_name = str(_loan_body(body, "bankName") or "").strip()
    if bank_name and not 2 <= len(bank_name) <= 100:
        raise AppException("VALIDATION_ERROR", "经办银行名称需2-100字")
    code = _receipt_code(_loan_body(body, "receiptCode"), required=student_self)
    if student_self and not bool(_loan_body(body, "confirm", False)):
        raise AppException("VALIDATION_ERROR", "请先确认贷款与回执信息真实")
    with session() as db:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id == sid,
            StudentProfile.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("学生不存在")
        if not student_self:
            _scope_or_403(db, sid, user)
        _assert_loan_unique(db, sid, year_code)
        receipt_hash = hash_sensitive(code, "loan_receipt") if code else None
        _assert_receipt_unique(db, receipt_hash)
        row = StudentLoan(
            tenant_id=_tid(), student_id=sid, loan_type=ltype,
            bank_name=bank_name or None, bank_last4=last4 or None,
            year_code=year_code, amount=amount,
            receipt_code_encrypted=encrypt_field(code), receipt_code_hash=receipt_hash,
            status="RECEIPT" if code else "REGISTERED",
            submitted_at=datetime.utcnow() if code else None,
            remark=str(_loan_body(body, "remark") or "").strip() or None, created_by=_uid(user),
        )
        db.add(row); db.flush()
        _bind_loan_receipt(db, row, _loan_body(body, "receiptFileId"), user)
        _audit(db, row.id, "LOAN_SELF_SUBMIT" if student_self else "LOAN_REGISTER",
               f"type={ltype};year={year_code};receipt={'yes' if code else 'no'}")
        from app.services.affairs_funding_todo_service import sync_loan_todos
        sync_loan_todos(db, row)
        db.commit(); db.refresh(row)
        return _loan_row(row, student, user, student_view=student_self)


def loan_action(loan_id, body, user) -> dict:
    from app.models import StudentLoan, StudentProfile
    action = str(_loan_body(body, "action") or "").upper()
    expected_version = _loan_body(body, "version")
    with session() as db:
        row = db.scalars(select(StudentLoan).where(
            StudentLoan.tenant_id == _tid(), StudentLoan.id == int(loan_id),
            StudentLoan.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("贷款记录不存在")
        _scope_or_403(db, row.student_id, user)
        atomic_claim_version(db, row, expected_version)
        before = row.status
        now = datetime.utcnow()
        if action == "SUBMIT_RECEIPT":
            if before not in ("REGISTERED", "RETURNED"):
                raise AppException("DATA_CONFLICT", "当前状态不能补录回执")
            code = _receipt_code(_loan_body(body, "receiptCode"), required=not bool(row.receipt_code_encrypted))
            if code:
                receipt_hash = hash_sensitive(code, "loan_receipt")
                _assert_receipt_unique(db, receipt_hash, exclude_id=row.id)
                row.receipt_code_encrypted = encrypt_field(code)
                row.receipt_code_hash = receipt_hash
            if _loan_body(body, "amount") not in (None, ""):
                row.amount = _loan_amount(_loan_body(body, "amount"))
            if _loan_body(body, "loanType") not in (None, ""):
                loan_type = str(_loan_body(body, "loanType")).upper()
                if loan_type not in ("ORIGIN", "CAMPUS"):
                    raise AppException("VALIDATION_ERROR", "贷款类型非法")
                row.loan_type = loan_type
            if _loan_body(body, "yearCode") not in (None, ""):
                row.year_code = _loan_year(_loan_body(body, "yearCode"))
                _assert_loan_unique(db, row.student_id, row.year_code, exclude_id=row.id)
            bank_name = str(_loan_body(body, "bankName") or "").strip()
            if bank_name:
                if not 2 <= len(bank_name) <= 100:
                    raise AppException("VALIDATION_ERROR", "经办银行名称需2-100字")
                row.bank_name = bank_name
            last4 = str(_loan_body(body, "bankLast4") or "").strip()
            if last4:
                if not re.fullmatch(r"\d{4}", last4):
                    raise AppException("VALIDATION_ERROR", "银行卡后4位必须为4位数字")
                row.bank_last4 = last4
            _bind_loan_receipt(db, row, _loan_body(body, "receiptFileId"), user)
            row.status, row.submitted_at = "RECEIPT", now
            row.review_opinion = None
            row.returned_at = None
        elif action == "VERIFY":
            if before != "RECEIPT":
                raise AppException("DATA_CONFLICT", "仅待核验回执可执行核验")
            if not row.receipt_code_encrypted:
                raise AppException("DATA_CONFLICT", "电子回执编号缺失，不能核验")
            row.status, row.verified_at = "VERIFIED", now
            row.review_opinion = str(_loan_body(body, "reason") or "").strip() or None
        elif action == "RETURN":
            if before not in ("RECEIPT", "VERIFIED"):
                raise AppException("DATA_CONFLICT", "当前状态不能退回")
            reason = str(_loan_body(body, "reason") or "").strip()
            if not 5 <= len(reason) <= 1000:
                raise AppException("VALIDATION_ERROR", "退回原因需5-1000字")
            row.status, row.review_opinion, row.returned_at = "RETURNED", reason, now
            row.verified_at = None
        elif action == "CONFIRM":
            if before != "VERIFIED":
                raise AppException("DATA_CONFLICT", "仅已核验记录可确认台账")
            row.status, row.confirmed_at = "CONFIRMED", now
        else:
            raise AppException("VALIDATION_ERROR", "贷款办理动作非法")
        operator, _role, _actor = _op()
        row.reviewer = operator
        row.updated_by = _uid(user)
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, f"LOAN_{action}", f"{before}->{row.status}")
        from app.services.affairs_funding_todo_service import sync_loan_todos
        sync_loan_todos(db, row)
        db.commit(); db.refresh(row)
        student = db.get(StudentProfile, int(row.student_id))
        return _loan_row(row, student, user)


def advance_loan(loan_id, user, *, expected_version=None) -> dict:
    """旧客户端兼容：仅保留无需补填资料的核验和确认，登记态必须改用语义动作。"""
    from app.models import StudentLoan
    with session() as db:
        row = db.get(StudentLoan, int(loan_id))
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("贷款记录不存在")
        status = row.status
    action = {"RECEIPT": "VERIFY", "VERIFIED": "CONFIRM"}.get(status)
    if not action:
        raise AppException("DATA_CONFLICT", "请使用补录回执、核验、退回或确认等明确动作")
    return loan_action(loan_id, {"action": action, "version": expected_version}, user)


def student_loans(user) -> dict:
    from app.models import StudentLoan
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        rows = db.scalars(select(StudentLoan).where(
            StudentLoan.tenant_id == _tid(), StudentLoan.student_id == student.id,
            StudentLoan.is_deleted.is_(False),
        ).order_by(StudentLoan.id.desc())).all()
        return {"items": [_loan_row(row, student, user, student_view=True) for row in rows],
                "policy": _loan_policy()}


def submit_loan_self(body, user) -> dict:
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        student_id = int(student.id)
    payload = dict(body or {})
    payload["studentId"] = student_id
    return register_loan(payload, user, student_self=True)


def resubmit_loan_self(loan_id, body, user) -> dict:
    from app.models import StudentLoan, StudentProfile
    from app.services.mobile_affairs_service import _me
    payload = dict(body or {})
    if not bool(payload.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先确认修改后的贷款与回执信息真实")
    with session() as db:
        student = _me(db, user)
        row = db.scalars(select(StudentLoan).where(
            StudentLoan.tenant_id == _tid(), StudentLoan.id == int(loan_id),
            StudentLoan.student_id == student.id, StudentLoan.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("贷款记录不存在或不属于本人")
        atomic_claim_version(db, row, payload.get("version"))
        if row.status not in ("REGISTERED", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前记录不能补充或重提回执")
        code = _receipt_code(payload.get("receiptCode"), required=not bool(row.receipt_code_encrypted))
        if code:
            receipt_hash = hash_sensitive(code, "loan_receipt")
            _assert_receipt_unique(db, receipt_hash, exclude_id=row.id)
            row.receipt_code_encrypted = encrypt_field(code)
            row.receipt_code_hash = receipt_hash
        row.amount = _loan_amount(payload.get("amount", row.amount))
        loan_type = str(payload.get("loanType") or row.loan_type).upper()
        if loan_type not in ("ORIGIN", "CAMPUS"):
            raise AppException("VALIDATION_ERROR", "贷款类型非法")
        row.loan_type = loan_type
        row.year_code = _loan_year(payload.get("yearCode") or row.year_code)
        _assert_loan_unique(db, row.student_id, row.year_code, exclude_id=row.id)
        bank_name = str(payload.get("bankName") or row.bank_name or "").strip()
        if bank_name and not 2 <= len(bank_name) <= 100:
            raise AppException("VALIDATION_ERROR", "经办银行名称需2-100字")
        row.bank_name = bank_name or None
        last4 = str(payload.get("bankLast4") or row.bank_last4 or "").strip()
        if last4 and not re.fullmatch(r"\d{4}", last4):
            raise AppException("VALIDATION_ERROR", "银行卡后4位必须为4位数字")
        row.bank_last4 = last4 or None
        _bind_loan_receipt(db, row, payload.get("receiptFileId"), user)
        before = row.status
        row.status, row.submitted_at = "RECEIPT", datetime.utcnow()
        row.review_opinion, row.returned_at = None, None
        row.updated_by = _uid(user)
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "LOAN_SELF_RESUBMIT", f"{before}->RECEIPT")
        from app.services.affairs_funding_todo_service import sync_loan_todos
        sync_loan_todos(db, row)
        db.commit(); db.refresh(row)
        return _loan_row(row, db.get(StudentProfile, int(row.student_id)), user, student_view=True)


def withdraw_loan_self(loan_id, body, user) -> dict:
    from app.models import StudentLoan, StudentProfile
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        row = db.scalars(select(StudentLoan).where(
            StudentLoan.tenant_id == _tid(), StudentLoan.id == int(loan_id),
            StudentLoan.student_id == student.id, StudentLoan.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("贷款记录不存在或不属于本人")
        atomic_claim_version(db, row, _loan_body(body, "version"))
        if row.status != "RECEIPT":
            raise AppException("DATA_CONFLICT", "仅学校核验前的回执可撤回")
        row.status, row.withdrawn_at = "WITHDRAWN", datetime.utcnow()
        row.review_opinion = "学生本人撤回"
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "LOAN_SELF_WITHDRAW", "RECEIPT->WITHDRAWN")
        from app.services.affairs_funding_todo_service import sync_loan_todos
        sync_loan_todos(db, row)
        db.commit(); db.refresh(row)
        return _loan_row(row, db.get(StudentProfile, int(row.student_id)), user, student_view=True)


# ═══════════ 减免与临时补助 ═══════════

_L_FEE = {
    "SUBMITTED": "待审核", "RETURNED": "待补正", "APPROVED": "已批准",
    "REJECTED": "未通过", "ISSUED": "已落实", "WITHDRAWN": "已撤回",
}
_FEE_STAFF_ACTIONS = {"SUBMITTED": ["APPROVE", "RETURN", "REJECT"], "APPROVED": ["FULFILL"]}
_FEE_STUDENT_ACTIONS = {"SUBMITTED": ["WITHDRAW"], "RETURNED": ["RESUBMIT"]}
_FEE_CATEGORIES = {
    "REDUCTION": {"SPECIAL_IDENTITY", "EXTREME_DIFFICULTY", "OTHER"},
    "TEMP_AID": {"SERIOUS_ILLNESS", "DISASTER", "FAMILY_CHANGE", "ACCIDENT", "OTHER"},
}


def _fee_year(value) -> str:
    if value in (None, ""):
        now = datetime.now()
        start = now.year if now.month >= 8 else now.year - 1
        value = f"{start}-{start + 1}"
    year = str(value).strip()
    match = re.fullmatch(r"(\d{4})-(\d{4})", year)
    if not match or int(match.group(2)) != int(match.group(1)) + 1:
        raise AppException("VALIDATION_ERROR", "申请学年格式应为连续的 YYYY-YYYY")
    return year


def _fee_type(value) -> str:
    item_type = str(value or "REDUCTION").upper().strip()
    if item_type not in _FEE_CATEGORIES:
        raise AppException("VALIDATION_ERROR", "申请类型非法")
    return item_type


def _fee_category(item_type: str, value) -> str:
    category = str(value or "OTHER").upper().strip()
    if category not in _FEE_CATEGORIES[item_type]:
        raise AppException("VALIDATION_ERROR", "困难原因类别非法")
    return category


def _fee_status_label(x) -> str:
    if x.status != "ISSUED":
        return _L_FEE.get(x.status, x.status)
    return "减免已确认" if x.item_type == "REDUCTION" else "补助已发放"


def _fee_attachment_ids(value) -> list[str]:
    raw = value if isinstance(value, list) else []
    ids = []
    for item in raw:
        normalized = str(item or "").strip()
        if not normalized.isdigit():
            raise AppException("VALIDATION_ERROR", "证明材料编号非法")
        if normalized not in ids:
            ids.append(normalized)
    if len(ids) > 5:
        raise AppException("VALIDATION_ERROR", "证明材料最多5份")
    return ids


def _fee_evidence(db, fee_id) -> list[dict]:
    from app.models.file import FileBinding
    from app.services import file_service
    ids = db.scalars(select(FileBinding.file_id).where(
        FileBinding.tenant_id == _tid(), FileBinding.biz_type == "REDUCTION",
        FileBinding.biz_id == str(fee_id), FileBinding.relation_type == "BUSINESS_EVIDENCE",
        FileBinding.status == "ACTIVE", FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.id)).all()
    return [view for view in (file_service.attachment_view(str(fid)) for fid in ids) if view]


def _bind_fee_evidence(db, row, file_ids: list[str], student, user) -> None:
    if not file_ids:
        return
    from app.models.file import FileBinding
    from app.services import file_business_binding_service as binding_service
    current = {str(value) for value in db.scalars(select(FileBinding.file_id).where(
        FileBinding.tenant_id == _tid(), FileBinding.biz_type == "REDUCTION",
        FileBinding.biz_id == str(row.id), FileBinding.relation_type == "BUSINESS_EVIDENCE",
        FileBinding.status == "ACTIVE", FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    )).all()}
    if len(current.union(file_ids)) > 5:
        raise AppException("VALIDATION_ERROR", "同一申请累计最多保留5份证明材料")
    for file_id in file_ids:
        binding_service.bind_file_to_business(
            db, file_id=file_id, biz_type="REDUCTION", biz_id=row.id, actor=user,
            subject_type="STUDENT", subject_id=student.id, relation_type="BUSINESS_EVIDENCE",
            module_code="STUDENT_AFFAIRS", student_id=student.id,
            college_id=getattr(student, "college_id", None), class_id=getattr(student, "class_id", None),
            scope={"studentId": str(student.id), "itemType": row.item_type,
                   "yearCode": row.year_code or ""},
        )


def _fee_policy() -> dict:
    return {
        "maxEvidenceCount": 5,
        "categories": {
            "REDUCTION": ["SPECIAL_IDENTITY", "EXTREME_DIFFICULTY", "OTHER"],
            "TEMP_AID": ["SERIOUS_ILLNESS", "DISASTER", "FAMILY_CHANGE", "ACCIDENT", "OTHER"],
        },
    }


def _fee_row(x, s=None, user=None, *, student_view: bool = False, db=None) -> dict:
    amount = format(x.amount, ".2f") if student_view and x.amount is not None else _amount_view(x.amount, user or {})
    return {"feeId": str(x.id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "itemType": x.item_type, "yearCode": x.year_code or "",
            "reasonCategory": x.reason_category or "OTHER", "amount": amount,
            "reason": x.reason or "", "status": x.status, "statusLabel": _fee_status_label(x),
            "reviewOpinion": x.review_opinion or "", "reviewer": x.reviewer or "",
            "fulfillmentChannel": x.fulfillment_channel or "",
            "fulfillmentReference": x.fulfillment_reference or "",
            "submittedAt": _iso(x.submitted_at), "returnedAt": _iso(x.returned_at),
            "reviewedAt": _iso(x.reviewed_at), "issuedAt": _iso(x.issued_at),
            "withdrawnAt": _iso(x.withdrawn_at), "version": int(x.version or 0),
            "evidence": _fee_evidence(db, x.id) if db is not None else [],
            "allowedActions": (_FEE_STUDENT_ACTIONS if student_view else _FEE_STAFF_ACTIONS).get(x.status, [])}


def list_reductions(user, itemType=None, status=None, page=1, page_size=50,
                    keyword="", year_code="", record_id=None):
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
        if record_id is not None:
            conds.append(FeeReduction.id == record_id)
        if itemType:
            conds.append(FeeReduction.item_type == _fee_type(itemType))
        if status:
            conds.append(FeeReduction.status == status)
        if year_code:
            conds.append(FeeReduction.year_code == _fee_year(year_code))
        term = str(keyword or "").strip()
        if term:
            conds.append(or_(StudentProfile.real_name.contains(term, autoescape=True),
                             StudentProfile.student_no.contains(term, autoescape=True),
                             FeeReduction.reason.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count(FeeReduction.id)).select_from(FeeReduction).join(
            StudentProfile, StudentProfile.id == FeeReduction.student_id
        ).where(*conds)) or 0)
        rows = db.execute(select(FeeReduction, StudentProfile).join(
            StudentProfile, StudentProfile.id == FeeReduction.student_id
        ).where(*conds).order_by(FeeReduction.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_fee_row(row, student, user, db=db) for row, student in rows], total, status_counts


def _assert_fee_unique(db, student_id: int, item_type: str, year_code: str, *, exclude_id=None):
    from app.models import FeeReduction
    active_statuses = ["SUBMITTED", "RETURNED", "APPROVED"]
    if item_type == "REDUCTION":
        active_statuses.append("ISSUED")
    conds = [FeeReduction.tenant_id == _tid(), FeeReduction.student_id == int(student_id),
             FeeReduction.item_type == item_type, FeeReduction.year_code == year_code,
             FeeReduction.status.in_(active_statuses), FeeReduction.is_deleted.is_(False)]
    if exclude_id:
        conds.append(FeeReduction.id != int(exclude_id))
    if db.scalars(select(FeeReduction.id).where(*conds).limit(1)).first():
        label = "学费减免" if item_type == "REDUCTION" else "临时困难补助"
        raise AppException("DATA_CONFLICT", f"该学生本学年已有办理中的{label}申请")


def submit_reduction(body, user, *, student_self: bool = False) -> dict:
    from app.models import FeeReduction, StudentProfile
    sid = int(_loan_body(body, "studentId", 0) or 0)
    item_type = _fee_type(_loan_body(body, "itemType", "REDUCTION"))
    year_code = _fee_year(_loan_body(body, "yearCode"))
    category = _fee_category(item_type, _loan_body(body, "reasonCategory", "OTHER"))
    reason = str(_loan_body(body, "reason", "") or "").strip()
    if not 10 <= len(reason) <= 1000:
        raise AppException("VALIDATION_ERROR", "申请理由需10-1000字")
    amount = _money(_loan_body(body, "amount"), "减免/补助金额", required=True)
    if amount <= 0:
        raise AppException("VALIDATION_ERROR", "减免/补助金额必须大于0")
    file_ids = _fee_attachment_ids(_loan_body(body, "attachmentIds", []))
    if student_self and not file_ids:
        raise AppException("VALIDATION_ERROR", "请至少提交1份困难证明材料")
    if student_self and not bool(_loan_body(body, "confirm", False)):
        raise AppException("VALIDATION_ERROR", "请先确认申请信息和材料真实")
    with session() as db:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id == sid,
            StudentProfile.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("学生不存在")
        if not student_self:
            _scope_or_403(db, sid, user)
        _assert_fee_unique(db, sid, item_type, year_code)
        row = FeeReduction(
            tenant_id=_tid(), student_id=sid, item_type=item_type,
            year_code=year_code, reason_category=category, amount=amount,
            reason=reason, status="SUBMITTED", submitted_at=datetime.utcnow(), created_by=_uid(user),
        )
        db.add(row); db.flush()
        _bind_fee_evidence(db, row, file_ids, student, user)
        _audit(db, row.id, "FEE_SELF_SUBMIT" if student_self else "FEE_SUBMIT",
               f"type={item_type};year={year_code};files={len(file_ids)}")
        from app.services.affairs_funding_todo_service import sync_reduction_todos
        sync_reduction_todos(db, row)
        db.commit(); db.refresh(row)
        return _fee_row(row, student, user, student_view=student_self, db=db)


def fee_action(fee_id, body, user) -> dict:
    """学校经办语义动作：批准、退回、驳回和结果落实。"""
    from app.models import FeeReduction, StudentProfile
    action = str(_loan_body(body, "action", "") or "").upper()
    opinion = str(_loan_body(body, "opinion", _loan_body(body, "reason", "")) or "").strip()
    with session() as db:
        x = db.scalars(select(FeeReduction).where(
            FeeReduction.tenant_id == _tid(), FeeReduction.id == int(fee_id),
            FeeReduction.is_deleted.is_(False),
        ).with_for_update()).first()
        if not x:
            raise not_found("记录不存在")
        _scope_or_403(db, x.student_id, user)
        atomic_claim_version(db, x, _loan_body(body, "version"))
        before, now = x.status, datetime.utcnow()
        if action == "APPROVE":
            if before != "SUBMITTED":
                raise AppException("DATA_CONFLICT", "仅待审核申请可批准")
            x.status, x.reviewed_at, x.returned_at = "APPROVED", now, None
        elif action in ("RETURN", "REJECT"):
            if before != "SUBMITTED":
                raise AppException("DATA_CONFLICT", "仅待审核申请可退回或驳回")
            if not 5 <= len(opinion) <= 1000:
                raise AppException("VALIDATION_ERROR", "处理意见需5-1000字")
            x.status = "RETURNED" if action == "RETURN" else "REJECTED"
            x.returned_at = now if action == "RETURN" else None
            x.reviewed_at = now
        elif action in ("FULFILL", "ISSUE"):
            if before != "APPROVED":
                raise AppException("DATA_CONFLICT", "仅已批准申请可落实结果")
            default_channel = "TUITION_LEDGER" if x.item_type == "REDUCTION" else "BANK_TRANSFER"
            channel = str(_loan_body(body, "fulfillmentChannel", default_channel) or default_channel).upper()
            allowed = {"TUITION_LEDGER"} if x.item_type == "REDUCTION" else {"BANK_TRANSFER", "OTHER"}
            if channel not in allowed:
                raise AppException("VALIDATION_ERROR", "结果落实方式与申请类型不匹配")
            reference = str(_loan_body(body, "fulfillmentReference", "") or "").strip()
            if len(reference) > 200:
                raise AppException("VALIDATION_ERROR", "结果凭证摘要最多200字")
            x.status, x.issued_at = "ISSUED", now
            x.fulfillment_channel, x.fulfillment_reference = channel, reference or None
        else:
            raise AppException("VALIDATION_ERROR", "减免/补助办理动作非法")
        if action not in ("FULFILL", "ISSUE"):
            x.review_opinion = opinion or None
        x.reviewer, x.updated_by = _op()[0], _uid(user)
        x.version = int(x.version or 0) + 1
        _audit(db, x.id, "FEE_" + ("FULFILL" if action == "ISSUE" else action),
               f"{before}->{x.status}")
        from app.services.affairs_funding_todo_service import sync_reduction_todos
        sync_reduction_todos(db, x)
        db.commit(); db.refresh(x)
        s = db.get(StudentProfile, int(x.student_id))
        return _fee_row(x, s, user, db=db)


def review_reduction(fee_id, body, user) -> dict:
    return fee_action(fee_id, body, user)


def issue_reduction(fee_id, user, *, expected_version=None) -> dict:
    return fee_action(fee_id, {"action": "FULFILL", "version": expected_version}, user)


def student_reductions(user) -> dict:
    from app.models import FeeReduction
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        rows = db.scalars(select(FeeReduction).where(
            FeeReduction.tenant_id == _tid(), FeeReduction.student_id == student.id,
            FeeReduction.is_deleted.is_(False),
        ).order_by(FeeReduction.id.desc())).all()
        return {"items": [_fee_row(row, student, user, student_view=True, db=db) for row in rows],
                "policy": _fee_policy()}


def submit_reduction_self(body, user) -> dict:
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        student_id = int(student.id)
    payload = dict(body or {})
    payload["studentId"] = student_id
    return submit_reduction(payload, user, student_self=True)


def resubmit_reduction_self(fee_id, body, user) -> dict:
    from app.models import FeeReduction, StudentProfile
    from app.services.mobile_affairs_service import _me
    payload = dict(body or {})
    if not bool(payload.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先确认补正信息和材料真实")
    with session() as db:
        student = _me(db, user)
        row = db.scalars(select(FeeReduction).where(
            FeeReduction.tenant_id == _tid(), FeeReduction.id == int(fee_id),
            FeeReduction.student_id == student.id, FeeReduction.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("申请不存在或不属于本人")
        atomic_claim_version(db, row, payload.get("version"))
        if row.status != "RETURNED":
            raise AppException("DATA_CONFLICT", "仅退回申请可补正重提")
        item_type = _fee_type(payload.get("itemType") or row.item_type)
        year_code = _fee_year(payload.get("yearCode") or row.year_code)
        reason = str(payload.get("reason") or row.reason or "").strip()
        if not 10 <= len(reason) <= 1000:
            raise AppException("VALIDATION_ERROR", "申请理由需10-1000字")
        amount = _money(payload.get("amount", row.amount), "减免/补助金额", required=True)
        if amount is None or amount <= 0:
            raise AppException("VALIDATION_ERROR", "减免/补助金额必须大于0")
        category = _fee_category(item_type, payload.get("reasonCategory") or row.reason_category)
        file_ids = _fee_attachment_ids(payload.get("attachmentIds", []))
        _assert_fee_unique(db, student.id, item_type, year_code, exclude_id=row.id)
        row.item_type, row.year_code, row.reason_category = item_type, year_code, category
        row.amount, row.reason = amount, reason
        _bind_fee_evidence(db, row, file_ids, student, user)
        from app.models.file import FileBinding
        evidence_count = int(db.scalar(select(func.count(FileBinding.id)).where(
            FileBinding.tenant_id == _tid(), FileBinding.biz_type == "REDUCTION",
            FileBinding.biz_id == str(row.id), FileBinding.relation_type == "BUSINESS_EVIDENCE",
            FileBinding.status == "ACTIVE", FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        )) or 0)
        if evidence_count < 1:
            raise AppException("VALIDATION_ERROR", "请至少保留1份困难证明材料")
        before = row.status
        row.status, row.submitted_at, row.returned_at = "SUBMITTED", datetime.utcnow(), None
        row.review_opinion, row.updated_by = None, _uid(user)
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "FEE_SELF_RESUBMIT", f"{before}->SUBMITTED;files={len(file_ids)}")
        from app.services.affairs_funding_todo_service import sync_reduction_todos
        sync_reduction_todos(db, row)
        db.commit(); db.refresh(row)
        return _fee_row(row, db.get(StudentProfile, int(row.student_id)), user, student_view=True, db=db)


def withdraw_reduction_self(fee_id, body, user) -> dict:
    from app.models import FeeReduction, StudentProfile
    from app.services.mobile_affairs_service import _me
    with session() as db:
        student = _me(db, user)
        row = db.scalars(select(FeeReduction).where(
            FeeReduction.tenant_id == _tid(), FeeReduction.id == int(fee_id),
            FeeReduction.student_id == student.id, FeeReduction.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("申请不存在或不属于本人")
        atomic_claim_version(db, row, _loan_body(body, "version"))
        if row.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        row.status, row.withdrawn_at = "WITHDRAWN", datetime.utcnow()
        row.review_opinion, row.updated_by = "学生本人撤回", _uid(user)
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "FEE_SELF_WITHDRAW", "SUBMITTED->WITHDRAWN")
        from app.services.affairs_funding_todo_service import sync_reduction_todos
        sync_reduction_todos(db, row)
        db.commit(); db.refresh(row)
        return _fee_row(row, db.get(StudentProfile, int(row.student_id)), user, student_view=True, db=db)


# ═══════════ 勤工月度考核（月度考核→累计补贴）═══════════

_L_RATING = {"GOOD": "优", "PASS": "合格", "FAIL": "不合格"}


def _monthly_row(m, user=None, *, exact_amount: bool = False) -> dict:
    subsidy_amount = (format(m.subsidy_amount, ".2f") if exact_amount and m.subsidy_amount is not None
                      else _amount_view(m.subsidy_amount, user or {}))
    return {"monthlyId": str(m.id), "recordId": str(m.record_id), "studentId": str(m.student_id),
            "monthCode": m.month_code, "workHours": float(m.work_hours) if m.work_hours is not None else None,
            "rating": m.rating, "ratingLabel": _L_RATING.get(m.rating, m.rating),
            "subsidyAmount": subsidy_amount, "remark": m.remark or ""}


def add_monthly(record_id, body, user) -> dict:
    """仅在岗记录可写入；同月唯一，金额与累计值均采用锁和定点数。"""
    from app.models import WorkStudyMonthly, WorkStudyPost, WorkStudyRecord
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
        post = db.scalars(select(WorkStudyPost).where(
            WorkStudyPost.tenant_id == _tid(), WorkStudyPost.id == int(record.post_id),
            WorkStudyPost.is_deleted.is_(False),
        ).with_for_update()).first()
        if not post:
            raise AppException("DATA_CONFLICT", "岗位不存在")
        recorded_hours = Decimal(str(db.scalar(select(func.coalesce(func.sum(WorkStudyMonthly.work_hours), 0)).where(
            WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.student_id == record.student_id,
            WorkStudyMonthly.month_code == month, WorkStudyMonthly.is_deleted.is_(False),
        )) or 0))
        limit = min(Decimal("40"), Decimal(str(post.monthly_hours_limit or 40)))
        if recorded_hours + hours > limit:
            raise AppException("DATA_CONFLICT", f"该生本月累计工时不能超过{format(limit, '.2f')}小时")
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
        exact_amount = str((user or {}).get("currentRoleCode") or "").upper() == "STUDENT"
        return [_monthly_row(row, user, exact_amount=exact_amount) for row in rows]
