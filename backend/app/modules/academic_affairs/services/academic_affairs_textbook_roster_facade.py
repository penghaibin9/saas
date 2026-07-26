"""教材发放名单与费用终态最终安全层。

当前组织模型的真实行政班类为 ``SchoolClass``。本层收口：
- 发放必须选择真实班级，学生必须全部属于该班；
- 学生ID去重，重复请求名单一致时幂等、不一致时409；
- 费用 ``PAID/WAIVED`` 终态不可逆；部分收款只允许 ``UNPAID/PARTIAL``；
- 其余征订、到货、价格快照、签收和退领逻辑复用下层facade。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.core.exceptions import AppException, not_found

from . import academic_affairs_textbook_final_facade as _base

_legacy = _base._legacy
_term_layer = _base._base


def __getattr__(name):
    return getattr(_base, name)


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
    requested_ids = _base._unique_positive_ids(student_ids)
    if not requested_ids:
        raise _legacy._bad("发放名单至少包含一名学生")

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        order = _term_layer._original_get_ob(db, int(order_batch_id))
        _term_layer._term(db, order.term_id)
        if order.status not in ("ARRIVED", "PARTIALLY_ARRIVED"):
            raise _legacy._invalid("对应征订批次未到货，不可发放")
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
            class_name=clazz.class_name,
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


def mark_fee(user, fee_id, action, amount=None, waive_reason=""):
    """教材费用终态不可逆；不提供无退款流水的反向冲销。"""
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        fee, _record, _distribution, _order = _term_layer._fee_chain(db, fee_id)
        action = str(action or "").upper()
        status = str(fee.status or "UNPAID").upper()
        due = Decimal(str(fee.amount or 0))
        paid = Decimal(str(fee.paid_amount or 0))

        if status == "PAID":
            if action == "PAID":
                return {
                    "feeId": str(fee.id), "status": fee.status,
                    "paidAmount": float(paid), "amount": float(due), "idempotent": True,
                }
            raise _legacy._invalid("费用已结清，不可改为部分收款或减免；退款须走独立冲正流程")
        if status == "WAIVED":
            if action in {"WAIVE", "WAIVED"}:
                return {
                    "feeId": str(fee.id), "status": fee.status,
                    "paidAmount": float(paid), "amount": float(due), "idempotent": True,
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
            reason = (waive_reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("减免原因必填且不少于5字")
            if paid > 0 or status == "PARTIAL":
                raise _legacy._invalid("费用已有实收金额，不能直接减免；须先完成退款/冲正")
            fee.status = "WAIVED"
            fee.waive_reason = reason
        else:
            raise _legacy._bad("非法操作")

        _legacy._audit(
            db, "AA_TEXTBOOK_FEE", fee.id, "TEXTBOOK_FEE_MARK",
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


_legacy.generate_distribution = generate_distribution
_legacy.mark_fee = mark_fee
