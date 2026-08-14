"""D9-U 教材域大校规模读侧。

只替换目录/批次/发放/费用列表与库存/统计的只读查询：数据范围、DTO、状态机与所有写链
继续复用 academic_affairs_textbook_service / final facade。禁止全租户 `.all()` 后 Python 切片。
"""
from __future__ import annotations

from sqlalchemy import func, or_

from . import academic_affairs_textbook_service as legacy


def _page(page, page_size):
    return max(1, int(page or 1)), max(1, int(page_size or 1))


def list_textbooks(user, keyword=None, status=None, page=1, page_size=20):
    from app.models import AaTextbook

    with legacy.session() as db:
        legacy._ctx(user, db)
        conds = [AaTextbook.tenant_id == legacy._tid(), AaTextbook.is_deleted.is_(False)]
        if status:
            conds.append(AaTextbook.status == status)
        if keyword:
            pattern = f"%{str(keyword).strip().lower()}%"
            conds.append(or_(
                func.lower(func.coalesce(AaTextbook.name, "")).like(pattern),
                func.lower(func.coalesce(AaTextbook.isbn, "")).like(pattern),
            ))
        page, page_size = _page(page, page_size)
        total = int(db.query(func.count(AaTextbook.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbook).filter(*conds).order_by(AaTextbook.id.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return [legacy._tb_dto(row) for row in rows], total


def list_review_batches(user, status=None, page=1, page_size=20):
    from app.models import AaTextbookReviewBatch

    with legacy.session() as db:
        legacy._ctx(user, db)
        conds = [
            AaTextbookReviewBatch.tenant_id == legacy._tid(),
            AaTextbookReviewBatch.is_deleted.is_(False),
        ]
        if status:
            conds.append(AaTextbookReviewBatch.status == status)
        page, page_size = _page(page, page_size)
        total = int(db.query(func.count(AaTextbookReviewBatch.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbookReviewBatch).filter(*conds).order_by(
            AaTextbookReviewBatch.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return [legacy._rb_dto(row) for row in rows], total


def list_order_batches(user, status=None, page=1, page_size=20):
    from app.models import AaTextbookOrderBatch

    with legacy.session() as db:
        legacy._ctx(user, db)
        conds = [
            AaTextbookOrderBatch.tenant_id == legacy._tid(),
            AaTextbookOrderBatch.is_deleted.is_(False),
        ]
        if status:
            conds.append(AaTextbookOrderBatch.status == status)
        page, page_size = _page(page, page_size)
        total = int(db.query(func.count(AaTextbookOrderBatch.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbookOrderBatch).filter(*conds).order_by(
            AaTextbookOrderBatch.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return [legacy._ob_dto(row) for row in rows], total


def list_distribution_records(user, batch_id, page=1, page_size=100):
    from app.models import AaTextbookDistributionRecord

    with legacy.session() as db:
        legacy._ctx(user, db)
        conds = [
            AaTextbookDistributionRecord.batch_id == int(batch_id),
            AaTextbookDistributionRecord.tenant_id == legacy._tid(),
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ]
        page, page_size = _page(page, page_size)
        total = int(db.query(func.count(AaTextbookDistributionRecord.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbookDistributionRecord).filter(*conds).order_by(
            AaTextbookDistributionRecord.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return [{
            "recordId": str(row.id),
            "studentId": str(row.student_id),
            "textbookName": row.textbook_name,
            "qty": row.qty,
            "status": row.status,
        } for row in rows], total


def list_fees(user, status=None, page=1, page_size=50):
    from app.models import AaTextbookFeeLedger

    with legacy.session() as db:
        legacy._ctx(user, db)
        conds = [
            AaTextbookFeeLedger.tenant_id == legacy._tid(),
            AaTextbookFeeLedger.is_deleted.is_(False),
        ]
        if status:
            conds.append(AaTextbookFeeLedger.status == status)
        page, page_size = _page(page, page_size)
        total = int(db.query(func.count(AaTextbookFeeLedger.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbookFeeLedger).filter(*conds).order_by(
            AaTextbookFeeLedger.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return [{
            "feeId": str(row.id),
            "studentId": str(row.student_id),
            "textbookName": row.textbook_name,
            "amount": legacy._fnum(row.amount),
            "paidAmount": legacy._fnum(row.paid_amount),
            "status": row.status,
            "waiveReason": row.waive_reason,
        } for row in rows], total


def textbook_stock(user):
    from app.models import AaTextbookDistributionRecord, AaTextbookOrderItem

    with legacy.session() as db:
        legacy._ctx(user, db)
        arrived_rows = db.query(
            AaTextbookOrderItem.textbook_id,
            func.max(AaTextbookOrderItem.textbook_name),
            func.coalesce(func.sum(AaTextbookOrderItem.arrived_qty), 0),
        ).filter(
            AaTextbookOrderItem.tenant_id == legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).group_by(AaTextbookOrderItem.textbook_id).all()
        distributed_rows = db.query(
            AaTextbookDistributionRecord.textbook_id,
            func.coalesce(func.sum(AaTextbookDistributionRecord.qty), 0),
        ).filter(
            AaTextbookDistributionRecord.tenant_id == legacy._tid(),
            AaTextbookDistributionRecord.status == "RECEIVED",
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ).group_by(AaTextbookDistributionRecord.textbook_id).all()
        distributed = {int(textbook_id): int(qty or 0) for textbook_id, qty in distributed_rows}
        return [{
            "textbookId": str(textbook_id),
            "textbookName": name,
            "arrivedQty": int(arrived or 0),
            "distributedQty": distributed.get(int(textbook_id), 0),
            "stockQty": max(0, int(arrived or 0) - distributed.get(int(textbook_id), 0)),
        } for textbook_id, name, arrived in arrived_rows]


def stats(user):
    from app.models import AaTextbookFeeLedger, AaTextbookOrderBatch, AaTextbookOrderItem, AaTextbookSelection

    with legacy.session() as db:
        legacy._ctx(user, db)
        selection_total = int(db.query(func.count(AaTextbookSelection.id)).filter(
            AaTextbookSelection.tenant_id == legacy._tid(),
            AaTextbookSelection.is_deleted.is_(False),
        ).scalar() or 0)
        selection_approved = int(db.query(func.count(AaTextbookSelection.id)).filter(
            AaTextbookSelection.tenant_id == legacy._tid(),
            AaTextbookSelection.status.in_(["APPROVED", "ORDERED"]),
            AaTextbookSelection.is_deleted.is_(False),
        ).scalar() or 0)
        order_batches = int(db.query(func.count(AaTextbookOrderBatch.id)).filter(
            AaTextbookOrderBatch.tenant_id == legacy._tid(),
            AaTextbookOrderBatch.is_deleted.is_(False),
        ).scalar() or 0)
        order_qty, arrived_qty = db.query(
            func.coalesce(func.sum(AaTextbookOrderItem.order_qty), 0),
            func.coalesce(func.sum(AaTextbookOrderItem.arrived_qty), 0),
        ).filter(
            AaTextbookOrderItem.tenant_id == legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).one()
        unpaid = db.query(func.coalesce(func.sum(AaTextbookFeeLedger.amount), 0)).filter(
            AaTextbookFeeLedger.tenant_id == legacy._tid(),
            AaTextbookFeeLedger.status.in_(["UNPAID", "PARTIAL"]),
            AaTextbookFeeLedger.is_deleted.is_(False),
        ).scalar() or 0
        order_qty = int(order_qty or 0)
        arrived_qty = int(arrived_qty or 0)
        return {
            "selectionTotal": selection_total,
            "selectionApproved": selection_approved,
            "orderBatchCount": order_batches,
            "orderQty": order_qty,
            "arrivedQty": arrived_qty,
            "arrivalRate": round(arrived_qty / order_qty, 4) if order_qty else 0,
            "unpaidAmount": round(float(unpaid or 0), 2),
        }
