"""教务归档批次与预检必须绑定真实学期的生产安全门。

历史表 ``t_aa_archive_batch.term_id`` 仍允许 NULL，只为兼容既有数据；正式创建语义始终是
“一学期一批次”。预检省略 termId 时仅允许解析真实 current term；没有 current term
必须 fail-closed，禁止把 None 传给十三域 evaluator 后退化成全租户历史扫描。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_archive_service as archive_service


_ORIGINAL_CREATE_BATCH = getattr(
    archive_service,
    "_archive_term_guard_original_create_batch",
    archive_service.create_batch,
)
_ORIGINAL_PRECHECK = getattr(
    archive_service,
    "_archive_term_guard_original_precheck",
    archive_service.precheck,
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


def resolve_precheck_term_id(user, raw_term_id=None) -> int:
    """显式 termId 优先；缺省仅解析 current term，绝不退化成全租户历史扫描。"""
    if raw_term_id is not None and str(raw_term_id).strip():
        return validate_term_id(raw_term_id)

    from app.models import AaTerm

    with archive_service._core.session() as db:
        archive_service._core._ctx(user, db)
        term = db.query(AaTerm).filter(
            AaTerm.tenant_id == _tid(),
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise not_found("未设置当前学期，请指定 termId")
        return int(term.id)


def precheck(user, term_id=None):
    """归档预检始终使用一个真实学期 ID 调用唯一公开 service。"""
    resolved_term_id = resolve_precheck_term_id(user, term_id)
    return _ORIGINAL_PRECHECK(user, resolved_term_id)


precheck._archive_term_precheck_guard = True


def install() -> None:
    """幂等安装到唯一公开 archive service。"""
    if not hasattr(archive_service, "_archive_term_guard_original_create_batch"):
        archive_service._archive_term_guard_original_create_batch = archive_service.create_batch
    if not hasattr(archive_service, "_archive_term_guard_original_precheck"):
        archive_service._archive_term_guard_original_precheck = archive_service.precheck
    archive_service.validate_term_id = validate_term_id
    archive_service.resolve_precheck_term_id = resolve_precheck_term_id
    if not getattr(archive_service.create_batch, "_archive_term_binding_guard", False):
        archive_service.create_batch = create_batch
    if not getattr(archive_service.precheck, "_archive_term_precheck_guard", False):
        archive_service.precheck = precheck
