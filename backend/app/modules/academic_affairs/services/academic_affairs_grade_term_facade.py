"""成绩学期写保护与名单冻结历史兼容入口。

正式实现已经合并到 ``academic_affairs_grade_service``。旧导入路径继续可用，
但本文件不再修改底层 Service 或维护第二套提交事务。
"""
from __future__ import annotations

from . import academic_affairs_grade_service as _canonical

_base = _canonical
_legacy = _canonical

grade_import_confirm = _canonical.grade_import_confirm
submit_task = _canonical.submit_task


def __getattr__(name):
    return getattr(_canonical, name)
