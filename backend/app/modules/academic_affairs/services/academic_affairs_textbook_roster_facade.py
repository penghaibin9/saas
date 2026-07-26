"""教材发放名单最终安全层。

当前组织模型的真实行政班类为 ``SchoolClass``。本层仅替换发放名单生成：
- 必须选择真实班级；
- 学生必须全部属于该班；
- 学生ID去重且不存在的ID直接拒绝；
- 同征订批次+班级重复请求，名单完全相同时幂等，不同时409；
- 其余征订、到货、价格快照、签收、退领和费用逻辑复用下层facade。
"""
from __future__ import annotations

from datetime import datetime

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
            existing_student_ids = {
                int(row[0] if isinstance(row, tuple) else row.student_id)
                for row in existing_rows
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


_legacy.generate_distribution = generate_distribution
