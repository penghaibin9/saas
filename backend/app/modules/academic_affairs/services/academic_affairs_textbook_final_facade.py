"""教材域单一公开入口。

复用原教材 Service 的只读与目录能力，集中承载学期写保护、审核/征订来源、价格快照、
库存并发、发放名单、签收计费、退领和费用终态。禁止通过导入副作用修改原模块。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from app.core.exceptions import AppException, not_found

from . import academic_affairs_textbook_service as _legacy

_ACTIVE_ALLOCATION_STATUSES = ("PENDING", "RECEIVED", "EXCHANGED")
_ELIGIBLE_STUDENT_STATUSES = {"NORMAL", "REGISTERED", "ON_CAMPUS"}


def __getattr__(name):
    return getattr(_legacy, name)


def _unique_positive_ids(values):
    seen = set()
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if not text.isdigit():
            continue
        number = int(text)
        if number <= 0 or number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def _invalid_order_quantity_ids(rows):
    return [
        int(row.id) for row in (rows or [])
        if not isinstance(getattr(row, "expected_qty", None), int)
        or int(row.expected_qty) <= 0
    ]


def _missing_price_textbook_ids(catalog_by_id, textbook_ids):
    return [
        int(textbook_id) for textbook_id in textbook_ids
        if textbook_id not in catalog_by_id
        or catalog_by_id[textbook_id].unit_price is None
    ]


def _distribution_shortage(arrived, allocated, requested):
    available = max(0, int(arrived or 0) - int(allocated or 0))
    return max(0, int(requested or 0) - available)


def _term(db, term_id):
    from app.models import AaTerm
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    if not term_id:
        raise AppException("VALIDATION_ERROR", "教材学期型业务必须绑定正式学期termId")
    try:
        value = int(term_id)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "termId格式不正确") from exc
    row = db.query(AaTerm).filter(
        AaTerm.id == value,
        AaTerm.tenant_id == _legacy._tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not row:
        raise not_found("学期不存在")
    guard_term_writable(db, row.id)
    return row


def _task_term(db, task_id):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == int(task_id),
        AaTeachingTask.tenant_id == _legacy._tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if not task:
        raise not_found("教学任务不存在")
    batch = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.id == task.batch_id,
        AaTeachingTaskBatch.tenant_id == _legacy._tid(),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).first()
    if not batch:
        raise AppException("DATA_CONFLICT", "教学任务未关联有效教学任务批次", http_status=409)
    _term(db, batch.term_id)
    return task, batch


def _selection_term(db, selection):
    _task, batch = _task_term(db, selection.task_id)
    return batch


def _get_selection(db, selection_id, *, lock=False):
    from app.models import AaTextbookSelection

    query = db.query(AaTextbookSelection).filter(
        AaTextbookSelection.id == int(selection_id),
        AaTextbookSelection.tenant_id == _legacy._tid(),
        AaTextbookSelection.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        raise not_found("选用记录不存在")
    return row


def _get_review_batch(db, batch_id, *, lock=False):
    from app.models import AaTextbookReviewBatch

    query = db.query(AaTextbookReviewBatch).filter(
        AaTextbookReviewBatch.id == int(batch_id),
        AaTextbookReviewBatch.tenant_id == _legacy._tid(),
        AaTextbookReviewBatch.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        raise not_found("审核批次不存在")
    return row


def _get_order_batch(db, batch_id, *, lock=False):
    from app.models import AaTextbookOrderBatch

    query = db.query(AaTextbookOrderBatch).filter(
        AaTextbookOrderBatch.id == int(batch_id),
        AaTextbookOrderBatch.tenant_id == _legacy._tid(),
        AaTextbookOrderBatch.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        raise not_found("征订批次不存在")
    return row


def _distribution_chain(db, record_id, *, lock=True):
    from app.models import AaTextbookDistributionBatch, AaTextbookDistributionRecord

    record_query = db.query(AaTextbookDistributionRecord).filter(
        AaTextbookDistributionRecord.id == int(record_id),
        AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
        AaTextbookDistributionRecord.is_deleted.is_(False),
    )
    if lock:
        record_query = record_query.with_for_update()
    record = record_query.first()
    if not record:
        raise not_found("发放记录不存在")

    distribution_query = db.query(AaTextbookDistributionBatch).filter(
        AaTextbookDistributionBatch.id == record.batch_id,
        AaTextbookDistributionBatch.tenant_id == _legacy._tid(),
        AaTextbookDistributionBatch.is_deleted.is_(False),
    )
    if lock:
        distribution_query = distribution_query.with_for_update()
    distribution = distribution_query.first()
    if not distribution:
        raise AppException("DATA_CONFLICT", "发放记录未关联有效发放批次", http_status=409)

    order = _get_order_batch(db, distribution.order_batch_id, lock=lock)
    _term(db, order.term_id)
    return record, distribution, order


def _fee_chain(db, fee_id):
    from app.models import AaTextbookFeeLedger

    preview = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.id == int(fee_id),
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).first()
    if not preview:
        raise not_found("费用记录不存在")
    record, distribution, order = _distribution_chain(db, preview.distribution_record_id, lock=True)
    fee = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.id == int(fee_id),
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).with_for_update().first()
    if not fee:
        raise not_found("费用记录不存在")
    return fee, record, distribution, order


def _refresh_distribution_batch(db, distribution):
    from app.models import AaTextbookDistributionRecord

    pending = db.query(AaTextbookDistributionRecord).filter(
        AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
        AaTextbookDistributionRecord.batch_id == distribution.id,
        AaTextbookDistributionRecord.status == "PENDING",
        AaTextbookDistributionRecord.is_deleted.is_(False),
    ).count()
    if pending == 0:
        distribution.status = "COMPLETED"
        distribution.completed_at = distribution.completed_at or datetime.utcnow()
    else:
        distribution.status = "DISTRIBUTING"


def create_selection(user, body):
    from app.core.affairs_security import _derive_keys
    from app.models import AaTextbook, AaTextbookSelection

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        task, task_batch = _task_term(db, int(body.taskId))
        textbook = db.query(AaTextbook).filter(
            AaTextbook.id == int(body.textbookId),
            AaTextbook.tenant_id == _legacy._tid(),
            AaTextbook.is_deleted.is_(False),
        ).first()
        if not textbook:
            raise not_found("教材不存在")
        active = db.query(AaTextbookSelection).filter(
            AaTextbookSelection.tenant_id == _legacy._tid(),
            AaTextbookSelection.task_id == task.id,
            AaTextbookSelection.status.notin_(["RETURNED", "ORDERED"]),
            AaTextbookSelection.is_deleted.is_(False),
        ).first()
        if active:
            raise _legacy._conflict("该教学任务已有未终结的教材选用")
        keys = _derive_keys(user)
        row = AaTextbookSelection(
            tenant_id=_legacy._tid(),
            task_id=task.id,
            textbook_id=textbook.id,
            textbook_name=textbook.name,
            course_name=getattr(task, "course_name", None),
            college_id=task_batch.college_id,
            officer_key=next(iter(keys), None) if keys else _legacy._op(),
            expected_qty=getattr(body, "expectedQty", None),
            remark=getattr(body, "remark", None),
            status="DRAFT",
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_TEXTBOOK_SELECTION", row.id, "TEXTBOOK_SELECTION_CREATE", f"选用 {textbook.name}")
        db.commit()
        return _legacy._sel_dto(row)


def submit_selection(user, selection_id):
    with _legacy.session() as db:
        _legacy._ctx(user, db)
        row = _get_selection(db, selection_id, lock=True)
        _selection_term(db, row)
        if row.status not in ("DRAFT", "RETURNED"):
            raise _legacy._invalid("仅草稿/退回选用可提交")
        row.status = "SUBMITTED"
        _legacy._audit(db, "AA_TEXTBOOK_SELECTION", row.id, "TEXTBOOK_SELECTION_SUBMIT", "提交选用")
        db.commit()
        return _legacy._sel_dto(row)


def withdraw_selection(user, selection_id):
    with _legacy.session() as db:
        _legacy._ctx(user, db)
        row = _get_selection(db, selection_id, lock=True)
        _selection_term(db, row)
        if row.status != "DRAFT":
            raise _legacy._invalid("仅草稿可撤回")
        row.is_deleted = True
        _legacy._audit(db, "AA_TEXTBOOK_SELECTION", row.id, "TEXTBOOK_SELECTION_WITHDRAW", "撤回")
        db.commit()
        return {"selectionId": str(row.id), "withdrawn": True}


def create_review_batch(user, body):
    from app.models import AaTextbookReviewBatch, AaTextbookReviewBatchItem, AaTextbookSelection

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        term = _term(db, getattr(body, "termId", None))
        selection_ids = _unique_positive_ids(getattr(body, "selectionIds", None))
        if not selection_ids:
            raise _legacy._bad("审核批次至少选择一条已提交教材选用")
        selections = db.query(AaTextbookSelection).filter(
            AaTextbookSelection.tenant_id == _legacy._tid(),
            AaTextbookSelection.id.in_(selection_ids),
            AaTextbookSelection.is_deleted.is_(False),
        ).with_for_update().all()
        by_id = {int(row.id): row for row in selections}
        accepted = []
        for selection_id in selection_ids:
            row = by_id.get(selection_id)
            if not row:
                raise not_found(f"教材选用 {selection_id} 不存在")
            if row.status != "SUBMITTED":
                raise _legacy._invalid(f"教材选用 {selection_id} 不是待审核状态")
            task_batch = _selection_term(db, row)
            if int(task_batch.term_id) != int(term.id):
                raise AppException("DATA_CONFLICT", "审核批次不能混入其它学期教材选用", http_status=409)
            accepted.append(row)
        batch = AaTextbookReviewBatch(
            tenant_id=_legacy._tid(),
            batch_name=(getattr(body, "batchName", None) or "教材审核批次").strip(),
            term_id=term.id,
            status="DRAFT",
        )
        db.add(batch)
        db.flush()
        for row in accepted:
            db.add(AaTextbookReviewBatchItem(
                tenant_id=_legacy._tid(),
                batch_id=batch.id,
                selection_id=row.id,
            ))
            row.status = "REVIEWING"
        _legacy._audit(
            db,
            "AA_TEXTBOOK_REVIEW",
            batch.id,
            "TEXTBOOK_REVIEW_CREATE",
            f"纳入 {len(accepted)} 条选用",
        )
        db.commit()
        return _legacy._rb_dto(batch)


def review_batch_advance(user, batch_id, action, reason=""):
    from app.models import AaTextbookReviewBatchItem, AaTextbookSelection

    action = str(action or "").upper()
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _get_review_batch(db, batch_id, lock=True)
        _term(db, batch.term_id)
        if action == "APPROVE":
            if batch.status not in _legacy._RB_CHAIN:
                raise _legacy._invalid("该批次已完成审核")
            batch.status = _legacy._RB_CHAIN[batch.status]
            if batch.status == "PUBLISHED":
                items = db.query(AaTextbookReviewBatchItem).filter(
                    AaTextbookReviewBatchItem.batch_id == batch.id,
                    AaTextbookReviewBatchItem.tenant_id == _legacy._tid(),
                ).all()
                selection_ids = [int(item.selection_id) for item in items]
                selections = db.query(AaTextbookSelection).filter(
                    AaTextbookSelection.tenant_id == _legacy._tid(),
                    AaTextbookSelection.id.in_(selection_ids or [0]),
                    AaTextbookSelection.is_deleted.is_(False),
                ).with_for_update().all()
                for selection in selections:
                    selection.status = "APPROVED"
        elif action == "RETURN":
            reason = str(reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("退回原因必填且不少于5字")
            batch.status = "RETURNED"
            batch.reject_reason = reason
            items = db.query(AaTextbookReviewBatchItem).filter(
                AaTextbookReviewBatchItem.batch_id == batch.id,
                AaTextbookReviewBatchItem.tenant_id == _legacy._tid(),
            ).all()
            selection_ids = [int(item.selection_id) for item in items]
            selections = db.query(AaTextbookSelection).filter(
                AaTextbookSelection.tenant_id == _legacy._tid(),
                AaTextbookSelection.id.in_(selection_ids or [0]),
                AaTextbookSelection.is_deleted.is_(False),
            ).with_for_update().all()
            for selection in selections:
                selection.status = "RETURNED"
                selection.reject_reason = reason
        else:
            raise _legacy._bad("非法审核动作")
        _legacy._audit(
            db,
            "AA_TEXTBOOK_REVIEW",
            batch.id,
            "TEXTBOOK_REVIEW_ADVANCE",
            f"{action}->{batch.status}",
        )
        db.commit()
        return _legacy._rb_dto(batch)


def create_order_batch(user, body):
    from app.models import (
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTextbook,
        AaTextbookOrderBatch,
        AaTextbookOrderItem,
        AaTextbookSelection,
    )

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        term = _term(db, getattr(body, "termId", None))
        selections = db.query(AaTextbookSelection).join(
            AaTeachingTask, AaTeachingTask.id == AaTextbookSelection.task_id,
        ).join(
            AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
        ).filter(
            AaTextbookSelection.tenant_id == _legacy._tid(),
            AaTextbookSelection.status == "APPROVED",
            AaTextbookSelection.is_deleted.is_(False),
            AaTeachingTask.tenant_id == _legacy._tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTaskBatch.tenant_id == _legacy._tid(),
            AaTeachingTaskBatch.term_id == term.id,
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).with_for_update().all()
        if not selections:
            raise _legacy._bad("本学期没有尚未征订的已备案教材选用")

        invalid_quantity_ids = _invalid_order_quantity_ids(selections)
        if invalid_quantity_ids:
            preview = "、".join(str(value) for value in invalid_quantity_ids[:10])
            suffix = "等" if len(invalid_quantity_ids) > 10 else ""
            raise AppException(
                "DATA_CONFLICT",
                f"教材选用 {preview}{suffix} 未填写正整数预计数量，不能生成征订批次",
                http_status=409,
            )

        textbook_ids = sorted({int(row.textbook_id) for row in selections})
        catalogs = db.query(AaTextbook).filter(
            AaTextbook.tenant_id == _legacy._tid(),
            AaTextbook.id.in_(textbook_ids),
            AaTextbook.is_deleted.is_(False),
        ).with_for_update().all()
        catalog_by_id = {int(row.id): row for row in catalogs}
        missing_catalog_ids = [value for value in textbook_ids if value not in catalog_by_id]
        if missing_catalog_ids:
            raise not_found(f"教材目录不存在或已删除：{missing_catalog_ids[:10]}")
        missing_price_ids = _missing_price_textbook_ids(catalog_by_id, textbook_ids)
        if missing_price_ids:
            raise AppException(
                "DATA_CONFLICT",
                f"教材目录缺少定价，不能形成征订价格快照：{missing_price_ids[:10]}",
                http_status=409,
            )

        previous_count = db.query(AaTextbookOrderBatch).filter(
            AaTextbookOrderBatch.tenant_id == _legacy._tid(),
            AaTextbookOrderBatch.term_id == term.id,
            AaTextbookOrderBatch.status != "CANCELLED",
            AaTextbookOrderBatch.is_deleted.is_(False),
        ).count()
        supplemental = previous_count > 0
        batch = AaTextbookOrderBatch(
            tenant_id=_legacy._tid(),
            batch_name=(
                getattr(body, "batchName", None)
                or ("教材补订批次" if supplemental else "教材征订批次")
            ).strip(),
            term_id=term.id,
            status="DRAFT",
        )
        db.add(batch)
        db.flush()

        merged = {}
        for selection in selections:
            textbook_id = int(selection.textbook_id)
            merged.setdefault(textbook_id, {
                "name": selection.textbook_name or catalog_by_id[textbook_id].name,
                "qty": 0,
            })
            merged[textbook_id]["qty"] += int(selection.expected_qty)
            selection.status = "ORDERED"
            _legacy._audit(
                db,
                "AA_TEXTBOOK_ORDER",
                batch.id,
                "TEXTBOOK_ORDER_SOURCE",
                f"selectionId={selection.id}",
            )

        for textbook_id, info in merged.items():
            catalog = catalog_by_id[textbook_id]
            db.add(AaTextbookOrderItem(
                tenant_id=_legacy._tid(),
                order_batch_id=batch.id,
                textbook_id=textbook_id,
                textbook_name=info["name"],
                order_qty=info["qty"],
                arrived_qty=0,
                unit_price_snapshot=catalog.unit_price,
            ))

        _legacy._audit(
            db,
            "AA_TEXTBOOK_ORDER",
            batch.id,
            "TEXTBOOK_ORDER_GENERATE",
            f"{'补订' if supplemental else '首批征订'}；教材{len(merged)}种；来源选用{len(selections)}条",
        )
        db.commit()
        return {
            "orderBatchId": str(batch.id),
            "itemCount": len(merged),
            "selectionCount": len(selections),
            "supplemental": supplemental,
        }


def submit_order(user, batch_id):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _get_order_batch(db, batch_id, lock=True)
        _term(db, batch.term_id)
        if batch.status != "DRAFT":
            raise _legacy._invalid("仅 DRAFT 征订批次可提交")
        batch.status = "ORDERED"
        batch.submit_at = datetime.utcnow()
        _legacy._audit(db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_SUBMIT", "提交征订")
        db.commit()
        return _legacy._ob_dto(batch)


def record_arrival(user, item_id, arrived_qty):
    from app.models import AaTextbookOrderItem

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        item = db.query(AaTextbookOrderItem).filter(
            AaTextbookOrderItem.id == int(item_id),
            AaTextbookOrderItem.tenant_id == _legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).with_for_update().first()
        if not item:
            raise not_found("征订明细不存在")
        order = _get_order_batch(db, item.order_batch_id, lock=True)
        _term(db, order.term_id)
        if order.status not in ("ORDERED", "PARTIALLY_ARRIVED"):
            raise _legacy._invalid("仅已征订/部分到货批次可登记到货")
        value = int(arrived_qty)
        current = int(item.arrived_qty or 0)
        ordered = int(item.order_qty or 0)
        if value < current:
            raise _legacy._invalid("累计到货量不可小于已登记数量；冲销须走供应商退货流程")
        if value > ordered:
            raise _legacy._invalid(f"累计到货量 {value} 不能超过征订数量 {ordered}")
        item.arrived_qty = value
        items = db.query(AaTextbookOrderItem).filter(
            AaTextbookOrderItem.order_batch_id == order.id,
            AaTextbookOrderItem.tenant_id == _legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).all()
        all_arrived = bool(items) and all(
            int(row.arrived_qty or 0) >= int(row.order_qty or 0) for row in items
        )
        any_arrived = any(int(row.arrived_qty or 0) > 0 for row in items)
        order.status = "ARRIVED" if all_arrived else (
            "PARTIALLY_ARRIVED" if any_arrived else "ORDERED"
        )
        _legacy._audit(
            db,
            "AA_TEXTBOOK_ORDER",
            order.id,
            "TEXTBOOK_ARRIVAL",
            f"itemId={item.id};累计到货={value}/{ordered}",
        )
        db.commit()
        return {"itemId": str(item.id), "arrivedQty": value, "batchStatus": order.status}


def archive_order_batch(user, batch_id):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _get_order_batch(db, batch_id, lock=True)
        _term(db, batch.term_id)
        if batch.status == "ARCHIVED":
            return _legacy._ob_dto(batch)
        if batch.status != "ARRIVED":
            raise _legacy._invalid("仅 ARRIVED 批次可归档")
        batch.status = "ARCHIVED"
        _legacy._audit(db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_ARCHIVE", "归档")
        db.commit()
        return _legacy._ob_dto(batch)


def cancel_order_batch(user, batch_id, reason):
    from app.models import AffairsAuditTrail, AaTextbookOrderItem, AaTextbookSelection

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("取消原因必填且不少于5字")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _get_order_batch(db, batch_id, lock=True)
        _term(db, batch.term_id)
        if batch.status == "CANCELLED":
            return _legacy._ob_dto(batch)
        if batch.status not in ("DRAFT", "ORDERED"):
            raise _legacy._invalid("仅未到货的草稿/已提交征订批次可取消")
        arrived = db.query(AaTextbookOrderItem).filter(
            AaTextbookOrderItem.tenant_id == _legacy._tid(),
            AaTextbookOrderItem.order_batch_id == batch.id,
            AaTextbookOrderItem.arrived_qty > 0,
            AaTextbookOrderItem.is_deleted.is_(False),
        ).count()
        if arrived:
            raise _legacy._invalid("批次已有到货，不能直接取消；请先完成供应商退货与财务核对")
        sources = db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == _legacy._tid(),
            AffairsAuditTrail.biz_type == "AA_TEXTBOOK_ORDER",
            AffairsAuditTrail.biz_id == batch.id,
            AffairsAuditTrail.action == "TEXTBOOK_ORDER_SOURCE",
        ).all()
        selection_ids = []
        for source in sources:
            detail = str(source.detail or "")
            if detail.startswith("selectionId=") and detail.split("=", 1)[1].isdigit():
                selection_ids.append(int(detail.split("=", 1)[1]))
        if not selection_ids:
            raise AppException(
                "DATA_CONFLICT",
                "历史征订批次缺少来源选用快照，不能自动取消并回退状态；请完成到货或人工数据治理",
                http_status=409,
            )
        selections = db.query(AaTextbookSelection).filter(
            AaTextbookSelection.tenant_id == _legacy._tid(),
            AaTextbookSelection.id.in_(selection_ids),
            AaTextbookSelection.is_deleted.is_(False),
        ).with_for_update().all()
        for selection in selections:
            if selection.status == "ORDERED":
                selection.status = "APPROVED"
        batch.status = "CANCELLED"
        _legacy._audit(db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_CANCEL", reason)
        db.commit()
        return _legacy._ob_dto(batch)


def generate_distribution(user, order_batch_id, class_id, student_ids):
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookOrderItem,
        SchoolClass,
        StudentProfile,
    )

    class_text = str(class_id or "").strip()
    if not class_text.isdigit():
        raise _legacy._bad("发放批次必须选择真实班级classId")
    class_value = int(class_text)
    requested_ids = _unique_positive_ids(student_ids)
    if not requested_ids:
        raise _legacy._bad("发放名单至少包含一名学生")

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        order = _get_order_batch(db, order_batch_id, lock=True)
        _term(db, order.term_id)
        if order.status not in ("ARRIVED", "PARTIALLY_ARRIVED", "ARCHIVED"):
            raise _legacy._invalid("对应征订批次尚未到货，不可发放")
        clazz = db.query(SchoolClass).filter(
            SchoolClass.id == class_value,
            SchoolClass.tenant_id == _legacy._tid(),
            SchoolClass.is_deleted.is_(False),
        ).first()
        if not clazz:
            raise not_found("班级不存在")
        students = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == _legacy._tid(),
            StudentProfile.id.in_(requested_ids),
            StudentProfile.is_deleted.is_(False),
        ).all()
        found_ids = {int(row.id) for row in students}
        missing = [value for value in requested_ids if value not in found_ids]
        if missing:
            raise _legacy._bad(f"发放名单包含不存在的学生ID：{missing[:10]}")
        wrong_class = [int(row.id) for row in students if int(row.class_id or 0) != class_value]
        if wrong_class:
            raise AppException(
                "DATA_CONFLICT",
                f"发放名单包含不属于所选班级的学生：{wrong_class[:10]}",
                http_status=409,
            )

        items = db.query(AaTextbookOrderItem).filter(
            AaTextbookOrderItem.order_batch_id == order.id,
            AaTextbookOrderItem.tenant_id == _legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).with_for_update().all()
        if not items:
            raise AppException("DATA_CONFLICT", "征订批次没有有效教材明细", http_status=409)

        existing = db.query(AaTextbookDistributionBatch).filter(
            AaTextbookDistributionBatch.tenant_id == _legacy._tid(),
            AaTextbookDistributionBatch.order_batch_id == order.id,
            AaTextbookDistributionBatch.class_id == class_value,
            AaTextbookDistributionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if existing:
            existing_rows = db.query(AaTextbookDistributionRecord.student_id).filter(
                AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
                AaTextbookDistributionRecord.batch_id == existing.id,
                AaTextbookDistributionRecord.is_deleted.is_(False),
            ).distinct().all()
            existing_student_ids = {int(row[0]) for row in existing_rows}
            if existing_student_ids != set(requested_ids):
                raise AppException(
                    "DATA_CONFLICT",
                    "该征订批次和班级已生成发放名单，且现有名单与本次请求不一致",
                    http_status=409,
                )
            _refresh_distribution_batch(db, existing)
            record_count = db.query(AaTextbookDistributionRecord).filter(
                AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
                AaTextbookDistributionRecord.batch_id == existing.id,
                AaTextbookDistributionRecord.is_deleted.is_(False),
            ).count()
            db.commit()
            return {
                "distributionBatchId": str(existing.id),
                "recordCount": record_count,
                "idempotent": True,
            }

        eligible_students = [
            student for student in students
            if str(student.student_status or "NORMAL").upper() in _ELIGIBLE_STUDENT_STATUSES
        ]
        eligible_count = len(eligible_students)
        capacity_errors = []
        for item in items:
            allocated = db.query(
                func.coalesce(func.sum(AaTextbookDistributionRecord.qty), 0)
            ).join(
                AaTextbookDistributionBatch,
                AaTextbookDistributionBatch.id == AaTextbookDistributionRecord.batch_id,
            ).filter(
                AaTextbookDistributionBatch.tenant_id == _legacy._tid(),
                AaTextbookDistributionBatch.order_batch_id == order.id,
                AaTextbookDistributionBatch.is_deleted.is_(False),
                AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
                AaTextbookDistributionRecord.textbook_id == item.textbook_id,
                AaTextbookDistributionRecord.status.in_(_ACTIVE_ALLOCATION_STATUSES),
                AaTextbookDistributionRecord.is_deleted.is_(False),
            ).scalar() or 0
            shortage = _distribution_shortage(item.arrived_qty, allocated, eligible_count)
            if shortage:
                available = max(0, int(item.arrived_qty or 0) - int(allocated or 0))
                capacity_errors.append(
                    f"{item.textbook_name}可分配{available}本，本班需{eligible_count}本，缺{shortage}本"
                )
        if capacity_errors:
            raise AppException(
                "DATA_CONFLICT",
                "到货库存不足，不能生成发放名单：" + "；".join(capacity_errors[:10]),
                http_status=409,
            )

        now = datetime.utcnow()
        batch = AaTextbookDistributionBatch(
            tenant_id=_legacy._tid(),
            order_batch_id=order.id,
            class_id=class_value,
            class_name=clazz.class_name,
            status="DISTRIBUTING" if eligible_count else "COMPLETED",
            started_at=now,
            completed_at=now if not eligible_count else None,
        )
        db.add(batch)
        db.flush()
        record_count = 0
        for student in students:
            enrolled = str(student.student_status or "NORMAL").upper() in _ELIGIBLE_STUDENT_STATUSES
            for item in items:
                db.add(AaTextbookDistributionRecord(
                    tenant_id=_legacy._tid(),
                    batch_id=batch.id,
                    student_id=student.id,
                    textbook_id=item.textbook_id,
                    textbook_name=item.textbook_name,
                    qty=1,
                    status="PENDING" if enrolled else "EXCLUDED",
                    exclude_reason=None if enrolled else "非在籍",
                ))
                record_count += 1
        _legacy._audit(
            db,
            "AA_TEXTBOOK_DIST",
            batch.id,
            "TEXTBOOK_DIST_GENERATE",
            f"classId={class_value};申请学生={len(students)};可发学生={eligible_count};记录={record_count}",
        )
        db.commit()
        return {
            "distributionBatchId": str(batch.id),
            "recordCount": record_count,
            "eligibleStudentCount": eligible_count,
            "idempotent": False,
        }


def _apply_receipt(db, record_id, note="签收"):
    from app.models import AaTextbookFeeLedger, AaTextbookOrderItem

    record, distribution, order = _distribution_chain(db, record_id, lock=True)
    status = str(record.status or "").upper()
    if status == "EXCLUDED":
        raise _legacy._invalid("非在籍学生不可签收")
    if status not in {"PENDING", "RECEIVED"}:
        raise _legacy._invalid(f"当前发放状态 {status or 'UNKNOWN'} 不可签收")
    item = db.query(AaTextbookOrderItem).filter(
        AaTextbookOrderItem.tenant_id == _legacy._tid(),
        AaTextbookOrderItem.order_batch_id == order.id,
        AaTextbookOrderItem.textbook_id == record.textbook_id,
        AaTextbookOrderItem.is_deleted.is_(False),
    ).with_for_update().first()
    if not item:
        raise AppException("DATA_CONFLICT", "发放记录未匹配到征订价格快照", http_status=409)
    price = Decimal(str(item.unit_price_snapshot or 0))
    amount = price * Decimal(int(record.qty or 1))
    fee = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.distribution_record_id == record.id,
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).with_for_update().first()
    if not fee:
        settled = amount == 0
        fee = AaTextbookFeeLedger(
            tenant_id=_legacy._tid(),
            distribution_record_id=record.id,
            student_id=record.student_id,
            textbook_name=record.textbook_name,
            amount=amount,
            paid_amount=Decimal("0"),
            status="PAID" if settled else "UNPAID",
            paid_at=datetime.utcnow() if settled else None,
        )
        db.add(fee)
    elif Decimal(str(fee.amount or 0)) != amount:
        raise AppException(
            "DATA_CONFLICT",
            "已有费用台账金额与征订价格快照不一致，禁止自动覆盖，请先完成财务数据治理",
            http_status=409,
        )
    if status != "RECEIVED":
        record.status = "RECEIVED"
        record.received_at = datetime.utcnow()
        record.received_by = _legacy._op()
        _legacy._audit(
            db,
            "AA_TEXTBOOK_DIST",
            record.id,
            "TEXTBOOK_SIGN_RECEIPT",
            f"{note};价格快照={price};数量={record.qty or 1};应收={amount}",
        )
    _refresh_distribution_batch(db, distribution)
    return {
        "recordId": str(record.id),
        "status": record.status,
        "feeStatus": fee.status,
        "amount": float(amount),
    }


def sign_receipt(user, record_id):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        result = _apply_receipt(db, int(record_id))
        db.commit()
        return result


def sign_receipt_my(user, student_id, record_id):
    from app.models import AaTextbookDistributionRecord

    with _legacy.session() as db:
        preview = db.query(AaTextbookDistributionRecord).filter(
            AaTextbookDistributionRecord.id == int(record_id),
            AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ).first()
        if not preview:
            raise not_found("发放记录不存在")
        if int(preview.student_id) != int(student_id):
            raise _legacy.no_data_scope("只能签收本人教材")
        result = _apply_receipt(db, int(record_id), "学生签收")
        db.commit()
        return result


def return_distribution(user, record_id, reason):
    from app.models import AaTextbookFeeLedger

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("退领原因必填且不少于5字")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        record, distribution, _order = _distribution_chain(db, record_id, lock=True)
        if record.status == "RETURNED":
            return {"recordId": str(record.id), "status": record.status}
        if record.status != "RECEIVED":
            raise _legacy._invalid("仅已签收教材可办理退领")
        fee = db.query(AaTextbookFeeLedger).filter(
            AaTextbookFeeLedger.tenant_id == _legacy._tid(),
            AaTextbookFeeLedger.distribution_record_id == record.id,
            AaTextbookFeeLedger.is_deleted.is_(False),
        ).with_for_update().first()
        if not fee:
            raise AppException(
                "DATA_CONFLICT",
                "已签收教材缺少费用台账，禁止退领；请先完成费用数据治理",
                http_status=409,
            )
        if Decimal(str(fee.paid_amount or 0)) > 0 or fee.status in ("PAID", "PARTIAL"):
            raise AppException(
                "DATA_CONFLICT",
                "该教材已发生实收，当前系统尚无退款流水，禁止直接退领冲销；请先完成正式退款闭环",
                http_status=409,
            )
        if fee.status == "UNPAID":
            fee.status = "WAIVED"
            fee.waive_reason = f"退领：{reason}"[:500]
        elif fee.status != "WAIVED":
            raise _legacy._invalid("费用状态异常，不能办理退领")
        record.status = "RETURNED"
        record.exchange_reason = reason
        _refresh_distribution_batch(db, distribution)
        _legacy._audit(db, "AA_TEXTBOOK_DIST", record.id, "TEXTBOOK_RETURN", reason)
        db.commit()
        return {"recordId": str(record.id), "status": record.status, "feeStatus": fee.status}


def mark_fee(user, fee_id, action, amount=None, waive_reason=""):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        fee, _record, _distribution, _order = _fee_chain(db, fee_id)
        action = str(action or "").upper()
        status = str(fee.status or "UNPAID").upper()
        due = Decimal(str(fee.amount or 0))
        paid = Decimal(str(fee.paid_amount or 0))

        if status == "PAID":
            if action == "PAID":
                return {
                    "feeId": str(fee.id),
                    "status": fee.status,
                    "paidAmount": float(paid),
                    "amount": float(due),
                    "idempotent": True,
                }
            raise _legacy._invalid("费用已结清，不可改为部分收款或减免；退款须走独立冲正流程")
        if status == "WAIVED":
            if action in {"WAIVE", "WAIVED"}:
                return {
                    "feeId": str(fee.id),
                    "status": fee.status,
                    "paidAmount": float(paid),
                    "amount": float(due),
                    "idempotent": True,
                }
            raise _legacy._invalid("费用已减免，不可重新标记收款")

        if action == "PAID":
            fee.paid_amount = due
            fee.status = "PAID"
            fee.paid_at = datetime.utcnow()
        elif action == "PARTIAL":
            if status not in {"UNPAID", "PARTIAL"}:
                raise _legacy._invalid("当前费用状态不可部分收款")
            value = Decimal(str(amount or 0))
            if value <= 0:
                raise _legacy._bad("部分收款金额须大于0")
            new_paid = paid + value
            if new_paid > due:
                raise _legacy._bad(f"累计已收 {new_paid} 超过应收 {due}")
            fee.paid_amount = new_paid
            if new_paid == due:
                fee.status = "PAID"
                fee.paid_at = datetime.utcnow()
            else:
                fee.status = "PARTIAL"
        elif action in {"WAIVE", "WAIVED"}:
            reason = str(waive_reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("减免原因必填且不少于5字")
            if paid > 0 or status == "PARTIAL":
                raise _legacy._invalid("费用已有实收金额，不能直接减免；须先完成退款/冲正")
            fee.status = "WAIVED"
            fee.waive_reason = reason
        else:
            raise _legacy._bad("非法操作")

        _legacy._audit(
            db,
            "AA_TEXTBOOK_FEE",
            fee.id,
            "TEXTBOOK_FEE_MARK",
            f"{status}->{fee.status};本次={amount or ''}",
        )
        db.commit()
        return {
            "feeId": str(fee.id),
            "status": fee.status,
            "paidAmount": float(fee.paid_amount or 0),
            "amount": float(due),
            "idempotent": False,
        }


def textbook_stock(user):
    from app.models import AaTextbookDistributionRecord, AaTextbookOrderItem

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        stock = {}
        for item in db.query(AaTextbookOrderItem).filter(
            AaTextbookOrderItem.tenant_id == _legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).all():
            key = int(item.textbook_id)
            row = stock.setdefault(key, {
                "textbookId": str(key),
                "textbookName": item.textbook_name,
                "arrivedQty": 0,
                "reservedQty": 0,
                "distributedQty": 0,
            })
            row["arrivedQty"] += int(item.arrived_qty or 0)
            if not row["textbookName"] and item.textbook_name:
                row["textbookName"] = item.textbook_name

        records = db.query(AaTextbookDistributionRecord).filter(
            AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
            AaTextbookDistributionRecord.status.in_(_ACTIVE_ALLOCATION_STATUSES),
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ).all()
        for record in records:
            key = int(record.textbook_id)
            row = stock.setdefault(key, {
                "textbookId": str(key),
                "textbookName": record.textbook_name,
                "arrivedQty": 0,
                "reservedQty": 0,
                "distributedQty": 0,
            })
            quantity = int(record.qty or 0)
            if str(record.status or "").upper() == "PENDING":
                row["reservedQty"] += quantity
            else:
                row["distributedQty"] += quantity

        items = []
        for row in stock.values():
            occupied = int(row["reservedQty"]) + int(row["distributedQty"])
            row["stockQty"] = int(row["arrivedQty"]) - occupied
            row["dataConflict"] = row["stockQty"] < 0
            items.append(row)
        return sorted(items, key=lambda row: (row["textbookName"] or "", row["textbookId"]))
