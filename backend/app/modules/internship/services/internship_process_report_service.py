"""岗位实习 · 过程报告（日报/月报/实习总结）服务。

对标工学云/顶岗实习：学生移动端提交 → 指导教师 PC 批阅 → 纳入归档与成绩月报项。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipAuditTrail, InternshipProcessReport, InternshipRecord, StudentProfile
from app.services import xlsx_util
from app.services.db_service import _as_id, _iso, _tid, session

TYPE_LABEL = {"DAILY": "日报", "MONTHLY": "月报", "SUMMARY": "实习总结"}
STATUS_LABEL = {"PENDING_REVIEW": "待批阅", "APPROVED": "已通过", "RETURNED": "已退回"}
MIN_WORDS = {"DAILY": 30, "MONTHLY": 100, "SUMMARY": 300}


def _op_name(user=None) -> str:
    if user:
        return user.get("realName") or "系统"
    from app.core.context import get_current_user_ctx
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, rid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=rid, target_type="PROCESS_REPORT",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _scope(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _row(r, rec, stu, class_name=None):
    return {
        "id": str(r.id), "internId": str(r.internship_id),
        "reportType": r.report_type, "reportTypeLabel": TYPE_LABEL.get(r.report_type, r.report_type),
        "periodKey": r.period_key,
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "className": class_name or "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "wordCount": r.word_count, "submitAt": _iso(r.submitted_at) or "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "reviewComment": r.review_comment or "", "reviewedByName": r.reviewed_by_name or "",
        "reviewedAt": _iso(r.reviewed_at) or "",
    }


def _student_record(db, user, *, batch_id=None, for_write: bool = False):
    from app.modules.internship.services.internship_record_resolver import (
        require_active_student_record,
        resolve_optional_student_record,
    )
    sno = (user or {}).get("studentNo")
    if not sno:
        if for_write:
            raise AppException("VALIDATION_ERROR", "学生身份信息缺失")
        return None, None
    if for_write:
        return require_active_student_record(db, user, batch_id=batch_id, student_no=sno)
    rec, stu, _ctx = resolve_optional_student_record(db, user, batch_id=batch_id, student_no=sno)
    return rec, stu


def my_reports(user) -> dict:
    """本人过程报告列表（含批阅意见）——补齐此前只能提交、读不到老师批阅结果的缺口。"""
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return {"items": []}
        rows = db.scalars(select(InternshipProcessReport).where(
            InternshipProcessReport.tenant_id == _tid(), InternshipProcessReport.internship_id == rec.id,
            InternshipProcessReport.is_deleted.is_(False)).order_by(
            InternshipProcessReport.submitted_at.desc(), InternshipProcessReport.id.desc())).all()
        return {"items": [_row(r, rec, stu) for r in rows]}


def list_reports(page, page_size, report_type=None, status=None, keyword=None, batch_id=None, user=None):
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipProcessReport).where(
            InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.is_deleted.is_(False),
            InternshipProcessReport.internship_id.in_(record_ids))
        if report_type:
            q = q.where(InternshipProcessReport.report_type == report_type)
        if status:
            q = q.where(InternshipProcessReport.status == status)
        rows = db.scalars(q.order_by(InternshipProcessReport.submitted_at.desc(),
                                     InternshipProcessReport.id.desc())).all()
        scope, in_scope = _scope(user)
        items = []
        for r in rows:
            rec = db.get(InternshipRecord, r.internship_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            from app.modules.internship.services.internship_service import (
                resolve_student_class_college_names)
            cn, _ = resolve_student_class_college_names(db, stu)
            items.append(_row(r, rec, stu, class_name=cn))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_report(rid, user=None):
    with session() as db:
        r = db.get(InternshipProcessReport, _as_id(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("过程报告不存在")
        rec = db.get(InternshipRecord, r.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            from app.core.exceptions import no_permission
            raise no_permission("不在数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "PROCESS_REPORT",
            InternshipAuditTrail.target_id == r.id).order_by(InternshipAuditTrail.id)).all()
        return {
            **_row(r, rec, stu),
            "content": r.content or "",
            "reviewComment": r.review_comment or "",
            "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                            "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                           for t in trail],
        }


def student_submit(rec, report_type: str, period_key: str, content: str) -> dict:
    rt = (report_type or "").upper()
    if rt not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "reportType 必须是 DAILY/MONTHLY/SUMMARY")
    text = (content or "").strip()
    min_w = MIN_WORDS.get(rt, 30)
    if len(text) < min_w:
        raise AppException("VALIDATION_ERROR", f"{TYPE_LABEL[rt]}正文至少 {min_w} 字")
    pk = (period_key or "").strip()
    if rt == "SUMMARY":
        pk = "FINAL"
    if not pk:
        raise AppException("VALIDATION_ERROR", "periodKey 必填")
    with session() as db:
        dup = db.scalars(select(InternshipProcessReport).where(
            InternshipProcessReport.tenant_id == _tid(), InternshipProcessReport.internship_id == rec.id,
            InternshipProcessReport.report_type == rt, InternshipProcessReport.period_key == pk,
            InternshipProcessReport.is_deleted.is_(False))).first()
        if dup and dup.status != "RETURNED":
            raise AppException("DATA_CONFLICT", f"该{TYPE_LABEL[rt]}已提交，请勿重复提交")
        if dup and dup.status == "RETURNED":
            dup.content = text
            dup.word_count = len(text)
            dup.status = "PENDING_REVIEW"
            dup.submitted_at = datetime.utcnow()
            dup.review_comment = None
            _trail(db, dup.id, "RESUBMIT", {"reportType": rt, "periodKey": pk})
            db.commit()
            return {"id": str(dup.id), "status": dup.status, "message": "已重新提交"}
        row = InternshipProcessReport(
            tenant_id=_tid(), internship_id=rec.id, report_type=rt, period_key=pk,
            content=text, word_count=len(text), status="PENDING_REVIEW", submitted_at=datetime.utcnow())
        db.add(row)
        db.flush()
        _trail(db, row.id, "SUBMIT", {"reportType": rt, "periodKey": pk})
        db.commit()
        return {"id": str(row.id), "status": row.status, "message": f"{TYPE_LABEL[rt]}提交成功"}


def review_report(rid, action: str, comment: str = "", user=None) -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        r = db.get(InternshipProcessReport, _as_id(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("过程报告不存在")
        rec = db.get(InternshipRecord, r.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            from app.core.exceptions import no_permission
            raise no_permission("不在数据范围内")
        if r.status not in ("PENDING_REVIEW", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可批阅")
        r.status = "APPROVED" if action == "APPROVE" else "RETURNED"
        r.review_action = action
        r.review_comment = (comment or "").strip()
        r.reviewed_by_name = _op_name(user)
        r.reviewed_at = datetime.utcnow()
        _trail(db, r.id, f"REVIEW_{action}", {"comment": r.review_comment})
        db.commit()
        return {"id": str(r.id), "status": r.status, "statusLabel": STATUS_LABEL.get(r.status)}


def export_reports(report_type=None, status=None, keyword=None, batch_id=None, user=None) -> dict:
    items, _ = list_reports(
        1, 100000, report_type=report_type, status=status, keyword=keyword, batch_id=batch_id, user=user)
    label = TYPE_LABEL.get((report_type or "").upper(), "过程报告")
    rows = [[it["studentNo"], it["studentName"], it["enterpriseName"], it["periodKey"],
             it["wordCount"], it["submitAt"], it["statusLabel"]] for it in items]
    headers = ["学号", "姓名", "企业", "周期", "字数", "提交时间", "状态"]
    wm = f"岗位实习中心·{label}台账 · {_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M}"
    content = xlsx_util.build_ledger_xlsx(f"{label}台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, f"{label}台账.xlsx", len(items))
