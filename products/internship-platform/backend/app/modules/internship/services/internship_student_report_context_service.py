"""学生月报、实习总结的批次化权威写入口。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import InternshipProcessReport, WeeklyReport
from app.modules.internship.services import internship_service as weekly_legacy
from app.modules.internship.services import internship_process_report_service as legacy
from app.modules.internship.services import internship_report_quality_service as quality
from app.modules.internship.services.internship_student_context_guard import (
    require_expected_version,
    require_explicit_context,
)
from app.services.db_service import _iso, _tid, session


def _context_row(row, record, student) -> dict:
    item = legacy._row(row, record, student)
    # This endpoint is restricted to the authenticated student's own record.
    # Return the body so a returned report can be corrected and resubmitted.
    item["content"] = row.content or ""
    item["submittedAt"] = _iso(row.submitted_at) or ""
    return item


def list_my(user: dict, *, batch_id, internship_id) -> dict:
    with session() as db:
        record, student, selected_batch_id = require_explicit_context(
            db,
            user,
            {"batchId": batch_id, "internshipId": internship_id},
            for_write=False,
        )
        rows = db.scalars(select(InternshipProcessReport).where(
            InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.internship_id == record.id,
            InternshipProcessReport.is_deleted.is_(False),
        ).order_by(
            InternshipProcessReport.submitted_at.desc(),
            InternshipProcessReport.id.desc(),
        )).all()
        items = []
        for row in rows:
            item = _context_row(row, record, student)
            snap = quality.latest_process_snapshot(db, row.id)
            item["reportVersion"] = int(snap.version_no) if snap else 0
            item["attachments"] = (snap.attachment_meta_json or []) if snap else []
            items.append(item)
        return {
            "items": items,
            "batchId": str(selected_batch_id),
            "internshipId": str(record.id),
            "rules": quality.rules_for_batch(db, selected_batch_id),
        }


def submit(user: dict, body: dict) -> dict:
    payload = body or {}
    report_type = str(payload.get("reportType") or "").upper()
    if report_type not in legacy.TYPE_LABEL:
        raise AppException(
            "VALIDATION_ERROR", "reportType 必须是 DAILY/MONTHLY/SUMMARY")
    content = str(payload.get("content") or "").strip()
    period_key = str(payload.get("periodKey") or "").strip()
    if report_type == "SUMMARY":
        period_key = "FINAL"
    if not period_key:
        raise AppException("VALIDATION_ERROR", "periodKey 必填")
    if len(period_key) > 20:
        raise AppException("VALIDATION_ERROR", "periodKey 最多 20 个字符")

    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        rules = quality.rules_for_batch(db, record.batch_id)
        minimum = quality.minimum_words(rules, report_type)
        if len(content) < minimum:
            raise AppException(
                "VALIDATION_ERROR",
                f"{legacy.TYPE_LABEL[report_type]}正文至少 {minimum} 字",
            )
        attachment_ids, attachment_meta = quality.validate_attachments(
            payload.get("attachmentFileIds") or payload.get("attachments") or [],
            rules,
        )
        existing = db.scalar(select(InternshipProcessReport).where(
            InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.internship_id == record.id,
            InternshipProcessReport.report_type == report_type,
            InternshipProcessReport.period_key == period_key,
            InternshipProcessReport.is_deleted.is_(False),
        ).with_for_update())
        current_version = int(existing.version or 0) if existing else 0
        require_expected_version(
            payload.get("expectedVersion"),
            current_version,
            entity_name="过程报告",
        )

        if existing:
            if existing.status != "RETURNED":
                raise AppException(
                    "DATA_CONFLICT", "该报告已提交，仅退回记录可按当前版本重交")
            existing.content = content
            existing.word_count = len(content)
            existing.status = "PENDING_REVIEW"
            existing.submitted_at = datetime.utcnow()
            existing.review_action = None
            existing.review_comment = None
            existing.reviewed_by_name = None
            existing.reviewed_at = None
            existing.version = current_version + 1
            row = existing
            action = "RESUBMIT_VERSIONED"
        else:
            row = InternshipProcessReport(
                tenant_id=_tid(),
                internship_id=record.id,
                report_type=report_type,
                period_key=period_key,
                content=content,
                word_count=len(content),
                status="PENDING_REVIEW",
                submitted_at=datetime.utcnow(),
            )
            db.add(row)
            db.flush()
            action = "SUBMIT_VERSIONED"

        snapshot = quality.append_process_snapshot(
            db,
            row=row,
            record=record,
            student=student,
            content=content,
            attachment_ids=attachment_ids,
            attachment_meta=attachment_meta,
        )
        legacy._trail(
            db,
            row.id,
            action,
            {
                "reportType": report_type,
                "periodKey": period_key,
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "expectedVersion": current_version,
                "newVersion": int(row.version or 0),
                "reportVersion": int(snapshot.version_no),
                "attachmentCount": len(attachment_ids),
                "minimumWords": minimum,
            },
            operator=legacy._op_name(user),
        )
        db.commit()
        result = _context_row(row, record, student)
        result["reportVersion"] = int(snapshot.version_no)
        result["attachments"] = attachment_meta
        result["minimumWords"] = minimum
        return result


def _weekly_row(row) -> dict:
    return {
        "id": str(row.id),
        "internshipId": str(row.internship_id),
        "week": int(row.week_number),
        "weekNo": int(row.week_number),
        "workContent": row.work_content or "",
        "harvestContent": row.harvest_content or "",
        "planContent": row.plan_content or "",
        "wordCount": int(row.word_count or 0),
        "reportVersion": int(row.report_version or 1),
        "version": int(row.version or 0),
        "status": row.status,
        "reviewComment": row.review_comment or "",
        "submittedAt": _iso(row.submitted_at) or "",
    }


def list_weekly(
    user: dict,
    *,
    batch_id,
    internship_id,
    page: int = 1,
    page_size: int = 20,
    focus_report_id: int | None = None,
) -> dict:
    """分页返回本人的周报；消息深链只可定位本人当前实习记录中的一条。"""
    try:
        safe_page = max(1, int(page or 1))
        safe_page_size = min(50, max(1, int(page_size or 20)))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "周报分页参数不正确") from None
    with session() as db:
        record, _student, selected_batch_id = require_explicit_context(
            db,
            user,
            {"batchId": batch_id, "internshipId": internship_id},
            for_write=False,
        )
        filters = (
            WeeklyReport.tenant_id == _tid(),
            WeeklyReport.internship_id == record.id,
            WeeklyReport.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(WeeklyReport).where(*filters)) or 0)
        focus_page = None
        if focus_report_id not in (None, ""):
            try:
                focus_id = int(focus_report_id)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "周报编号不正确") from None
            focused = db.scalar(select(WeeklyReport).where(*filters, WeeklyReport.id == focus_id))
            # URL 参数即使被改成其他学生的 ID，也只能得到统一的不存在，不泄露对象或分页位置。
            if focused is None:
                raise not_found("周报不存在或不属于当前实习记录")
            before_count = int(db.scalar(select(func.count()).select_from(WeeklyReport).where(
                *filters,
                or_(
                    WeeklyReport.week_number > focused.week_number,
                    and_(WeeklyReport.week_number == focused.week_number, WeeklyReport.id > focused.id),
                ),
            )) or 0)
            focus_page = before_count // safe_page_size + 1
        rows = db.scalars(select(WeeklyReport).where(*filters).order_by(
            WeeklyReport.week_number.desc(),
            WeeklyReport.id.desc(),
        ).offset((safe_page - 1) * safe_page_size).limit(safe_page_size)).all()
        return {
            "items": [_weekly_row(row) for row in rows],
            "batchId": str(selected_batch_id),
            "internshipId": str(record.id),
            "page": safe_page,
            "pageSize": safe_page_size,
            "total": total,
            "hasMore": safe_page * safe_page_size < total,
            # 首屏仍返回第一页；客户端只在深链目标不在首屏时额外请求这一页，
            # 不为对象定位把整个历史列表一次性拉到手机上。
            "focusPage": focus_page,
        }


def submit_weekly(user: dict, body: dict) -> dict:
    payload = body or {}
    try:
        week_no = int(payload.get("weekNo") or payload.get("weekNumber"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "周次必须为数字") from None
    if week_no < 1:
        raise AppException("VALIDATION_ERROR", "周次必须大于等于 1")
    work_content = str(payload.get("workContent") or "").strip()
    harvest_content = str(payload.get("harvestContent") or "").strip()
    plan_content = str(payload.get("planContent") or "").strip()
    if len(work_content) < 10 or len(harvest_content) < 10:
        raise AppException(
            "VALIDATION_ERROR", "本周工作内容与本周收获均至少 10 个字")

    with session() as db:
        record, _student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        existing = db.scalar(select(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(),
            WeeklyReport.internship_id == record.id,
            WeeklyReport.week_number == week_no,
            WeeklyReport.is_deleted.is_(False),
        ).with_for_update())
        current_version = int(existing.version or 0) if existing else 0
        require_expected_version(
            payload.get("expectedVersion"),
            current_version,
            entity_name="周报",
        )

        if existing:
            if existing.status != "RETURNED":
                raise AppException(
                    "DATA_CONFLICT", f"第 {week_no} 周周报已提交，仅退回记录可重交")
            existing.work_content = work_content
            existing.harvest_content = harvest_content
            existing.plan_content = plan_content
            existing.word_count = (
                len(work_content) + len(harvest_content) + len(plan_content))
            existing.report_version = int(existing.report_version or 1) + 1
            existing.version = current_version + 1
            existing.status = "PENDING_REVIEW"
            existing.submitted_at = datetime.utcnow()
            existing.review_action = None
            existing.review_comment = None
            existing.reviewed_by_name = None
            existing.reviewed_at = None
            row = existing
            action = "RESUBMIT_VERSIONED"
        else:
            row = WeeklyReport(
                tenant_id=_tid(),
                internship_id=record.id,
                week_number=week_no,
                work_content=work_content,
                harvest_content=harvest_content,
                plan_content=plan_content,
                word_count=(
                    len(work_content) + len(harvest_content) + len(plan_content)),
                report_version=1,
                status="PENDING_REVIEW",
                submitted_at=datetime.utcnow(),
            )
            db.add(row)
            db.flush()
            action = "SUBMIT_VERSIONED"

        weekly_legacy._trail(
            db,
            row.id,
            "REPORT",
            action,
            {
                "weekNo": week_no,
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "expectedVersion": current_version,
                "newVersion": int(row.version or 0),
                "reportVersion": int(row.report_version or 1),
            },
        )
        from app.modules.internship.services import internship_todo_helper as todo
        todo.push_weekly_todo(db, row, record)
        db.commit()
        return _weekly_row(row)
