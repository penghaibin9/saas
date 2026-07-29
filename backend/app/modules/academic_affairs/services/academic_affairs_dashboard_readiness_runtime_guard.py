"""教务 readiness 真实模型兼容历史入口。

运行风险统计已显式收口到 ``academic_affairs_dashboard_readiness_final_service``；
本文件仅保留旧导入路径，不再覆盖基础 Service。
"""
from __future__ import annotations

from . import academic_affairs_dashboard_readiness_final_service as _canonical

_base = _canonical
_operation_risks = _canonical._operation_risks
readiness = _canonical.readiness
export_readiness_xlsx = _canonical.export_readiness_xlsx


def __getattr__(name):
    return getattr(_canonical, name)
