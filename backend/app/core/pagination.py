"""分页门面：统一分页参数与数据结构（实现复用 core/response.paginate）。"""
from __future__ import annotations

from app.core.response import paginate  # noqa: F401

PAGE_SIZE_MAX = 200
PAGE_SIZE_DEFAULT = 20


def normalize_page(page: int | None = 1, page_size: int | None = PAGE_SIZE_DEFAULT,
                   *, default_size: int = PAGE_SIZE_DEFAULT) -> tuple[int, int]:
    """统一 page>=1、1<=pageSize<=200。所有学工 list 入口应调用。"""
    p = max(1, int(page or 1))
    size = min(PAGE_SIZE_MAX, max(1, int(page_size if page_size is not None else default_size)))
    return p, size


def page_slice(items: list, page: int = 1, page_size: int = 20) -> list:
    """内存分页（仅 mock/极小集合；生产列表应走 SQL offset/limit）。"""
    page, page_size = normalize_page(page, page_size)
    start = (page - 1) * page_size
    return items[start : start + page_size]
