"""教务归档结构化语义兼容入口。

正式实现已经合并到 ``academic_affairs_archive_service``。本文件仅保留历史导入路径，
不再覆盖归档执行器函数，也不依赖 Facade 加载顺序。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical

precheck = _canonical.precheck
run_check = _canonical.run_check
get_batch = _canonical.get_batch
parse_persisted_remark = _canonical.parse_persisted_remark
_persisted_remark = _canonical._persisted_remark
_evaluate_domains = _canonical._evaluate_domains
_items_dto = _canonical._items_dto


def __getattr__(name):
    return getattr(_canonical, name)
