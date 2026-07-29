"""教材PC工作台只读聚合。

只提供页面所需的当前学期候选、发放批次和学生明细；不新建业务事实、不绕过教材最终写facade。
"""
from __future__ import annotations

from sqlalchemy import func

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可使用教材征订与发放工作台")
    return ctx


def _formal_term(db, term_id):
    from app.models import AaTerm

    if not term_id or not str(term_id).isdigit():
        raise AppException("VALIDATION_ERROR", "请选择正式学期termId")
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise not_found("学期不存在")
    return term


def list_review_candidates(user, term_id):
    """当前学期待审核教材选用，供创建审核批次；返回termId防前端跨学期混选。"""
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTextbookSelection
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with session() as db:
        _require_school(user, db)
        term = _formal_term(db, term_id)
        guard_term_writable(db, term.id)
        rows = db.query(AaTextbookSelection, AaTeachingTask).join(
            AaTeachingTask,
            AaTeachingTask.id == AaTextbookSelection.task_id,
        ).join(
            AaTeachingTaskBatch,
            AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
        ).filter(
            AaTextbookSelection.tenant_id == _tid(),
            AaTextbookSelection.status == "SUBMITTED",
            AaTextbookSelection.is_deleted.is_(False),
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.term_id == term.id,
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).order_by(AaTextbookSelection.id).all()
        return {
            "termId": str(term.id),
            "items": [{
                "selectionId": str(selection.id),
                "courseName": selection.course_name or task.course_name,
                "textbookName": selection.textbook_name,
                "expectedQty": selection.expected_qty,
                "status": selection.status,
            } for selection, task in rows],
            "total": len(rows),
        }


def list_distribution_batches(user, term_id=None, page=1, page_size=50):
    """按学期列出教材发放批次和首屏处置结论。"""
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
    )

    with session() as db:
        _require_school(user, db)
        term = _formal_term(db, term_id) if term_id else None
        query = db.query(AaTextbookDistributionBatch, AaTextbookOrderBatch).join(
            AaTextbookOrderBatch,
            AaTextbookOrderBatch.id == AaTextbookDistributionBatch.order_batch_id,
        ).filter(
            AaTextbookDistributionBatch.tenant_id == _tid(),
            AaTextbookDistributionBatch.is_deleted.is_(False),
            AaTextbookOrderBatch.tenant_id == _tid(),
            AaTextbookOrderBatch.is_deleted.is_(False),
        )
        if term:
            query = query.filter(AaTextbookOrderBatch.term_id == term.id)
        total = query.count()
        rows = query.order_by(AaTextbookDistributionBatch.id.desc()).offset(
            (max(1, int(page)) - 1) * int(page_size)
        ).limit(int(page_size)).all()

        items = []
        for batch, order in rows:
            counts = dict(db.query(
                AaTextbookDistributionRecord.status,
                func.count(AaTextbookDistributionRecord.id),
            ).filter(
                AaTextbookDistributionRecord.tenant_id == _tid(),
                AaTextbookDistributionRecord.batch_id == batch.id,
                AaTextbookDistributionRecord.is_deleted.is_(False),
            ).group_by(AaTextbookDistributionRecord.status).all())
            record_ids = [value for (value,) in db.query(AaTextbookDistributionRecord.id).filter(
                AaTextbookDistributionRecord.tenant_id == _tid(),
                AaTextbookDistributionRecord.batch_id == batch.id,
                AaTextbookDistributionRecord.is_deleted.is_(False),
            ).all()]
            unsettled = 0
            if record_ids:
                unsettled = db.query(AaTextbookFeeLedger).filter(
                    AaTextbookFeeLedger.tenant_id == _tid(),
                    AaTextbookFeeLedger.distribution_record_id.in_(record_ids),
                    AaTextbookFeeLedger.status.in_(["UNPAID", "PARTIAL"]),
                    AaTextbookFeeLedger.is_deleted.is_(False),
                ).count()
            pending = int(counts.get("PENDING", 0) or 0)
            items.append({
                "distributionBatchId": str(batch.id),
                "orderBatchId": str(order.id),
                "orderBatchName": order.batch_name,
                "termId": str(order.term_id) if order.term_id else None,
                "classId": str(batch.class_id) if batch.class_id else None,
                "className": batch.class_name,
                "status": batch.status,
                "recordCount": int(sum(counts.values())),
                "pendingCount": pending,
                "receivedCount": int(counts.get("RECEIVED", 0) or 0),
                "returnedCount": int(counts.get("RETURNED", 0) or 0),
                "excludedCount": int(counts.get("EXCLUDED", 0) or 0),
                "unsettledFeeCount": int(unsettled or 0),
                "nextAction": (
                    "继续签收" if pending else
                    ("处理未结清费用" if unsettled else "本批次已收口")
                ),
            })
        return items, total


def list_distribution_records(user, batch_id, page=1, page_size=100):
    """发放批次学生明细，包含姓名、学号与费用状态，供独立处理页。"""
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
        StudentProfile,
    )

    with session() as db:
        _require_school(user, db)
        batch = db.query(AaTextbookDistributionBatch).filter(
            AaTextbookDistributionBatch.id == int(batch_id),
            AaTextbookDistributionBatch.tenant_id == _tid(),
            AaTextbookDistributionBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("教材发放批次不存在")
        order = db.query(AaTextbookOrderBatch).filter(
            AaTextbookOrderBatch.id == batch.order_batch_id,
            AaTextbookOrderBatch.tenant_id == _tid(),
            AaTextbookOrderBatch.is_deleted.is_(False),
        ).first()
        if not order:
            raise AppException("DATA_CONFLICT", "发放批次未关联有效征订批次", http_status=409)
        query = db.query(AaTextbookDistributionRecord, StudentProfile).join(
            StudentProfile,
            StudentProfile.id == AaTextbookDistributionRecord.student_id,
        ).filter(
            AaTextbookDistributionRecord.tenant_id == _tid(),
            AaTextbookDistributionRecord.batch_id == batch.id,
            AaTextbookDistributionRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        total = query.count()
        rows = query.order_by(
            StudentProfile.student_no,
            AaTextbookDistributionRecord.textbook_name,
        ).offset((max(1, int(page)) - 1) * int(page_size)).limit(int(page_size)).all()
        record_ids = [int(record.id) for record, _student in rows]
        fees = {}
        if record_ids:
            fees = {
                int(fee.distribution_record_id): fee
                for fee in db.query(AaTextbookFeeLedger).filter(
                    AaTextbookFeeLedger.tenant_id == _tid(),
                    AaTextbookFeeLedger.distribution_record_id.in_(record_ids),
                    AaTextbookFeeLedger.is_deleted.is_(False),
                ).all()
            }
        return [{
            "recordId": str(record.id),
            "studentId": str(record.student_id),
            "studentNo": student.student_no,
            "studentName": student.real_name,
            "textbookName": record.textbook_name,
            "qty": record.qty,
            "status": record.status,
            "feeStatus": fees.get(int(record.id)).status if fees.get(int(record.id)) else None,
            "amount": float(fees.get(int(record.id)).amount) if fees.get(int(record.id)) else None,
            "paidAmount": float(fees.get(int(record.id)).paid_amount) if fees.get(int(record.id)) else None,
        } for record, student in rows], total, {
            "distributionBatchId": str(batch.id),
            "orderBatchId": str(order.id),
            "orderBatchName": order.batch_name,
            "classId": str(batch.class_id) if batch.class_id else None,
            "className": batch.class_name,
            "status": batch.status,
        }
