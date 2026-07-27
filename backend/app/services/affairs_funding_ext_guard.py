"""勤工助学/贷款/减免安全门：状态动作、容量、金额精度、范围与并发累计。"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_INSTALLED = False
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


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import StudentProfile, WorkStudyMonthly, WorkStudyPost, WorkStudyRecord
    from app.services import affairs_funding_ext_service as service

    old_post_row = service._post_row
    old_ws_row = service._ws_row
    old_loan_row = service._loan_row
    old_fee_row = service._fee_row
    old_create_post = service.create_post
    old_register_loan = service.register_loan
    old_submit_reduction = service.submit_reduction

    def post_row(row):
        data = old_post_row(row)
        data["version"] = int(row.version or 0)
        return data

    def ws_row(row, student=None, user=None):
        data = old_ws_row(row, student, user)
        data["version"] = int(row.version or 0)
        data["allowedActions"] = {
            "APPLIED": ["APPROVE", "REJECT"],
            "APPROVED": ["ONBOARD", "TERMINATE"],
            "ONBOARD": ["TERMINATE"],
        }.get(row.status, [])
        return data

    def loan_row(row, student=None, user=None):
        data = old_loan_row(row, student, user)
        data["version"] = int(row.version or 0)
        data["allowedActions"] = ["ADVANCE"] if row.status in service._LOAN_NEXT else []
        return data

    def fee_row(row, student=None, user=None):
        data = old_fee_row(row, student, user)
        data["version"] = int(row.version or 0)
        data["allowedActions"] = {
            "SUBMITTED": ["APPROVE", "REJECT"],
            "APPROVED": ["ISSUE"],
        }.get(row.status, [])
        return data

    def create_post(body, user):
        salary = _money(getattr(body, "salary", None), "岗位薪酬")
        headcount = getattr(body, "headcount", None)
        if headcount not in (None, ""):
            try:
                headcount = int(headcount)
            except (TypeError, ValueError) as exc:
                raise AppException("VALIDATION_ERROR", "需求人数必须为整数") from exc
            if headcount < 1 or headcount > 10000:
                raise AppException("VALIDATION_ERROR", "需求人数应为1-10000")
        body.salary, body.headcount = salary, headcount
        return old_create_post(body, user)

    def register_loan(body, user):
        amount = _money(getattr(body, "amount", None), "贷款金额", required=True)
        last4 = str(getattr(body, "bankLast4", None) or "").strip()
        if last4 and not re.fullmatch(r"\d{4}", last4):
            raise AppException("VALIDATION_ERROR", "银行卡后4位必须为4位数字")
        body.amount, body.bankLast4 = amount, last4 or None
        return old_register_loan(body, user)

    def submit_reduction(body, user):
        amount = _money(getattr(body, "amount", None), "减免/补助金额", required=True)
        if amount <= 0:
            raise AppException("VALIDATION_ERROR", "减免/补助金额必须大于0")
        body.amount = amount
        return old_submit_reduction(body, user)

    def act_work_study(record_id, action, user, reason="", *, expected_version=None):
        action = str(action or "").upper()
        with session() as db:
            record = db.scalars(select(WorkStudyRecord).where(
                WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.id == int(record_id),
                WorkStudyRecord.is_deleted.is_(False),
            ).with_for_update()).first()
            if not record:
                raise AppException("DATA_NOT_FOUND", "上岗记录不存在")
            service._scope_or_403(db, record.student_id, user)
            service.atomic_claim_version(db, record, expected_version)
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
                occupied = db.scalar(select(func.count()).select_from(WorkStudyRecord).where(
                    WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.post_id == post.id,
                    WorkStudyRecord.status.in_(("APPROVED", "ONBOARD")),
                    WorkStudyRecord.is_deleted.is_(False),
                )) or 0
                if post.headcount is not None and int(occupied) >= int(post.headcount):
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
                if len(text) < 5 or len(text) > 500:
                    raise AppException("VALIDATION_ERROR", "终止原因需5-500字")
                record.status, record.terminated_at, record.remark = "TERMINATED", datetime.utcnow(), text
            else:
                raise AppException("VALIDATION_ERROR", "动作非法")
            record.version = int(record.version or 0) + 1
            service._audit(db, record.id, "WS_" + action, f"{before}->{record.status}")
            db.commit(); db.refresh(record)
            student = db.get(StudentProfile, int(record.student_id))
            return ws_row(record, student, user)

    def add_monthly(record_id, body, user):
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
                raise AppException("DATA_NOT_FOUND", "上岗记录不存在")
            service._scope_or_403(db, record.student_id, user)
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
                created_by=service._uid(user),
            )
            db.add(monthly)
            record.subsidy_total = (Decimal(str(record.subsidy_total or 0)) + amount).quantize(Decimal("0.01"))
            if record.subsidy_total > _MAX_AMOUNT:
                raise AppException("DATA_CONFLICT", "累计补贴超过金额上限")
            record.version = int(record.version or 0) + 1
            service._audit(db, record.id, "WS_MONTHLY", f"{month}:{rating}:{amount}")
            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise AppException("DATA_CONFLICT", "该月已考核") from exc
            db.refresh(monthly)
            return service._monthly_row(monthly, user)

    def list_monthly(record_id, user):
        with session() as db:
            record = service._load_ws(db, record_id)
            service._scope_or_403(db, record.student_id, user)
            rows = db.scalars(select(WorkStudyMonthly).where(
                WorkStudyMonthly.tenant_id == _tid(), WorkStudyMonthly.record_id == int(record_id),
                WorkStudyMonthly.is_deleted.is_(False),
            ).order_by(WorkStudyMonthly.month_code.desc())).all()
            return [service._monthly_row(row, user) for row in rows]

    service._post_row = post_row
    service._ws_row = ws_row
    service._loan_row = loan_row
    service._fee_row = fee_row
    service.create_post = create_post
    service.register_loan = register_loan
    service.submit_reduction = submit_reduction
    service.act_work_study = act_work_study
    service.add_monthly = add_monthly
    service.list_monthly = list_monthly
    _INSTALLED = True
