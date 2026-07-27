"""培养方案绑定校验兼容入口。

绑定班级有效性、专业年级一致性和跨方案唯一性已经合并到
``academic_affairs_program_governance_service``。本文件只保留旧导入路径兼容，
不再维护第二套校验实现。
"""
from __future__ import annotations

from . import academic_affairs_program_governance_service as _canonical

validate_program_db = _canonical.validate_program_db
validate_program = _canonical.validate_program
program_governance_summary = _canonical.program_governance_summary
opening_differences = _canonical.opening_differences


def __getattr__(name):
    return getattr(_canonical, name)
