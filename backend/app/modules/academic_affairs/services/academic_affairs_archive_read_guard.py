"""教务归档批次列表的大校规模只读安全层。

只替换公开 archive service 的列表读取：保持原 DTO/筛选合同，把全量 ``.all()`` 后 Python
切片改为数据库 COUNT + OFFSET/LIMIT，并统一 page/pageSize 边界。归档状态机、Manifest、
确认/纠错写链均继续由既有 canonical service 持有。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException

from . import academic_affairs_archive_service as archive_service
from .academic_affairs_production_audit_guard import _bounded_page_size


_ORIGINAL_LIST_BATCHES = getattr(
    archive_service,
    "_archive_read_guard_original_list_batches",
    archive_service.list_batches,
)


def list_batches(user, status=None, page=1, page_size=20):
    from app.models import AaArchiveBatch

    try:
        page_no = int(page or 1)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    if page_no < 1:
        raise AppException("VALIDATION_ERROR", "page 必须大于等于 1")
    size = _bounded_page_size(page_size, default=20)

    with archive_service._core.session() as db:
        archive_service._core._ctx(user, db)
        conditions = [
            AaArchiveBatch.tenant_id == archive_service._core._tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ]
        if status:
            conditions.append(AaArchiveBatch.status == status)

        total = int(
            db.scalar(select(func.count(AaArchiveBatch.id)).where(*conditions)) or 0
        )
        rows = db.scalars(
            select(AaArchiveBatch)
            .where(*conditions)
            .order_by(AaArchiveBatch.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [archive_service._core._batch_dto(batch) for batch in rows], total


list_batches._archive_sql_paging_guard = True


def install() -> None:
    if not hasattr(archive_service, "_archive_read_guard_original_list_batches"):
        archive_service._archive_read_guard_original_list_batches = archive_service.list_batches
    if not getattr(archive_service.list_batches, "_archive_sql_paging_guard", False):
        archive_service.list_batches = list_batches
