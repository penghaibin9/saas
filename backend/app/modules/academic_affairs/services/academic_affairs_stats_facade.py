"""教务统计历史兼容入口。

正式范围门禁与公开查询入口已收口到 ``academic_affairs_stats_public_service``；
本文件保留旧导入路径，不修改旧统计 Service。
"""
from __future__ import annotations

from . import academic_affairs_stats_public_service as _canonical

_validate_college_param = _canonical._validate_college_param
_precheck = _canonical._precheck


def __getattr__(name):
    return getattr(_canonical, name)
