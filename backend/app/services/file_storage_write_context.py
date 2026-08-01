"""物理存储写入的一次性模块上下文。

文件业务层在调用 ``StorageBackend.persist`` 前显式声明业务类型；治理后端读取模块后执行
配额预留。ContextVar 隔离异步请求，作用域退出即恢复，不使用全局可变状态或调用栈猜测。
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from app.services.file_storage_quota_reservation_service import _module_from_biz

_module_code: ContextVar[str] = ContextVar("file_storage_write_module", default="SHARED")


@contextmanager
def storage_write_scope(biz_type: str | None) -> Iterator[None]:
    token = _module_code.set(_module_from_biz(biz_type))
    try:
        yield
    finally:
        _module_code.reset(token)


def current_storage_module() -> str:
    return str(_module_code.get() or "SHARED").upper()
