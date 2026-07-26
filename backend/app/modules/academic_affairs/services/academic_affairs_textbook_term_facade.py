"""教材域最终学期写保护与异常闭环层。

当前真实模型：
- 教材目录/库存是跨学期主数据，不随学期封存；
- 教材选用通过教学任务批次回链 ``term_id``；
- 审核批次、征订批次直接保存 ``term_id``；
- 发放与费用通过 ``费用→发放记录→发放批次→征订批次→term_id`` 回链。

本层只保护学期事实写动作，并修复征订批次跨学期汇总全部 APPROVED 选用的问题。
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_textbook_service as _legacy

_SELECTION_WRITE = ContextVar("aa_textbook_selection_write", default=False)
_REVIEW_WRITE = ContextVar("aa_textbook_review_write", default=False)
_ORDER_WRITE = ContextVar("aa_textbook_order_write", default=False)

_original_get_sel = _legacy._get_sel
_original_get_rb = _legacy._get_rb
_original_get_ob = _legacy._get_ob
_original_apply_receipt = _legacy._apply_receipt


def __getattr__(name):
    return getattr(_legacy, name)


def _term(db, term_id, *, required=True):
    from app.models import AaTerm
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    if not term_id:
        if required:
            raise AppException("VALIDATION_ERROR", "教材学期型业务必须绑定正式学期termId")
        return None
    try:
        value = int(term_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "termId格式不正确")
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


def _get_sel(db, selection_id):
    row = _original_get_sel(db, int(selection_id))
    if _SELECTION_WRITE.get():
        _selection_term(db, row)
    return row


def _get_rb(db, batch_id):
    row = _original_get_rb(db, int(batch_id))
    if _REVIEW_WRITE.get():
        _term(db, row.term_id)
    return row


def _get_ob(db, batch_id):
    row = _original_get_ob(db, int(batch_id))
    if _ORDER_WRITE.get():
        _term(db, row.term_id)
    return row


def _distribution_chain(db, record_id):
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
    )

    record = db.query(AaTextbookDistributionRecord).filter(
        AaTextbookDistributionRecord.id == int(record_id),
        AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
        AaTextbookDistributionRecord.is_deleted.is_(False),
    ).first()
    if not record:
        raise not_found("发放记录不存在")
    distribution = db.query(AaTextbookDistributionBatch).filter(
        AaTextbookDistributionBatch.id == record.batch_id,
        AaTextbookDistributionBatch.tenant_id == _legacy._tid(),
        AaTextbookDistributionBatch.is_deleted.is_(False),
    ).first()
    if not distribution:
        raise AppException("DATA_CONFLICT", "发放记录未关联有效发放批次", http_status=409)
    order = _original_get_ob(db, distribution.order_batch_id)
    _term(db, order.term_id)
    return record, distribution, order


def _fee_chain(db, fee_id):
    from app.models import AaTextbookFeeLedger

    fee = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.id == int(fee_id),
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).first()
    if not fee:
        raise not_found("费用记录不存在")
    record, distribution, order = _distribution_chain(db, fee.distribution_record_id)
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


def _with_flag(flag, fn):
    def wrapped(*args, **kwargs):
        token = flag.set(True)
        try:
            return fn(*args, **kwargs)
        finally:
            flag.reset(token)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    wrapped.__module__ = __name__
    return wrapped


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


def create_review_batch(user, body):
    from app.models import AaTextbookReviewBatch, AaTextbookReviewBatchItem, AaTextbookSelection

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        term = _term(db, getattr(body, "termId", None))
        selection_ids = [int(value) for value in (getattr(body, "selectionIds", None) or []) if str(value).isdigit()]
        if not selection_ids:
            raise _legacy._bad("审核批次至少选择一条已提交教材选用")
        selections = db.query(AaTextbookSelection).filter(
            AaTextbookSelection.tenant_id == _legacy._tid(),
            AaTextbookSelection.id.in_(selection_ids),
            AaTextbookSelection.is_deleted.is_(False),
        ).all()
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
                tenant_id=_legacy._tid(), batch_id=batch.id, selection_id=row.id,
            ))
            row.status = "REVIEWING"
        _legacy._audit(db, "AA_TEXTBOOK_REVIEW", batch.id, "TEXTBOOK_REVIEW_CREATE", f"纳入 {len(accepted)} 条选用")
        db.commit()
        return _legacy._rb_dto(batch)


def create_order_batch(user, body):
    """仅汇总指定学期且尚未征订的 APPROVED 选用；再次调用即为真实补订批次。"""
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
        rows = db.query(AaTextbookSelection).join(
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
        ).all()
        if not rows:
            raise _legacy._bad("本学期没有尚未征订的已备案教材选用")
        batch = AaTextbookOrderBatch(
            tenant_id=_legacy._tid(),
            batch_name=(getattr(body, "batchName", None) or "教材征订批次").strip(),
            term_id=term.id,
            status="DRAFT",
        )
        db.add(batch)
        db.flush()
        merged = {}
        for selection in rows:
            merged.setdefault(selection.textbook_id, {"name": selection.textbook_name, "qty": 0})
            merged[selection.textbook_id]["qty"] += int(selection.expected_qty or 0)
            selection.status = "ORDERED"
            _legacy._audit(
                db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_SOURCE", f"selectionId={selection.id}",
            )
        for textbook_id, info in merged.items():
            textbook = db.query(AaTextbook).filter(
                AaTextbook.id == textbook_id,
                AaTextbook.tenant_id == _legacy._tid(),
                AaTextbook.is_deleted.is_(False),
            ).first()
            db.add(AaTextbookOrderItem(
                tenant_id=_legacy._tid(),
                order_batch_id=batch.id,
                textbook_id=textbook_id,
                textbook_name=info["name"],
                order_qty=info["qty"],
                arrived_qty=0,
                unit_price_snapshot=textbook.unit_price if textbook else None,
            ))
        _legacy._audit(db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_GENERATE", f"合并 {len(merged)} 种教材；来源选用 {len(rows)} 条")
        db.commit()
        return {"orderBatchId": str(batch.id), "itemCount": len(merged), "selectionCount": len(rows)}


def cancel_order_batch(user, batch_id, reason):
    """无到货的征订批次可取消；按创建时审计快照精确恢复来源选用，历史无快照批次拒绝自动取消。"""
    from app.models import AffairsAuditTrail, AaTextbookOrderItem, AaTextbookSelection

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("取消原因必填且不少于5字")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _original_get_ob(db, int(batch_id))
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
            text = str(source.detail or "")
            if text.startswith("selectionId=") and text.split("=", 1)[1].isdigit():
                selection_ids.append(int(text.split("=", 1)[1]))
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
        ).all()
        for selection in selections:
            if selection.status == "ORDERED":
                selection.status = "APPROVED"
        batch.status = "CANCELLED"
        _legacy._audit(db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_CANCEL", reason)
        db.commit()
        return _legacy._ob_dto(batch)


def _apply_receipt(db, record, note="签收"):
    _record, distribution, _order = _distribution_chain(db, record.id)
    result = _original_apply_receipt(db, record, note)
    _refresh_distribution_batch(db, distribution)
    return result


def return_distribution(user, record_id, reason):
    """未发生实收的已签收教材可退领；已有收款必须先走正式退款能力，禁止静默冲销。"""
    from app.models import AaTextbookFeeLedger

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("退领原因必填且不少于5字")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        record, distribution, _order = _distribution_chain(db, record_id)
        if record.status == "RETURNED":
            return {"recordId": str(record.id), "status": record.status}
        if record.status != "RECEIVED":
            raise _legacy._invalid("仅已签收教材可办理退领")
        fee = db.query(AaTextbookFeeLedger).filter(
            AaTextbookFeeLedger.tenant_id == _legacy._tid(),
            AaTextbookFeeLedger.distribution_record_id == record.id,
            AaTextbookFeeLedger.is_deleted.is_(False),
        ).first()
        if fee and (float(fee.paid_amount or 0) > 0 or fee.status in ("PAID", "PARTIAL")):
            raise AppException(
                "DATA_CONFLICT",
                "该教材已发生实收，当前系统尚无退款流水，禁止直接退领冲销；请先完成正式退款闭环",
                http_status=409,
            )
        if fee and fee.status == "UNPAID":
            fee.status = "WAIVED"
            fee.waive_reason = f"退领：{reason}"[:500]
        record.status = "RETURNED"
        record.exchange_reason = reason
        _refresh_distribution_batch(db, distribution)
        _legacy._audit(db, "AA_TEXTBOOK_DIST", record.id, "TEXTBOOK_RETURN", reason)
        db.commit()
        return {"recordId": str(record.id), "status": record.status, "feeStatus": fee.status if fee else None}


def mark_fee(user, fee_id, action, amount=None, waive_reason=""):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        fee, _record, _distribution, _order = _fee_chain(db, fee_id)
        action = str(action or "").upper()
        due = float(fee.amount or 0)
        if action == "PAID":
            fee.paid_amount = due
            fee.status = "PAID"
            fee.paid_at = datetime.utcnow()
        elif action == "PARTIAL":
            value = float(amount or 0)
            if value <= 0:
                raise _legacy._bad("部分收款金额须大于0")
            new_paid = float(fee.paid_amount or 0) + value
            if new_paid > due:
                raise _legacy._bad(f"累计已收 {new_paid} 超过应收 {due}")
            fee.paid_amount = new_paid
            if new_paid >= due:
                fee.status = "PAID"
                fee.paid_at = datetime.utcnow()
            else:
                fee.status = "PARTIAL"
        elif action in ("WAIVE", "WAIVED"):
            waive_reason = (waive_reason or "").strip()
            if len(waive_reason) < 5:
                raise _legacy._bad("减免原因必填且不少于5字")
            if float(fee.paid_amount or 0) > 0:
                raise _legacy._invalid("已有实收金额的费用不能直接减免，须先完成退款/冲正")
            fee.status = "WAIVED"
            fee.waive_reason = waive_reason
        else:
            raise _legacy._bad("非法操作")
        _legacy._audit(db, "AA_TEXTBOOK_FEE", fee.id, "TEXTBOOK_FEE_MARK", f"{action} {amount or ''}")
        db.commit()
        return {"feeId": str(fee.id), "status": fee.status, "paidAmount": _legacy._fnum(fee.paid_amount), "amount": due}


# 在原事务内插入学期门禁，避免只在路由前检查形成TOCTOU窗口。
_legacy._get_sel = _get_sel
_legacy._get_rb = _get_rb
_legacy._get_ob = _get_ob
_legacy._apply_receipt = _apply_receipt

for _name in ("submit_selection", "withdraw_selection"):
    _wrapped = _with_flag(_SELECTION_WRITE, getattr(_legacy, _name))
    globals()[_name] = _wrapped
    setattr(_legacy, _name, _wrapped)

review_batch_advance = _with_flag(_REVIEW_WRITE, _legacy.review_batch_advance)
_legacy.review_batch_advance = review_batch_advance

for _name in ("submit_order", "record_arrival", "archive_order_batch", "generate_distribution"):
    _wrapped = _with_flag(_ORDER_WRITE, getattr(_legacy, _name))
    globals()[_name] = _wrapped
    setattr(_legacy, _name, _wrapped)

_legacy.create_selection = create_selection
_legacy.create_review_batch = create_review_batch
_legacy.create_order_batch = create_order_batch
_legacy.cancel_order_batch = cancel_order_batch
_legacy.return_distribution = return_distribution
_legacy.mark_fee = mark_fee
