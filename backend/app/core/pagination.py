"""分页门面：统一分页参数与数据结构（实现复用 core/response.paginate）。"""
from __future__ import annotations

from app.core.response import paginate  # noqa: F401


def page_slice(items: list, page: int = 1, page_size: int = 20) -> list:
    """内存分页（mock/DB_ENABLED=False 阶段用）。"""
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    start = (page - 1) * page_size
    return items[start : start + page_size]
