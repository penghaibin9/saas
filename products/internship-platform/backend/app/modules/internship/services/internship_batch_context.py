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


def list_batch_options(page, page_size, user, *, keyword=None, selected_id=None):
    """Only navigation metadata; selecting a batch grants no business/detail access."""
    from sqlalchemy import func, or_, select
    from app.core.permissions import ROLE_PERMISSIONS, get_effective_access_context, has_permission
    from app.core.exceptions import no_permission
    from app.models import InternshipRecord
    from app.services.db_service import session, _iso
    from app.services.mobile_teacher_service import _ADVISOR_ROLES, _role
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    permissions = get_effective_access_context(user)['permissions']
    if (_role(user) not in (set(ROLE_PERMISSIONS) - {'STUDENT'}) | _ADVISOR_ROLES
            or not any(code == '*' or code.startswith('internship.') for code in permissions)):
        raise no_permission('当前身份没有实习业务办理权限')
    query = select(InternshipBatch).where(InternshipBatch.tenant_id == _tid(),
        InternshipBatch.is_deleted.is_(False), InternshipBatch.status != 'VOIDED')
    if not has_permission(user, 'internship.batch.view'):
        records = apply_internship_record_scope(select(InternshipRecord.batch_id).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False)), user)
        query = query.where(InternshipBatch.id.in_(records))
    if keyword and keyword.strip():
        query = query.where(or_(InternshipBatch.batch_name.contains(keyword.strip(), autoescape=True),
                                InternshipBatch.batch_no.contains(keyword.strip(), autoescape=True)))

    def project(row):
        return {'id': str(row.id), 'batchName': row.batch_name or '', 'batchNo': row.batch_no or '',
                'status': row.status, 'startDate': (_iso(row.start_date) or '')[:10],
                'endDate': (_iso(row.end_date) or '')[:10]}

    with session() as db:
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        fields = (InternshipBatch.id, InternshipBatch.batch_name, InternshipBatch.batch_no,
                  InternshipBatch.status, InternshipBatch.start_date, InternshipBatch.end_date)
        limited = query.with_only_columns(*fields)
        rows = db.execute(limited.order_by(InternshipBatch.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
        selected = db.execute(limited.where(InternshipBatch.id == int(selected_id))).first() if selected_id else None
        return [project(row) for row in rows], total, project(selected) if selected else None
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


def batch_record_ids(db, batch_id, *, for_write: bool = False) -> tuple[InternshipBatch, list[int]]:
    """解析批次并返回该批次下全部未删除实习记录 id（列表/统计/导出共用）。"""
    from sqlalchemy import select
    from app.models import InternshipRecord

    batch = resolve_batch(db, batch_id, for_write=for_write)
    ids = list(db.scalars(select(InternshipRecord.id).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False),
        InternshipRecord.batch_id == batch.id,
    )).all())
    return batch, ids


def assert_record_batch(record, expected_batch_id) -> int | None:
    """在写事务内确认被锁定记录仍属于调用方当前选择的批次。"""
    if expected_batch_id is None:
        return None
    bid = parse_required_batch_id(expected_batch_id)
    if not record or int(getattr(record, "batch_id", 0) or 0) != bid:
        raise AppException(
            "DATA_CONFLICT",
            "该记录不属于当前实习批次，请刷新批次上下文",
        )
    return bid
