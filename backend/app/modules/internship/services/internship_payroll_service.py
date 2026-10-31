"""Yiyang C05/G13 monthly payroll statements with immutable correction versions."""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipApplication,
    InternshipAuditTrail,
    InternshipPayrollStatement,
    InternshipPayrollVersion,
)
from app.modules.internship.services.internship_scope import assert_internship_record_scope
from app.modules.internship.services.internship_student_context_guard import require_explicit_context, require_expected_version
from app.services import file_access_service, file_business_binding_service
from app.services.db_service import _as_id, _tid, session

_MONTH = re.compile(r"^(20\d{2})-(0[1-9]|1[0-2])$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


def _op(user):
    return str((user or {}).get("realName") or "系统")


def _money(value, label="实发金额") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label}必须是合法金额") from None
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise AppException("VALIDATION_ERROR", f"{label}超出允许范围")
    return amount.quantize(Decimal("0.01"))


def _date_value(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise AppException("VALIDATION_ERROR", "发薪日期格式必须为 YYYY-MM-DD") from None


def _current(db, statement, *, lock=False):
    if not statement.current_version_id:
        return None
    query = select(InternshipPayrollVersion).where(InternshipPayrollVersion.id == statement.current_version_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if not row or row.tenant_id != _tid() or row.statement_id != statement.id or row.is_deleted or not row.is_current:
        return None
    return row


def _agreed_salary_snapshot(db, record_id):
    row = db.scalar(select(InternshipApplication).where(
        InternshipApplication.tenant_id == _tid(),
        InternshipApplication.record_id == int(record_id),
        InternshipApplication.status == "APPROVED",
        InternshipApplication.agreed_salary.is_not(None),
        InternshipApplication.is_deleted.is_(False),
    ).order_by(
        InternshipApplication.reviewed_at.desc(),
        InternshipApplication.id.desc(),
    ).limit(1))
    return _money(row.agreed_salary, "约定报酬") if row and row.agreed_salary is not None else None


def _version_view(row):
    return {
        "id": str(row.id),
        "revisionNo": int(row.revision_no),
        "actualAmount": float(row.actual_amount),
        "currency": row.currency,
        "paidOn": row.paid_on.isoformat() if row.paid_on else "",
        "evidenceFileId": str(row.evidence_file_id or ""),
        "evidenceSha256": row.evidence_sha256 or "",
        "submitNote": row.submit_note or "",
        "correctionReason": row.correction_reason or "",
        "status": row.status,
        "statusLabel": {
            "SUBMITTED": "待审核",
            "APPROVED": "已确认",
            "RETURNED": "已退回",
            "SUPERSEDED": "历史版本",
        }.get(row.status, row.status),
        "isCurrent": bool(row.is_current),
        "submittedAt": row.submitted_at.isoformat() + "Z" if row.submitted_at else "",
        "reviewedBy": row.reviewed_by_name or "",
        "reviewedAt": row.reviewed_at.isoformat() + "Z" if row.reviewed_at else "",
        "reviewComment": row.review_comment or "",
        "version": int(row.version or 0),
    }


def _view(db, statement, include_history=True, current=None):
    current = current if current is not None else _current(db, statement)
    versions = []
    if include_history:
        rows = db.scalars(select(InternshipPayrollVersion).where(
            InternshipPayrollVersion.tenant_id == _tid(),
            InternshipPayrollVersion.statement_id == statement.id,
            InternshipPayrollVersion.is_deleted.is_(False),
        ).order_by(InternshipPayrollVersion.revision_no.desc())).all()
        versions = [_version_view(row) for row in rows]
    return {
        "id": str(statement.id),
        "internshipId": str(statement.internship_id),
        "studentId": str(statement.student_id),
        "batchId": str(statement.batch_id),
        "payMonth": statement.pay_month,
        "agreedSalary": float(statement.agreed_salary_snapshot) if statement.agreed_salary_snapshot is not None else None,
        "agreedSalaryCurrency": statement.agreed_salary_currency,
        "revisionCount": int(statement.revision_count or 0),
        "current": _version_view(current) if current else None,
        "history": versions,
        "version": int(statement.version or 0),
    }


def _trail(db, statement, action, detail, user):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=statement.id,
        target_type="PAYROLL",
        action=action,
        operator_name=_op(user),
        detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def list_my(user: dict, *, batch_id, internship_id):
    with session() as db:
        record, _student, _batch = require_explicit_context(
            db, user, {"batchId": batch_id, "internshipId": internship_id}, for_write=False)
        rows = db.scalars(select(InternshipPayrollStatement).where(
            InternshipPayrollStatement.tenant_id == _tid(),
            InternshipPayrollStatement.internship_id == record.id,
            InternshipPayrollStatement.is_deleted.is_(False),
        ).order_by(InternshipPayrollStatement.pay_month.desc())).all()
        return [_view(db, row) for row in rows]


def submit_my(user: dict, body: dict):
    payload = body or {}
    month = str(payload.get("payMonth") or "").strip()
    if not _MONTH.fullmatch(month):
        raise AppException("VALIDATION_ERROR", "工资月份格式必须为 YYYY-MM")
    amount = _money(payload.get("actualAmount"))
    currency = str(payload.get("currency") or "CNY").strip().upper()
    if not _CURRENCY.fullmatch(currency):
        raise AppException("VALIDATION_ERROR", "币种必须使用3位大写代码，如 CNY、USD、JPY")
    paid_on = _date_value(payload.get("paidOn"))
    file_id = str(payload.get("evidenceFileId") or "").strip()
    if not file_id:
        raise AppException("VALIDATION_ERROR", "请上传工资单或工资到账凭证照片")

    with session() as db:
        record, student, _batch = require_explicit_context(db, user, payload, for_write=True)
        year, month_no = [int(part) for part in month.split("-", 1)]
        month_start = date(year, month_no, 1)
        month_end = date(year, month_no, calendar.monthrange(year, month_no)[1])
        intern_start = record.intern_start_date.date() if record.intern_start_date else None
        intern_end = record.intern_end_date.date() if record.intern_end_date else None
        if intern_start and month_end < intern_start or intern_end and month_start > intern_end:
            raise AppException("VALIDATION_ERROR", "工资月份必须落在当前实习周期内")
        statement = db.scalar(select(InternshipPayrollStatement).where(
            InternshipPayrollStatement.tenant_id == _tid(),
            InternshipPayrollStatement.internship_id == record.id,
            InternshipPayrollStatement.pay_month == month,
            InternshipPayrollStatement.is_deleted.is_(False),
        ).with_for_update())
        if statement is None:
            statement = InternshipPayrollStatement(
                tenant_id=_tid(),
                internship_id=record.id,
                student_id=student.id,
                batch_id=record.batch_id,
                pay_month=month,
                agreed_salary_snapshot=_agreed_salary_snapshot(db, record.id),
                agreed_salary_currency="CNY",
                revision_count=0,
            )
            db.add(statement)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                raise AppException("DATA_CONFLICT", "该月份工资单刚被其他请求创建，请刷新后重试") from None
        elif statement.student_id != student.id or statement.batch_id != record.batch_id:
            raise AppException("DATA_CONFLICT", "工资单上下文与当前实习记录不一致")

        current = _current(db, statement, lock=True)
        if current:
            require_expected_version(payload.get("expectedVersion"), statement.version, entity_name="工资单")
        correction_reason = str(payload.get("correctionReason") or "").strip()
        if current and current.status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该月份已有待审核工资单，请等待处理后再更正")
        if current and len(correction_reason) < 5:
            raise AppException("VALIDATION_ERROR", "更正已有月份工资单时必须填写不少于5字的更正原因")

        file_obj = file_access_service.require_file_access(file_id, user=user, action="bind")
        if not str(file_obj.mime_type or "").lower().startswith("image/"):
            raise AppException("VALIDATION_ERROR", "工资凭证必须是图片")

        if current:
            current.is_current = False
            current.status = "SUPERSEDED"
            current.version = int(current.version or 0) + 1

        revision_no = int(statement.revision_count or 0) + 1
        version = InternshipPayrollVersion(
            tenant_id=_tid(),
            statement_id=statement.id,
            revision_no=revision_no,
            actual_amount=amount,
            currency=currency,
            paid_on=paid_on,
            evidence_file_id=int(file_obj.id),
            evidence_sha256=file_obj.sha256,
            submit_note=str(payload.get("submitNote") or "").strip()[:500] or None,
            correction_reason=correction_reason or None,
            status="SUBMITTED",
            is_current=True,
            submitted_at=datetime.utcnow(),
        )
        db.add(version)
        db.flush()
        file_business_binding_service.bind_file_to_business(
            db,
            file_id=file_obj.id,
            biz_type="INTERNSHIP_PAYROLL_VERSION",
            biz_id=version.id,
            actor=user or {},
            subject_type="STUDENT",
            subject_id=student.id,
            relation_type="BUSINESS_EVIDENCE",
            module_code="INTERNSHIP",
            student_id=student.id,
            batch_id=str(record.batch_id),
            college_id=student.college_id,
            class_id=student.class_id,
            scope={
                "internshipId": str(record.id),
                "studentId": str(student.id),
                "batchId": str(record.batch_id),
                "payMonth": month,
                "revisionNo": revision_no,
            },
        )
        statement.current_version_id = version.id
        statement.revision_count = revision_no
        statement.version = int(statement.version or 0) + 1
        _trail(db, statement, "PAYROLL_SUBMIT" if revision_no == 1 else "PAYROLL_CORRECT", {
            "internshipId": str(record.id),
            "studentId": str(student.id),
            "batchId": str(record.batch_id),
            "payMonth": month,
            "revisionNo": revision_no,
            "actualAmount": str(amount),
            "currency": currency,
            "agreedSalary": str(statement.agreed_salary_snapshot) if statement.agreed_salary_snapshot is not None else None,
            "evidenceFileId": str(file_obj.id),
            "evidenceSha256": file_obj.sha256 or "",
            "correctionReason": correction_reason or None,
        }, user)
        db.commit()
        return _view(db, statement)


def list_for_teacher(*, batch_id, page=1, page_size=20, status="ALL", user=None):
    return list_payrolls(page, page_size, batch_id=batch_id, status=status, user=user)


def list_payrolls(page=1, page_size=20, *, batch_id, status="ALL", pay_month=None,
                 keyword=None, college_id=None, user=None):
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.models import College, Major, SchoolClass, InternshipRecord, StudentProfile

    month = str(pay_month or "").strip()
    if month and not _MONTH.fullmatch(month):
        raise AppException("VALIDATION_ERROR", "工资月份格式应为年-月")

    with session() as db:
        scoped = apply_internship_record_scope(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == int(batch_id),
            InternshipRecord.is_deleted.is_(False),
        ), user).subquery()
        query = select(InternshipPayrollStatement, InternshipPayrollVersion, StudentProfile,
                       InternshipRecord, College.college_name, Major.major_name, SchoolClass.class_name).join(
            InternshipPayrollVersion,
            InternshipPayrollVersion.id == InternshipPayrollStatement.current_version_id,
        ).join(
            StudentProfile,
            StudentProfile.id == InternshipPayrollStatement.student_id,
        ).join(
            InternshipRecord, and_(InternshipRecord.id == InternshipPayrollStatement.internship_id,
                                  InternshipRecord.student_id == StudentProfile.id),
        ).outerjoin(
            SchoolClass, and_(SchoolClass.id == StudentProfile.class_id,
                             SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False)),
        ).outerjoin(
            Major, and_(Major.id == func.coalesce(StudentProfile.major_id, SchoolClass.major_id),
                        Major.tenant_id == _tid(), Major.is_deleted.is_(False)),
        ).outerjoin(
            College, and_(College.id == func.coalesce(StudentProfile.college_id, Major.college_id),
                          College.tenant_id == _tid(), College.is_deleted.is_(False)),
        ).where(
            InternshipPayrollStatement.tenant_id == _tid(),
            InternshipPayrollStatement.batch_id == int(batch_id),
            InternshipPayrollStatement.internship_id.in_(select(scoped.c.id)),
            InternshipPayrollStatement.is_deleted.is_(False),
            InternshipPayrollVersion.tenant_id == _tid(),
            InternshipPayrollVersion.is_current.is_(True),
            InternshipPayrollVersion.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == InternshipPayrollStatement.batch_id,
            InternshipPayrollVersion.statement_id == InternshipPayrollStatement.id,
        )
        if month:
            query = query.where(InternshipPayrollStatement.pay_month == month)
        if college_id:
            query = query.where(College.id == _as_id(college_id))
        term = str(keyword or "").strip()
        if term:
            query = query.where(or_(StudentProfile.real_name.contains(term, autoescape=True),
                                    StudentProfile.student_no.contains(term, autoescape=True)))
        status_value = str(status or "ALL").upper()
        if status_value != "ALL":
            if status_value not in {"SUBMITTED", "APPROVED", "RETURNED"}:
                raise AppException("VALIDATION_ERROR", "工资单状态不合法")
            query = query.where(InternshipPayrollVersion.status == status_value)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.execute(
            query.order_by(
                InternshipPayrollStatement.pay_month.desc(),
                StudentProfile.student_no,
                InternshipPayrollStatement.id,
            ).offset((max(1, int(page)) - 1) * int(page_size)).limit(int(page_size))
        ).all()
        items = []
        for statement, version, student, record, college, major, class_name in rows:
            item = _view(db, statement, include_history=False, current=version)
            item.update({
                "studentName": student.real_name,
                "studentNo": student.student_no,
                "college": college or "", "major": major or "", "className": class_name or "",
                "enterpriseName": record.enterprise_name or "", "positionName": record.position_name or "",
            })
            items.append(item)
        return items, total


