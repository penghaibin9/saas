"""退宿写操作的显式 version 合同。

API 已把当前床位 version 作为第三个参数传入；旧可靠性包装层只接收两个参数，
会在进入业务校验前抛 TypeError。本守卫恢复与正式 API 一致的函数签名，
并在同一事务中完成范围、状态与乐观锁校验。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.optimistic_lock import atomic_claim_version
from app.services.db_service import _tid, session


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.models import CsDormRecord, DormBed
    from app.services import affairs_dorm_service as dorm

    def checkout(bed_id, user, expected_version=None):
        with session() as db:
            bed = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(),
                DormBed.id == int(bed_id),
                DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if not bed:
                raise not_found("床位不存在")
            dorm._require_dorm_scope(db, bed.building_id, user)
            if bed.status != "OCCUPIED" or not bed.student_id:
                raise AppException("DATA_CONFLICT", "该床位无人入住")
            atomic_claim_version(db, bed, expected_version)

            student_id = int(bed.student_id)
            if bed.cs_dorm_record_id:
                record = db.get(CsDormRecord, int(bed.cs_dorm_record_id))
                if record and record.tenant_id == _tid():
                    record.status = "OUT"
                    record.record_status = "INACTIVE"
                    record.version = int(record.version or 0) + 1

            bed.student_id = None
            bed.status = "VACANT"
            bed.occupied_at = None
            bed.cs_dorm_record_id = None
            bed.version = int(bed.version or 0) + 1
            dorm._audit(db, "DORM_BED", bed.id, "CHECKOUT", f"student={student_id}")
            db.commit()
            return {"bedId": str(bed.id), "status": "VACANT", "version": int(bed.version or 0)}

    dorm.checkout = checkout
    _INSTALLED = True
