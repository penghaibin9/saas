"""教务归档批次必须绑定学期的生产安全门。

历史表 ``t_aa_archive_batch.term_id`` 仍允许 NULL，只为兼容既有数据；正式创建语义始终是
“一学期一批次”。本 guard 在 public service 边界 fail-closed，防止 HTTP 之外的脚本或
内部调用创建“可归档但不冻结任何学期”的孤儿批次。
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_archive_service as archive_service


_ORIGINAL_CREATE_BATCH = getattr(
    archive_service,
    "_archive_term_guard_original_create_batch",
    archive_service.create_batch,
)


def validate_term_id(raw_term_id) -> int:
    """返回合法正整数学期 ID；缺失/非法值一律拒绝。"""
    if raw_term_id is None or not str(raw_term_id).strip():
        raise AppException("VALIDATION_ERROR", "教务归档批次必须绑定学期")
    try:
        term_id = int(str(raw_term_id).strip())
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "termId 必须为有效学期 ID") from None
    if term_id <= 0:
        raise AppException("VALIDATION_ERROR", "termId 必须为有效学期 ID")
    return term_id


def create_batch(user, body):
    """内部/脚本调用同样禁止绕过学期绑定。"""
    validate_term_id(getattr(body, "termId", None))
    return _ORIGINAL_CREATE_BATCH(user, body)


create_batch._archive_term_binding_guard = True


def install() -> None:
    """幂等安装到唯一公开 archive service。"""
    if not hasattr(archive_service, "_archive_term_guard_original_create_batch"):
        archive_service._archive_term_guard_original_create_batch = archive_service.create_batch
    archive_service.validate_term_id = validate_term_id
    if not getattr(archive_service.create_batch, "_archive_term_binding_guard", False):
        archive_service.create_batch = create_batch