def get_payroll(statement_id, user=None):
    with session() as db:
        statement = db.scalar(select(InternshipPayrollStatement).where(
            InternshipPayrollStatement.id == _as_id(statement_id),
            InternshipPayrollStatement.tenant_id == _tid(),
            InternshipPayrollStatement.is_deleted.is_(False)))
        if not statement:
            raise not_found("工资单不存在")
        assert_internship_record_scope(db, statement.internship_id, user, "查看工资单")
        return _view(db, statement)


def export_payrolls(*, batch_id, status="ALL", pay_month=None, keyword=None, college_id=None, user=None):
    from app.modules.internship.services.internship_export_util import load_export_rows, write_export_audit
    from app.modules.internship.services.internship_report_quality_service import format_report_time
    from app.modules.internship.services.internship_student_service import _currency_label
    from app.services import xlsx_util

    filters = dict(batch_id=batch_id, status=status, pay_month=pay_month, keyword=keyword, college_id=college_id)
    items, total = load_export_rows(list_payrolls, **filters, user=user)
    headers = ["工资单编号", "实习记录编号", "学号", "姓名", "院系", "专业", "班级", "工资月份",
               "当前实习单位", "当前实习岗位", "实发金额", "币种", "发薪日期", "状态", "版本",
               "提交时间", "更正原因", "审核人", "审核时间", "审核意见"]
    rows = []
    for item in items:
        version = item["current"]
        currency = _currency_label(version["currency"])
        if currency == "其他币种":
            currency = f'{version["currency"]}（其他币种）'
        rows.append([item["id"], item["internshipId"], item["studentNo"], item["studentName"],
                     item["college"], item["major"], item["className"], item["payMonth"],
                     item["enterpriseName"], item["positionName"], version["actualAmount"], currency,
                     version["paidOn"], version["statusLabel"], version["revisionNo"],
                     format_report_time(version["submittedAt"]), version["correctionReason"],
                     version["reviewedBy"], format_report_time(version["reviewedAt"]), version["reviewComment"]])
    content = xlsx_util.build_ledger_xlsx("月度工资台账", headers, rows,
        watermark=f"岗位实习中心·月度工资台账 · {_op(user)} · {datetime.now():%Y-%m-%d %H:%M}")
    with session() as db:
        write_export_audit(db, "月度工资台账", total, user=user, filters=filters)
        db.commit()
    return xlsx_util.pack_xlsx_result(content, "月度工资台账.xlsx", total)


