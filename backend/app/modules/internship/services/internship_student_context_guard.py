"""学生岗位实习 Context API 的显式上下文校验。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import InternshipRecord
from app.modules.internship.services.internship_batch_context import parse_required_batch_id
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.services.db_service import _as_id, _tid


def require_context_fields(payload: dict) -> None:
    body = payload or {}
    if body.get("batchId") is None or str(body.get("batchId")).strip() == "":
        raise AppException("VALIDATION_ERROR", "缺少当前实习批次 batchId")
    if body.get("internshipId") is None or str(body.get("internshipId")).strip() == "":
        raise AppException("VALIDATION_ERROR", "缺少当前实习记录 internshipId")


def require_explicit_context(db, user: dict, payload: dict, *, for_write: bool):
    """解析并核对请求声明的批次和实习记录，写操作额外锁定实习记录。"""
    body = payload or {}
    require_context_fields(body)

    batch_id = parse_required_batch_id(body.get("batchId"))
    try:
        internship_id = _as_id(body.get("internshipId"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "internshipId 格式非法") from None

    ctx = resolve_student_internship_context(
        db,
        student_no=(user or {}).get("studentNo"),
        batch_id=batch_id,
        for_write=for_write,
    )
    if not ctx.record or int(ctx.record.id) != int(internship_id):
        raise AppException(
            "DATA_CONFLICT",
            "该记录不属于当前实习批次，请刷新批次上下文",
        )

    record = ctx.record
    if for_write:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == internship_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
        ).with_for_update())
        if (
            not record
            or int(record.student_id) != int(ctx.student.id)
            or int(record.batch_id or 0) != int(batch_id)
        ):
            raise AppException(
                "DATA_CONFLICT",
                "该记录不属于当前实习批次，请刷新批次上下文",
            )
    return record, ctx.student, batch_id


def require_expected_version(raw, current: int, *, entity_name: str) -> int:
    try:
        expected = int(raw)
    except (TypeError, ValueError):
        raise AppException(
            "DATA_CONFLICT",
            f"缺少有效{entity_name}版本，请刷新后重试",
        ) from None
    if expected != int(current or 0):
        raise AppException(
            "DATA_CONFLICT",
            f"{entity_name}已被其他操作更新，请刷新后重试",
        )
    return expected
