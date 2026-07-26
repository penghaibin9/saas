"""教材征订价格与来源最终保护层。

征订生成必须在同一事务内完成：
- 只消费所属学期、状态APPROVED的教材选用；
- 每条选用具有正整数预计数量；
- 教材目录记录真实存在且未删除；
- 单价快照不得为NULL，真实0元教材允许；
- 校验全部通过后才推进选用为ORDERED并生成批次，禁止形成无法签收/归档的死批次。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found

from . import academic_affairs_textbook_lock_facade as _base

_legacy = _base._legacy
_term_layer = _base._term_layer
_final_layer = _base._base._base


def __getattr__(name):
    return getattr(_base, name)


def _missing_price_textbook_ids(catalog_by_id, textbook_ids):
    return [
        int(textbook_id) for textbook_id in textbook_ids
        if textbook_id not in catalog_by_id
        or catalog_by_id[textbook_id].unit_price is None
    ]


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
        term = _term_layer._term(db, getattr(body, "termId", None))
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

        invalid_quantity_ids = _final_layer._invalid_order_quantity_ids(selections)
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


# 封死旧service和中间facade的征订旁路。
_legacy.create_order_batch = create_order_batch
_final_layer.create_order_batch = create_order_batch
