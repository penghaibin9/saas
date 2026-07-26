"""教务归档最终学期解析与写保护层。

历史业务表仍有只保存 ``term_code`` 的模型。本层提供唯一解析入口：必须在本租户正式 AaTerm 中精确
匹配 ``{year_code}-{term_no}``，再复用既有 ``guard_term_writable``。业务服务禁止自行切字符串。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services.db_service import _tid

from . import academic_affairs_archive_selection_facade as _base


def __getattr__(name):
    return getattr(_base, name)


def resolve_term_by_code(db, term_code, *, required: bool = True):
    from app.models import AaTerm

    code = str(term_code or "").strip()
    if not code:
        if required:
            raise AppException("VALIDATION_ERROR", "业务记录必须绑定正式学期termCode")
        return None
    rows = db.query(AaTerm).filter(
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).all()
    matches = [row for row in rows if f"{row.year_code}-{row.term_no}" == code]
    if not matches:
        raise AppException("DATA_CONFLICT", f"termCode={code} 未匹配到本校正式学期", http_status=409)
    if len(matches) > 1:
        raise AppException("DATA_CONFLICT", f"termCode={code} 匹配到多个学期，请先修复基础数据", http_status=409)
    return matches[0]


def guard_term_code_writable(db, term_code, *, required: bool = True):
    term = resolve_term_by_code(db, term_code, required=required)
    if term is None:
        return None
    _base.guard_term_writable(db, term.id)
    return term
