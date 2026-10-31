"""D9-U 教材域大校规模读侧。

只替换目录/批次/发放/费用列表与库存/统计的只读查询：数据范围、DTO、状态机与所有写链
继续复用 academic_affairs_textbook_service / final facade。禁止全租户 `.all()` 后 Python 切片。
"""
from __future__ import annotations

from sqlalchemy import and_, case, func, or_

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
    from . import academic_affairs_textbook_final_facade as final

    with legacy.session() as db:
        ctx = legacy._ctx(user, db)
        sources = final._review_sources(db)
        conds = [
            AaTextbookReviewBatch.tenant_id == legacy._tid(),
            AaTextbookReviewBatch.is_deleted.is_(False),
        ]
        if status:
            conds.append(AaTextbookReviewBatch.status == status)
        if ctx.scope_type != "TENANT_ALL":
            if ctx.scope_type != "COLLEGE":
                return [], 0
            conds.extend([
                sources.c.college_id.in_(sorted(ctx.college_ids) or [-1]),
                sources.c.owner_count == sources.c.item_count, sources.c.college_count == 1,
                sources.c.min_term_id == AaTextbookReviewBatch.term_id,
                sources.c.max_term_id == AaTextbookReviewBatch.term_id,
                or_(AaTextbookReviewBatch.college_id.is_(None), AaTextbookReviewBatch.college_id == sources.c.college_id),
            ])
        page, page_size = _page(page, page_size)
        query = db.query(AaTextbookReviewBatch, sources).outerjoin(sources, sources.c.batch_id == AaTextbookReviewBatch.id).filter(*conds)
        total = query.count()
        rows = query.order_by(
            AaTextbookReviewBatch.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return [final._review_dto(ctx, row[0], row) for row in rows], total


def review_items(user, batch_id, page=1, page_size=20):
    from app.models import AaTextbookReviewBatchItem, AaTextbookSelection, AaTextbook
    from . import academic_affairs_textbook_final_facade as final

    with legacy.session() as db:
        ctx = legacy._ctx(user, db)
        batch = final._get_review_batch(db, batch_id)
        source = db.query(final._review_sources(db)).filter_by(batch_id=batch.id).first()
        if ctx.scope_type != "TENANT_ALL" and not (
            ctx.scope_type == "COLLEGE" and final._review_source_valid(batch, source)
            and source.college_id in ctx.college_ids
        ):
            raise legacy.no_data_scope("该教材审核批次不在您的学院范围内")
        query = db.query(AaTextbookSelection, AaTextbook).join(
            AaTextbookReviewBatchItem, AaTextbookReviewBatchItem.selection_id == AaTextbookSelection.id,
        ).outerjoin(AaTextbook, and_(AaTextbook.id == AaTextbookSelection.textbook_id,
            AaTextbook.tenant_id == legacy._tid(), AaTextbook.is_deleted.is_(False)),
        ).filter(AaTextbookSelection.tenant_id == legacy._tid(), AaTextbookSelection.is_deleted.is_(False),
            AaTextbookReviewBatchItem.tenant_id == legacy._tid(), AaTextbookReviewBatchItem.is_deleted.is_(False),
            AaTextbookReviewBatchItem.batch_id == batch.id)
        total = query.count()
        page, page_size = _page(page, min(page_size, 200))
        rows = query.order_by(AaTextbookSelection.id).offset((page - 1) * page_size).limit(page_size).all()
        return [{**legacy._sel_dto(selection), "isbn": book.isbn if book else None,
                 "edition": book.edition if book else None, "publisher": book.publisher if book else None}
                for selection, book in rows], total, final._review_dto(ctx, batch, source)


def list_order_batches(user, status=None, page=1, page_size=20):
    from app.models import AaTextbookOrderBatch

    with legacy.session() as db:
        legacy._require_school(legacy._ctx(user, db))
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
        legacy._require_school(legacy._ctx(user, db))
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
    from app.models import AaTextbookFeeLedger, AaTextbookRefund, StudentProfile, AaTextbookDistributionRecord

    with legacy.session() as db:
        legacy._require_school(legacy._ctx(user, db))
        conds = [
            AaTextbookFeeLedger.tenant_id == legacy._tid(),
            AaTextbookFeeLedger.is_deleted.is_(False),
        ]
        if status:
            conds.append(AaTextbookFeeLedger.status == status)
        page, page_size = _page(page, page_size)
        total = int(db.query(func.count(AaTextbookFeeLedger.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbookFeeLedger, StudentProfile, AaTextbookDistributionRecord.batch_id).outerjoin(
            StudentProfile, and_(StudentProfile.id == AaTextbookFeeLedger.student_id,
                StudentProfile.tenant_id == legacy._tid(), StudentProfile.is_deleted.is_(False)),
        ).outerjoin(
            AaTextbookDistributionRecord, and_(AaTextbookDistributionRecord.id == AaTextbookFeeLedger.distribution_record_id,
                AaTextbookDistributionRecord.tenant_id == legacy._tid(), AaTextbookDistributionRecord.is_deleted.is_(False)),
        ).filter(*conds).order_by(
            AaTextbookFeeLedger.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        ids = [row.id for row, _, _ in rows]
        refunds = {int(r.fee_id): r for r in db.query(AaTextbookRefund).filter(
            AaTextbookRefund.tenant_id == legacy._tid(), AaTextbookRefund.fee_id.in_(ids)).all()} if ids else {}
        return [{
            "feeId": str(row.id),
            "studentId": str(row.student_id),
            "studentName": student.real_name if student else None,
            "studentNo": student.student_no if student else None,
            "distributionBatchId": str(batch_id) if batch_id else None,
            "textbookName": row.textbook_name,
            "amount": legacy._fnum(row.amount),
            "paidAmount": legacy._fnum(row.paid_amount),
            "refundAmount": legacy._fnum(refunds[int(row.id)].amount) if int(row.id) in refunds else 0,
            "refundReason": refunds[int(row.id)].reason if int(row.id) in refunds else None,
            "refundAt": legacy._iso(refunds[int(row.id)].created_at) if int(row.id) in refunds else None,
            "status": row.status,
            "waiveReason": row.waive_reason,
        } for row, student, batch_id in rows], total


def my_student_distributions(user, student_id, page=1, page_size=20, *, record_id=None):
    """Current student's distribution page, with an optional self-scoped receipt reread."""
    from app.models import AaTextbook, AaTextbookDistributionRecord

    page, page_size = _page(page, page_size)
    page_size = min(page_size, 100)
    with legacy.session() as db:
        conds = [
            AaTextbookDistributionRecord.tenant_id == legacy._tid(),
            AaTextbookDistributionRecord.student_id == int(student_id),
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ]
        if record_id is not None:
            try:
                exact_record_id = int(record_id)
            except (TypeError, ValueError) as exc:
                raise legacy._bad("教材发放记录标识不正确") from exc
            if exact_record_id <= 0:
                raise legacy._bad("教材发放记录标识不正确")
            conds.append(AaTextbookDistributionRecord.id == exact_record_id)
        total = int(db.query(func.count(AaTextbookDistributionRecord.id)).filter(*conds).scalar() or 0)
        rows = db.query(AaTextbookDistributionRecord, AaTextbook.isbn).outerjoin(
            AaTextbook,
            and_(
                AaTextbook.id == AaTextbookDistributionRecord.textbook_id,
                AaTextbook.tenant_id == legacy._tid(),
                AaTextbook.is_deleted.is_(False),
            ),
        ).filter(*conds).order_by(
            AaTextbookDistributionRecord.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [{
                "recordId": str(record.id), "textbookName": record.textbook_name,
                "qty": record.qty, "isbn": isbn, "status": record.status,
                "receivedAt": legacy._iso(record.received_at),
            } for record, isbn in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": page * page_size < total,
        }


def my_student_fees(user, student_id, page=1, page_size=20):
    """Current student's fee page plus full SQL totals; never materialize the ledger in Python."""
    from app.models import AaTextbookFeeLedger, AaTextbookRefund

    page, page_size = _page(page, page_size)
    page_size = min(page_size, 100)
    with legacy.session() as db:
        conds = [
            AaTextbookFeeLedger.tenant_id == legacy._tid(),
            AaTextbookFeeLedger.student_id == int(student_id),
            AaTextbookFeeLedger.is_deleted.is_(False),
        ]
        total = int(db.query(func.count(AaTextbookFeeLedger.id)).filter(*conds).scalar() or 0)
        has_refund = db.query(AaTextbookRefund.id).filter(
            AaTextbookRefund.tenant_id == AaTextbookFeeLedger.tenant_id,
            AaTextbookRefund.fee_id == AaTextbookFeeLedger.id,
        ).exists()
        gross_amount, excluded_amount, waived_amount, total_paid = db.query(
            func.coalesce(func.sum(AaTextbookFeeLedger.amount), 0),
            func.coalesce(func.sum(case(
                (AaTextbookFeeLedger.status.in_(["WAIVED", "REFUNDED"]), AaTextbookFeeLedger.amount), else_=0,
            )), 0),
            func.coalesce(func.sum(case(
                (and_(AaTextbookFeeLedger.status == "WAIVED", ~has_refund), AaTextbookFeeLedger.amount), else_=0,
            )), 0),
            func.coalesce(func.sum(AaTextbookFeeLedger.paid_amount), 0),
        ).filter(*conds).one()
        gross_amount = float(gross_amount or 0)
        excluded_amount = float(excluded_amount or 0)
        waived_amount = float(waived_amount or 0)
        refunded = float(db.query(func.coalesce(func.sum(AaTextbookRefund.amount), 0)).join(
            AaTextbookFeeLedger, and_(AaTextbookFeeLedger.id == AaTextbookRefund.fee_id,
                AaTextbookFeeLedger.tenant_id == AaTextbookRefund.tenant_id),
        ).filter(*conds, AaTextbookRefund.tenant_id == legacy._tid()).scalar() or 0)
        total_paid = float(total_paid or 0) - refunded
        total_due = gross_amount - excluded_amount
        rows = db.query(AaTextbookFeeLedger).filter(*conds).order_by(
            AaTextbookFeeLedger.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size).all()
        ids = [fee.id for fee in rows]
        refunds = {int(r.fee_id): r for r in db.query(AaTextbookRefund).filter(
            AaTextbookRefund.tenant_id == legacy._tid(), AaTextbookRefund.fee_id.in_(ids)).all()} if ids else {}
        return {
            "items": [{
                "feeId": str(fee.id), "textbookName": fee.textbook_name,
                "amount": legacy._fnum(fee.amount), "paidAmount": legacy._fnum(fee.paid_amount),
                "refundAmount": legacy._fnum(refunds[int(fee.id)].amount) if int(fee.id) in refunds else 0,
                "status": fee.status,
            } for fee in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": page * page_size < total,
            "totalDue": round(total_due, 2),
            "totalPaid": round(total_paid, 2),
            "totalRefunded": round(refunded, 2),
            "waivedAmount": round(waived_amount, 2),
            "unpaid": round(total_due - total_paid, 2),
        }


def textbook_stock(user):
    from app.models import AaTextbookDistributionRecord, AaTextbookOrderItem
    from .academic_affairs_textbook_final_facade import _ACTIVE_ALLOCATION_STATUSES

    with legacy.session() as db:
        legacy._require_school(legacy._ctx(user, db))
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
            AaTextbookDistributionRecord.status,
            func.max(AaTextbookDistributionRecord.textbook_name),
            func.coalesce(func.sum(AaTextbookDistributionRecord.qty), 0),
        ).filter(
            AaTextbookDistributionRecord.tenant_id == legacy._tid(),
            AaTextbookDistributionRecord.status.in_(_ACTIVE_ALLOCATION_STATUSES),
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ).group_by(AaTextbookDistributionRecord.textbook_id, AaTextbookDistributionRecord.status).all()
        stock = {int(book_id): {"textbookId": str(book_id), "textbookName": name,
            "arrivedQty": int(arrived or 0), "reservedQty": 0, "distributedQty": 0}
            for book_id, name, arrived in arrived_rows}
        for book_id, status, name, qty in distributed_rows:
            row = stock.setdefault(int(book_id), {"textbookId": str(book_id), "textbookName": name,
                "arrivedQty": 0, "reservedQty": 0, "distributedQty": 0})
            row["reservedQty" if status == "PENDING" else "distributedQty"] += int(qty or 0)
        for row in stock.values():
            row["stockQty"] = row["arrivedQty"] - row["reservedQty"] - row["distributedQty"]
            row["dataConflict"] = row["stockQty"] < 0
        return sorted(stock.values(), key=lambda row: (row['textbookName'] or '', row['textbookId']))


def stats(user):
    from app.models import AaTextbookFeeLedger, AaTextbookRefund, AaTextbookOrderBatch, AaTextbookOrderItem, AaTextbookSelection
    from app.core.permissions import _match

    with legacy.session() as db:
        ctx = legacy._ctx(user, db)
        legacy._require_school(ctx)
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
            AaTextbookOrderBatch.status != "CANCELLED",
        ).scalar() or 0)
        order_qty, arrived_qty = db.query(
            func.coalesce(func.sum(AaTextbookOrderItem.order_qty), 0),
            func.coalesce(func.sum(AaTextbookOrderItem.arrived_qty), 0),
        ).join(AaTextbookOrderBatch, AaTextbookOrderBatch.id == AaTextbookOrderItem.order_batch_id).filter(
            AaTextbookOrderBatch.tenant_id == legacy._tid(),
            AaTextbookOrderBatch.is_deleted.is_(False),
            AaTextbookOrderBatch.status != "CANCELLED",
            AaTextbookOrderItem.tenant_id == legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).one()
        fee_visible = _match("academicAffairs.textbook.fee.manage", ctx.permission_codes)
        unpaid = refunded = pending_returns = None
        if fee_visible:
            unpaid = db.query(func.coalesce(func.sum(func.greatest(AaTextbookFeeLedger.amount - func.coalesce(AaTextbookFeeLedger.paid_amount, 0), 0)), 0)).filter(
                AaTextbookFeeLedger.tenant_id == legacy._tid(),
                AaTextbookFeeLedger.status.in_(["UNPAID", "PARTIAL"]),
                AaTextbookFeeLedger.is_deleted.is_(False),
            ).scalar() or 0
            refunded = db.query(func.coalesce(func.sum(AaTextbookRefund.amount), 0)).join(
                AaTextbookFeeLedger, and_(AaTextbookFeeLedger.id == AaTextbookRefund.fee_id,
                                          AaTextbookFeeLedger.tenant_id == AaTextbookRefund.tenant_id),
            ).filter(AaTextbookRefund.tenant_id == legacy._tid(), AaTextbookFeeLedger.is_deleted.is_(False)).scalar() or 0
            pending_returns = db.query(func.count(AaTextbookFeeLedger.id)).filter(
                AaTextbookFeeLedger.tenant_id == legacy._tid(), AaTextbookFeeLedger.is_deleted.is_(False),
                AaTextbookFeeLedger.status == "REFUNDED",
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
            "feeVisible": fee_visible,
            "unpaidAmount": round(float(unpaid), 2) if fee_visible else None,
            "refundedAmount": round(float(refunded), 2) if fee_visible else None,
            "refundPendingReturnCount": int(pending_returns) if fee_visible else None,
        }
