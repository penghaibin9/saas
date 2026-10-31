"""岗位实习 · 过程报告（日报/月报/实习总结）服务。

对标工学云/顶岗实习：学生移动端提交 → 指导教师 PC 批阅 → 纳入归档与成绩月报项。
"""
from __future__ import annotations

from app.core.tenant_scoped import tenant_get

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import InternshipAuditTrail, InternshipProcessReport, InternshipRecord, SchoolClass, StudentProfile
from app.modules.internship.services.internship_version import extract_expected_version, versioned_update
from app.modules.internship.services import internship_report_quality_service as quality
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
        "batchId": str(rec.batch_id) if rec and rec.batch_id else "",
        "reportType": r.report_type, "reportTypeLabel": TYPE_LABEL.get(r.report_type, "过程报告"),
        "periodKey": r.period_key,
        "periodLabel": "实习总结" if r.report_type == "SUMMARY" else r.period_key,
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "className": class_name or "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "wordCount": r.word_count, "submitAt": _iso(r.submitted_at) or "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, "状态待确认"),
        "version": int(r.version or 0),
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


def list_reports(page, page_size, report_type=None, status=None, keyword=None, batch_id=None, user=None,
                 start_date=None, end_date=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    with session() as db:
        batch = resolve_batch(db, batch_id)
        q = select(InternshipProcessReport, InternshipRecord, StudentProfile, SchoolClass.class_name).join(
            InternshipRecord, and_(InternshipRecord.id == InternshipProcessReport.internship_id,
                InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False)),
        ).join(StudentProfile, and_(StudentProfile.id == InternshipRecord.student_id,
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)),
        ).outerjoin(SchoolClass, and_(SchoolClass.id == StudentProfile.class_id,
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False)),
        ).where(
            InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id)
        q = apply_internship_record_scope(q, user)
        q = quality.filter_submission_dates(q, InternshipProcessReport, start_date, end_date)
        if report_type:
            q = q.where(InternshipProcessReport.report_type == report_type)
        if status:
            q = q.where(InternshipProcessReport.status == status)
        if keyword and keyword.strip():
            term = keyword.strip()
            q = q.where(or_(StudentProfile.real_name.contains(term, autoescape=True),
                StudentProfile.student_no.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        if page_size <= 0:
            return [], total
        rows = db.execute(q.order_by(InternshipProcessReport.submitted_at.desc(), InternshipProcessReport.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        reviews = quality.latest_review_map(db, "PROCESS", [r.id for r, *_ in rows])
        snapshots = quality.latest_snapshot_map(db, "PROCESS", [r.id for r, *_ in rows])
        return [{**_row(r, rec, stu, class_name=cn), "review": reviews.get(r.id),
                 "reportVersion": int(snapshots[r.id].version_no) if r.id in snapshots else 0}
                for r, rec, stu, cn in rows], total


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
        quality_view = quality.snapshot_view(db, r.id)
        versions = quality_view.get("versions") or []
        return {
            **_row(r, rec, stu),
            "content": r.content or "",
            "reviewComment": r.review_comment or "",
            "versions": versions,
            "reportVersion": versions[0]["versionNo"] if versions else 0,
            "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                            "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                           for t in trail],
        }


def student_submit(rec, report_type: str, period_key: str, content: str) -> dict:
    rt = (report_type or "").upper()
    if rt not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "报告类型必须是日报 / 月报 / 总结")
    text = (content or "").strip()
    min_w = MIN_WORDS.get(rt, 30)
    if len(text) < min_w:
        raise AppException("VALIDATION_ERROR", f"{TYPE_LABEL[rt]}正文至少 {min_w} 字")
    pk = (period_key or "").strip()
    if rt == "SUMMARY":
        pk = "FINAL"
    if not pk:
        raise AppException("VALIDATION_ERROR", "请选择报告周期")
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
            dup.version = int(dup.version or 0) + 1
            _trail(db, dup.id, "RESUBMIT", {"reportType": rt, "periodKey": pk,
                                             "version": int(dup.version or 0)})
            from app.modules.internship.services import internship_todo_helper as todo
            todo.push_process_report_todo(db, dup, rec)
            db.commit()
            return {"id": str(dup.id), "status": dup.status, "version": int(dup.version or 0),
                    "message": "已重新提交"}
        row = InternshipProcessReport(
            tenant_id=_tid(), internship_id=rec.id, report_type=rt, period_key=pk,
            content=text, word_count=len(text), status="PENDING_REVIEW", submitted_at=datetime.utcnow())
        db.add(row)
        db.flush()
        _trail(db, row.id, "SUBMIT", {"reportType": rt, "periodKey": pk})
        from app.modules.internship.services import internship_todo_helper as todo
        todo.push_process_report_todo(db, row, rec)
        db.commit()
        return {"id": str(row.id), "status": row.status, "message": f"{TYPE_LABEL[rt]}提交成功"}


def review_report(rid, action: str, comment: str = "", user=None, *, expected_version=None,
                  expected_batch_id=None, rating_level=None, summary_score=None) -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        r = db.scalar(select(InternshipProcessReport).where(
            InternshipProcessReport.id == _as_id(rid), InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.is_deleted.is_(False),
        ).with_for_update())
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("过程报告不存在")
        rec = tenant_get(db, InternshipRecord, r.internship_id)
        stu = tenant_get(db, StudentProfile, rec.student_id) if rec else None
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            from app.core.exceptions import no_permission
            raise no_permission("不在数据范围内")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(rec, expected_batch_id)
        if r.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅学生已提交/重交后的待批阅报告可审核")
        status = "APPROVED" if action == "APPROVE" else "RETURNED"
        review_fact = quality.record_process_review(
            db,
            row=r,
            action=action,
            comment=comment,
            user=user or {},
            rating_level=rating_level,
            summary_score=summary_score,
        )
        new_ver = versioned_update(
            db, InternshipProcessReport, entity_id=r.id, tenant_id=_tid(),
            expected_version=extract_expected_version({"expectedVersion": expected_version}),
            expected_status=r.status, values={"status": status, "review_action": action,
                                               "review_comment": (comment or "").strip(),
                                               "reviewed_by_name": _op_name(user),
                                               "reviewed_at": datetime.utcnow()})
        _trail(
            db,
            r.id,
            f"REVIEW_{action}",
            {
                "comment": (comment or "").strip(),
                "ratingLevel": review_fact.rating_level,
                "summaryScore": (
                    float(review_fact.summary_score)
                    if review_fact.summary_score is not None else None
                ),
                "reportVersionId": str(review_fact.report_version_id),
            },
            operator=_op_name(user),
        )
        from app.modules.internship.services import internship_todo_helper as todo
        todo.todo_done(db, biz_id=r.id, todo_type=todo.process_report_todo_type(r))
        db.commit()
        return {
            "id": str(r.id),
            "status": status,
            "statusLabel": STATUS_LABEL.get(status),
            "version": new_ver,
            "ratingLevel": review_fact.rating_level,
            "summaryScore": (
                float(review_fact.summary_score)
                if review_fact.summary_score is not None else None
            ),
        }


def export_reports(report_type=None, status=None, keyword=None, batch_id=None, user=None,
                   start_date=None, end_date=None) -> dict:
    from app.modules.internship.services.internship_export_util import load_export_rows, write_export_audit

    items, _ = load_export_rows(
        list_reports, report_type=report_type, status=status, keyword=keyword,
        batch_id=batch_id, user=user, start_date=start_date, end_date=end_date)

    label = TYPE_LABEL.get((report_type or "").upper(), "过程报告")
    headers = [
        "学号", "姓名", "企业", "报告类型", "周期", "提交版本", "字数", "提交时间", "状态",
        "五级评价", "总结评分(0-100)", "批阅教师", "批阅时间", "批阅意见",
    ]
    rows = []
    for it in items:
        review = it.get("review")
        rows.append([
            it["studentNo"], it["studentName"], it["enterpriseName"],
            it["reportTypeLabel"], it.get("periodLabel") or ("实习总结" if it.get("reportType") == "SUMMARY" else it["periodKey"]), it.get("reportVersion") or "版本待核实", it["wordCount"], quality.format_report_time(it["submitAt"]),
            it["statusLabel"],
            review.get("ratingLevel") if review else "",
            review.get("summaryScore") if review and review.get("summaryScore") is not None else "",
            review.get("reviewerName") if review else "",
            quality.format_report_time(review.get("reviewedAt")) if review else "",
            review.get("comment") if review else "",
        ])
    wm = f"岗位实习中心·{label}台账 · {_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M}"
    content = xlsx_util.build_ledger_xlsx(f"{label}台账", headers, rows, watermark=wm)
    with session() as db:
        write_export_audit(db, '过程报告台账', len(items), user=user,
            filters={'batchId': str(batch_id or ''), 'reportType': report_type, 'status': status,
                     'keyword': keyword, 'startDate': str(start_date or ''), 'endDate': str(end_date or '')})
        db.commit()
    return xlsx_util.pack_xlsx_result(content, f"{label}台账.xlsx", len(items))
