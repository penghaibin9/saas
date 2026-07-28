"""学生调岗、换单位与退岗的批次化权威写入口。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipChangeRequest
from app.modules.internship.services import internship_change_service as legacy
from app.modules.internship.services.internship_student_context_guard import (
    require_expected_version,
    require_explicit_context,
)
from app.services.db_service import _as_id, _tid, session


def _optional_positive_id(payload: dict, key: str):
    raw = (payload or {}).get(key)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{key} 格式非法") from None
    if value < 1:
        raise AppException("VALIDATION_ERROR", f"{key} 格式非法")
    return value


def list_my(user: dict, *, batch_id, internship_id) -> dict:
    with session() as db:
        record, student, selected_batch_id = require_explicit_context(
            db,
            user,
            {"batchId": batch_id, "internshipId": internship_id},
            for_write=False,
        )
        rows = db.scalars(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.internship_id == record.id,
            InternshipChangeRequest.student_id == student.id,
            InternshipChangeRequest.is_deleted.is_(False),
        ).order_by(InternshipChangeRequest.id.desc())).all()
        return {
            "items": [legacy._row(row, record, student) for row in rows],
            "batchId": str(selected_batch_id),
            "internshipId": str(record.id),
        }


def apply(user: dict, body: dict) -> dict:
    payload = body or {}
    change_type = str(payload.get("changeType") or "").upper()
    if change_type not in legacy.TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "changeType 无效")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")
    if change_type == "CHANGE_POSITION" and not payload.get("targetPositionId"):
        raise AppException("VALIDATION_ERROR", "换岗必须选择目标岗位")
    require_expected_version(
        payload.get("expectedVersion"), 0, entity_name="变更申请上下文")

    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        pending = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.internship_id == record.id,
            InternshipChangeRequest.status == "PENDING",
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update())
        if pending:
            raise AppException(
                "DATA_CONFLICT", "已有待审核的变更申请，请等待处理或撤回")

        row = InternshipChangeRequest(
            tenant_id=_tid(),
            internship_id=record.id,
            student_id=student.id,
            change_type=change_type,
            reason=reason,
            target_enterprise_id=_optional_positive_id(
                payload, "targetEnterpriseId"),
            target_position_id=_optional_positive_id(
                payload, "targetPositionId"),
            target_enterprise_name=(
                str(payload.get("targetEnterpriseName") or "").strip() or None
            ),
            target_position_name=(
                str(payload.get("targetPositionName") or "").strip() or None
            ),
            status="PENDING",
        )
        db.add(row)
        db.flush()
        legacy._trail(
            db,
            row.id,
            "APPLY_VERSIONED",
            {
                "changeType": change_type,
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "expectedVersion": 0,
            },
            operator=legacy._op_name(user),
        )
        db.commit()
        return legacy._row(row, record, student)


def withdraw(user: dict, change_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        row = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == _as_id(change_id),
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("变更申请不存在")
        if row.internship_id != record.id or row.student_id != student.id:
            raise no_permission("只能撤回本人当前批次的变更申请")
        require_expected_version(
            payload.get("expectedVersion"), row.version, entity_name="变更申请")
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        legacy._trail(
            db,
            row.id,
            "WITHDRAW_VERSIONED",
            {
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "newVersion": int(row.version or 0),
            },
            operator=legacy._op_name(user),
        )
        db.commit()
        return {
            "id": str(row.id),
            "status": row.status,
            "statusLabel": legacy.STATUS_LABEL.get(row.status, row.status),
            "version": int(row.version or 0),
        }
