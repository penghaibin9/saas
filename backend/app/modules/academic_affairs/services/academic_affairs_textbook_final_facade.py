"""教材域最终输入、发放、计费与异常闭环校验层。

在学期写保护facade之上补生产级约束：
- 审核批次selectionIds去重；
- 征订来源必须有正整数预计数量；
- 同学期已有有效征订时才标记补订；
- 到货累计量不可倒退、不可超过征订量；
- 发放必须绑定真实班级，学生名单必须全部属于该班，重复请求幂等；
- 签收应收按征订时 ``unit_price_snapshot`` 计价，目录后续调价不得改写历史费用；
- 退领必须存在费用台账，已有实收时禁止静默冲销。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

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
    """同学期新增已备案选用形成新批次；数量不完整时整批拒绝。"""
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
            f"{'补订' if supplemental else '首批征订'}；合并 {len(merged)} 种教材；来源选用 {len(rows)} 条",
        )
        db.commit()
        return {
            "orderBatchId": str(batch.id),
            "itemCount": len(merged),
            "selectionCount": len(rows),
            "supplemental": supplemental,
        }


def record_arrival(user, item_id, arrived_qty):
    """登记累计到货量：只能递增且不得超过征订数量。"""
    from app.models import AaTextbookOrderItem

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        item = db.query(AaTextbookOrderItem).filter(
            AaTextbookOrderItem.id == int(item_id),
            AaTextbookOrderItem.tenant_id == _legacy._tid(),
            AaTextbookOrderItem.is_deleted.is_(False),
        ).first()
        if not item:
            raise not_found("征订明细不存在")
        order = _base._original_get_ob(db, item.order_batch_id)
        _base._term(db, order.term_id)
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
            db, "AA_TEXTBOOK_ORDER", order.id, "TEXTBOOK_ARRIVAL",
            f"itemId={item.id};累计到货={value}/{ordered}",
        )
        db.commit()
        return {"itemId": str(item.id), "arrivedQty": value, "batchStatus": order.status}


def generate_distribution(user, order_batch_id, class_id, student_ids):
    """按真实行政班生成发放名单；完全相同的重复请求幂等，不同名单冲突。"""
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookOrderItem,
        StudentClass,
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
        order = _base._original_get_ob(db, int(order_batch_id))
        _base._term(db, order.term_id)
        if order.status not in ("ARRIVED", "PARTIALLY_ARRIVED"):
            raise _legacy._invalid("对应征订批次未到货，不可发放")
        clazz = db.query(StudentClass).filter(
            StudentClass.id == class_value,
            StudentClass.tenant_id == _legacy._tid(),
            StudentClass.is_deleted.is_(False),
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
        ).all()
        if not items:
            raise AppException("DATA_CONFLICT", "征订批次没有有效教材明细", http_status=409)
        if any(int(item.arrived_qty or 0) <= 0 for item in items):
            raise _legacy._invalid("征订批次仍有教材未到货，不能生成完整发放名单")

        existing = db.query(AaTextbookDistributionBatch).filter(
            AaTextbookDistributionBatch.tenant_id == _legacy._tid(),
            AaTextbookDistributionBatch.order_batch_id == order.id,
            AaTextbookDistributionBatch.class_id == class_value,
            AaTextbookDistributionBatch.is_deleted.is_(False),
        ).first()
        if existing:
            existing_student_ids = {
                int(value) for (value,) in db.query(AaTextbookDistributionRecord.student_id).filter(
                    AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
                    AaTextbookDistributionRecord.batch_id == existing.id,
                    AaTextbookDistributionRecord.is_deleted.is_(False),
                ).distinct().all()
            }
            if existing_student_ids != set(requested_ids):
                raise AppException(
                    "DATA_CONFLICT",
                    "该征订批次和班级已生成发放名单，且现有名单与本次请求不一致",
                    http_status=409,
                )
            record_count = db.query(AaTextbookDistributionRecord).filter(
                AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
                AaTextbookDistributionRecord.batch_id == existing.id,
                AaTextbookDistributionRecord.is_deleted.is_(False),
            ).count()
            return {
                "distributionBatchId": str(existing.id),
                "recordCount": record_count,
                "idempotent": True,
            }

        batch = AaTextbookDistributionBatch(
            tenant_id=_legacy._tid(),
            order_batch_id=order.id,
            class_id=class_value,
            class_name=getattr(clazz, "class_name", None),
            status="DISTRIBUTING",
            started_at=datetime.utcnow(),
        )
        db.add(batch)
        db.flush()
        record_count = 0
        for student in students:
            enrolled = str(student.student_status or "NORMAL").upper() in {
                "NORMAL", "REGISTERED", "ON_CAMPUS",
            }
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
            db, "AA_TEXTBOOK_DIST", batch.id, "TEXTBOOK_DIST_GENERATE",
            f"classId={class_value};学生={len(students)};记录={record_count}",
        )
        db.commit()
        return {
            "distributionBatchId": str(batch.id),
            "recordCount": record_count,
            "idempotent": False,
        }


def _apply_receipt(db, record, note="签收"):
    """签收幂等生成应收；金额固定使用征订明细价格快照。"""
    from app.models import AaTextbookFeeLedger, AaTextbookOrderItem

    record, distribution, order = _base._distribution_chain(db, record.id)
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
    ).first()
    if not item:
        raise AppException("DATA_CONFLICT", "发放记录未匹配到征订价格快照", http_status=409)
    price = Decimal(str(item.unit_price_snapshot or 0))
    amount = price * Decimal(int(record.qty or 1))
    fee = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.distribution_record_id == record.id,
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).first()
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
            db, "AA_TEXTBOOK_DIST", record.id, "TEXTBOOK_SIGN_RECEIPT",
            f"{note};价格快照={price};数量={record.qty or 1};应收={amount}",
        )
    _base._refresh_distribution_batch(db, distribution)
    return {
        "recordId": str(record.id),
        "status": record.status,
        "feeStatus": fee.status,
        "amount": float(amount),
    }


def return_distribution(user, record_id, reason):
    """未实收教材可退领；缺费用台账或已有实收均拒绝，避免无退款流水静默冲销。"""
    from app.models import AaTextbookFeeLedger

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("退领原因必填且不少于5字")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        record, distribution, _order = _base._distribution_chain(db, record_id)
        if record.status == "RETURNED":
            return {"recordId": str(record.id), "status": record.status}
        if record.status != "RECEIVED":
            raise _legacy._invalid("仅已签收教材可办理退领")
        fee = db.query(AaTextbookFeeLedger).filter(
            AaTextbookFeeLedger.tenant_id == _legacy._tid(),
            AaTextbookFeeLedger.distribution_record_id == record.id,
            AaTextbookFeeLedger.is_deleted.is_(False),
        ).first()
        if not fee:
            raise AppException(
                "DATA_CONFLICT",
                "已签收教材缺少费用台账，禁止退领；请先完成费用数据治理",
                http_status=409,
            )
        if float(fee.paid_amount or 0) > 0 or fee.status in ("PAID", "PARTIAL"):
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
        _base._refresh_distribution_batch(db, distribution)
        _legacy._audit(db, "AA_TEXTBOOK_DIST", record.id, "TEXTBOOK_RETURN", reason)
        db.commit()
        return {"recordId": str(record.id), "status": record.status, "feeStatus": fee.status}


# 原service函数从其自身globals读取_apply_receipt，必须替换真实执行对象，而不是只覆盖facade属性。
_legacy._apply_receipt = _apply_receipt
_legacy.create_review_batch = create_review_batch
_legacy.create_order_batch = create_order_batch
_legacy.record_arrival = record_arrival
_legacy.generate_distribution = generate_distribution
_legacy.return_distribution = return_distribution
