"""岗位实习批次上下文校验（共享）。

禁止：batchId 为空时静默回退到全历史；非法参数不得抛成 500。
写操作额外禁止 VOIDED / ARCHIVED / CLOSED 批次新增学生。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found
from app.models import InternshipBatch
from app.services.db_service import _tid

BATCH_STATUS_LABEL = {
    "DRAFT": "草稿", "RUNNING": "进行中", "CLOSED": "已结束",
    "ARCHIVED": "已归档", "VOIDED": "已作废",
}
# 禁止新增学生的批次状态（已结束/归档/作废）
WRITE_FORBIDDEN_STATUSES = frozenset({"VOIDED", "ARCHIVED", "CLOSED"})


def parse_required_batch_id(batch_id) -> int:
    if batch_id is None or str(batch_id).strip() == "":
        raise AppException("VALIDATION_ERROR", "必须指定实习批次 batchId")
    try:
        return int(str(batch_id).strip())
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "batchId 格式非法") from None


def resolve_batch(db, batch_id, *, for_write: bool = False) -> InternshipBatch:
    """校验批次存在、属于当前租户、未软删；写操作再校验状态。"""
    bid = parse_required_batch_id(batch_id)
    b = db.get(InternshipBatch, bid)
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("实习批次不存在或不在当前数据范围内")
    if for_write and b.status in WRITE_FORBIDDEN_STATUSES:
        label = BATCH_STATUS_LABEL.get(b.status, b.status)
        raise AppException("DATA_CONFLICT", f"批次状态为「{label}」，禁止新增实习学生")
    return b


def batch_public_fields(b: InternshipBatch) -> dict:
    from app.services.db_service import _iso
    return {
        "batchId": str(b.id),
        "batchName": b.batch_name or "",
        "batchNo": b.batch_no or "",
        "batchStatus": b.status or "",
        "batchStatusLabel": BATCH_STATUS_LABEL.get(b.status, b.status or ""),
        "startDate": (_iso(b.start_date) or "")[:10],
        "endDate": (_iso(b.end_date) or "")[:10],
        "batchRange": (
            f"{(_iso(b.start_date) or '')[:10]} ~ {(_iso(b.end_date) or '')[:10]}"
            if b.start_date and b.end_date else ""
        ),
    }
