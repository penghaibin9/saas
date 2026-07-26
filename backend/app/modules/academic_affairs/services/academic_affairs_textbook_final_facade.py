"""教材域最终输入校验层。

在学期写保护facade之上补两条生产级约束：
- 审核批次selectionIds去重，避免同一选用重复插入唯一关联；
- 征订前所有来源选用必须有正整数预计数量，禁止生成0本征订后错误推进状态。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found

from . import academic_affairs_textbook_term_facade as _base

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


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


def create_review_batch(user, body):
    from app.models import AaTextbookReviewBatch, AaTextbookReviewBatchItem, AaTextbookSelection

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        term = _base._term(db, getattr(body, "termId", None))
        selection_ids = _unique_positive_ids(getattr(body, "selectionIds", None))
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
            task_batch = _base._selection_term(db, row)
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
        _legacy._audit(
            db, "AA_TEXTBOOK_REVIEW", batch.id, "TEXTBOOK_REVIEW_CREATE",
            f"纳入 {len(accepted)} 条选用",
        )
        db.commit()
        return _legacy._rb_dto(batch)


def create_order_batch(user, body):
    """同学期新增已备案选用形成新批次，即补订；数量不完整时整批拒绝。"""
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
        term = _base._term(db, getattr(body, "termId", None))
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
        invalid_ids = _invalid_order_quantity_ids(rows)
        if invalid_ids:
            preview = "、".join(str(value) for value in invalid_ids[:10])
            suffix = "等" if len(invalid_ids) > 10 else ""
            raise AppException(
                "DATA_CONFLICT",
                f"教材选用 {preview}{suffix} 未填写正整数预计数量，不能生成征订批次",
                http_status=409,
            )

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
            textbook_id = int(selection.textbook_id)
            merged.setdefault(textbook_id, {"name": selection.textbook_name, "qty": 0})
            merged[textbook_id]["qty"] += int(selection.expected_qty)
            selection.status = "ORDERED"
            _legacy._audit(
                db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_SOURCE",
                f"selectionId={selection.id}",
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
        _legacy._audit(
            db, "AA_TEXTBOOK_ORDER", batch.id, "TEXTBOOK_ORDER_GENERATE",
            f"合并 {len(merged)} 种教材；来源选用 {len(rows)} 条",
        )
        db.commit()
        return {
            "orderBatchId": str(batch.id),
            "itemCount": len(merged),
            "selectionCount": len(rows),
            "supplemental": True,
        }


_legacy.create_review_batch = create_review_batch
_legacy.create_order_batch = create_order_batch
