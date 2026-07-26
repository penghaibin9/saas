"""选课服务兼容入口。

保留原选课状态机、容量并发控制、补退选和抽签实现，只接管 CLOSED→LOCKED：
锁定前必须证明课程供给、教学任务、学生主档、人数计数和抽签结果一致；锁定后把正式人数投影到
教学任务 ``expected_students``，但名单成员事实仍以 LOCKED 选课记录为准。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException

from . import academic_affairs_selection_service as _legacy
from .academic_affairs_teaching_roster_service import (
    apply_locked_roster_projection,
    validate_selection_lock,
)


def __getattr__(name):
    return getattr(_legacy, name)


def lock_batch(user, batch_id) -> dict:
    from app.models import AaSelectionRecord

    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(batch_id))
        if batch.status == _legacy._BATCH_LOCKED:
            return _legacy._batch_dto(batch)
        if batch.status != _legacy._BATCH_CLOSED:
            raise _legacy._invalid(f"仅 CLOSED 批次可锁定，当前 {batch.status}")

        validation = validate_selection_lock(db, batch)
        if not validation["valid"]:
            messages = [issue["message"] for issue in validation["issues"][:8]]
            suffix = "…" if len(validation["issues"]) > 8 else ""
            raise AppException(
                "DATA_CONFLICT",
                "选课名单一致性检查未通过：" + "；".join(messages) + suffix,
                details=validation,
                http_status=409,
            )

        claimed = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.status == _legacy._REC_SELECTED,
            AaSelectionRecord.is_deleted.is_(False),
        ).update(
            {AaSelectionRecord.status: _legacy._REC_LOCKED},
            synchronize_session=False,
        )
        if int(claimed or 0) != int(validation["selectedRecordCount"] or 0):
            db.rollback()
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "锁定期间选课名单已发生变化，请刷新后重新检查",
                http_status=409,
            )

        apply_locked_roster_projection(db, validation)
        batch.status = _legacy._BATCH_LOCKED
        batch.locked_at = datetime.utcnow()
        _legacy._audit(
            db,
            batch.id,
            "SELECTION_BATCH_LOCK",
            f"锁定正式名单 records={claimed};tasks={len(validation.get('taskStudentCounts') or {})}",
        )
        db.commit()
        return _legacy._batch_dto(batch)


_legacy.lock_batch = lock_batch
