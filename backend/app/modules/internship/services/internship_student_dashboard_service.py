"""学生双端岗位实习显式批次工作台。

仅返回当前登录学生本人在所选 batchId 下的实习摘要。多条进行中记录时禁止
服务端猜默认记录；学生选择后，小程序首页、合规状态和安全教育使用同一批次。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import (
    InternshipAgreement, InternshipBatch, InternshipCheckin, InternshipInsurance,
    InternshipLeave, InternshipPosition, WeeklyReport,
)
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.services.db_service import _iso, _tid, session


def _student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    student = resolve_student(db, _require_student(user))
    if not student:
        raise AppException("NO_PERMISSION", "无法解析当前登录学生身份")
    return student


def _timeline(record, agreement_status, insurance_status):
    statuses = {
        "PREPARING": 0, "READY": 1, "ONBOARD": 2, "ASSESSING": 3, "ARCHIVED": 4,
    }
    current = statuses.get(record.status, 0)
    nodes = [
        ("档案与岗位", bool(record.position_id and record.enterprise_id)),
        ("协议与保险", agreement_status in ("EFFECTIVE", "ARCHIVED") and insurance_status == "VERIFIED"),
        ("到岗实习", current >= 2),
        ("过程考核", current >= 3),
        ("归档完成", current >= 4),
    ]
    first_open = next((idx for idx, (_, done) in enumerate(nodes) if not done), None)
    return [{
        "id": f"student-internship-{idx + 1}",
        "title": title,
        "status": "COMPLETED" if done else ("PROCESSING" if idx == first_open else "NOT_STARTED"),
        "current": idx == first_open,
    } for idx, (title, done) in enumerate(nodes)]


def get_my_dashboard(user, batch_id=None):
    with session() as db:
        student = _student(db, user)
        ctx = resolve_student_internship_context(
            db, student=student, batch_id=batch_id, for_write=False)
        if ctx.mode == "need_select":
            return {
                "hasData": False, "needSelect": True,
                "message": ctx.message, "candidates": ctx.candidates,
            }
        record = ctx.record
        if not record:
            return {
                "hasData": False, "needSelect": False,
                "message": ctx.message or "你暂无实习记录", "candidates": ctx.candidates,
            }
        batch = ctx.batch or (db.get(InternshipBatch, record.batch_id) if record.batch_id else None)
        position = db.get(InternshipPosition, record.position_id) if record.position_id else None

        reports = db.scalars(select(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(),
            WeeklyReport.internship_id == record.id,
            WeeklyReport.is_deleted.is_(False)).order_by(
                WeeklyReport.week_number.desc(), WeeklyReport.id.desc())).all()
        latest_report = reports[0] if reports else None

        today = f"{datetime.now():%Y-%m-%d}"
        checkin = db.scalars(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(),
            InternshipCheckin.internship_id == record.id,
            InternshipCheckin.checkin_date == today,
            InternshipCheckin.is_deleted.is_(False)).order_by(
                InternshipCheckin.id.desc())).first()
        checkin_total = int(db.scalar(select(func.count()).select_from(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(),
            InternshipCheckin.internship_id == record.id,
            InternshipCheckin.is_deleted.is_(False))) or 0)

        agreement = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(),
            InternshipAgreement.internship_id == record.id,
            InternshipAgreement.is_deleted.is_(False)).order_by(
                InternshipAgreement.id.desc())).first()
        insurance = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.internship_id == record.id,
            InternshipInsurance.is_deleted.is_(False)).order_by(
                InternshipInsurance.id.desc())).first()
        leave = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(),
            InternshipLeave.internship_id == record.id,
            InternshipLeave.status.in_(("PENDING", "APPROVED")),
            InternshipLeave.is_deleted.is_(False)).order_by(
                InternshipLeave.id.desc())).first()

        agreement_status = agreement.status if agreement else "PENDING"
        insurance_status = insurance.status if insurance else "NOT_SUBMITTED"
        week_no = 1
        submitted = False
        feedback = ""
        if latest_report:
            feedback = latest_report.review_comment or ""
            if latest_report.status == "APPROVED":
                week_no = int(latest_report.week_number or 0) + 1
            else:
                week_no = int(latest_report.week_number or 1)
                submitted = latest_report.status == "PENDING_REVIEW"

        return {
            "hasData": True, "needSelect": False,
            "historyMode": ctx.mode == "history",
            "recordId": str(record.id), "batchId": str(record.batch_id or ""),
            "batchName": getattr(batch, "batch_name", "") or "",
            "recordStatus": record.status,
            "enterpriseId": str(record.enterprise_id or ""),
            "enterpriseName": record.enterprise_name or "",
            "positionId": str(record.position_id or ""),
            "positionName": record.position_name or "",
            "workLocation": getattr(position, "work_location", "") or getattr(position, "work_address", "") or "",
            "advisorName": record.advisor_name or "",
            "enterpriseMentor": record.mentor_name or "",
            "todayCheckin": {
                "done": bool(checkin),
                "time": _iso(getattr(checkin, "checkin_time", None)) or "",
                "totalDays": checkin_total,
            },
            "weekly": {
                "weekNumber": week_no, "submitted": submitted,
                "lastFeedback": feedback,
            },
            "agreementStatus": agreement_status,
            "insuranceStatus": insurance_status,
            "leaveStatus": leave.status if leave else "NONE",
            "timeline": _timeline(record, agreement_status, insurance_status),
            "candidates": ctx.candidates,
        }