def review(version_id, body: dict, user: dict):
    payload = body or {}
    action = str(payload.get("action") or "").strip().upper()
    if action not in {"APPROVE", "RETURN"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 RETURN")
    comment = str(payload.get("comment") or "").strip()
    if action == "RETURN" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因不少于5个字")

    with session() as db:
        version = db.scalar(select(InternshipPayrollVersion).where(
            InternshipPayrollVersion.id == _as_id(version_id),
            InternshipPayrollVersion.tenant_id == _tid(),
            InternshipPayrollVersion.is_deleted.is_(False),
        ))
        if not version:
            raise not_found("工资单版本不存在")
        statement = db.get(InternshipPayrollStatement, version.statement_id)
        if not statement or statement.tenant_id != _tid() or statement.is_deleted:
            raise not_found("工资单不存在")
        # 学生更正与教师审核统一按实习记录、工资单、版本加锁。
        assert_internship_record_scope(db, statement.internship_id, user, "审核学生工资单", lock=True)
        statement = db.scalar(select(InternshipPayrollStatement).where(
            InternshipPayrollStatement.id == version.statement_id,
            InternshipPayrollStatement.tenant_id == _tid(),
            InternshipPayrollStatement.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True))
        version = db.scalar(select(InternshipPayrollVersion).where(
            InternshipPayrollVersion.id == version.id,
            InternshipPayrollVersion.tenant_id == _tid(),
        ).with_for_update().execution_options(populate_existing=True))
        if not statement or statement.current_version_id != version.id or not version.is_current:
            raise AppException("DATA_CONFLICT", "该工资单已产生新版本，请刷新后重试")
        require_expected_version(payload.get("expectedVersion"), version.version, entity_name="工资审核")
        if version.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅待审核工资单可处理")
        version.status = "APPROVED" if action == "APPROVE" else "RETURNED"
        version.reviewed_by_name = _op(user)
        version.reviewed_at = datetime.utcnow()
        version.review_comment = comment or None
        version.version = int(version.version or 0) + 1
        statement.version = int(statement.version or 0) + 1
        _trail(db, statement, f"PAYROLL_{action}", {
            "versionId": str(version.id),
            "revisionNo": int(version.revision_no),
            "payMonth": statement.pay_month,
            "actualAmount": str(version.actual_amount),
            "currency": version.currency,
            "reason": comment or None,
        }, user)
        db.commit()
        return _view(db, statement)
