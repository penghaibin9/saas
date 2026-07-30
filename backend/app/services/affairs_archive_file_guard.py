"""学工归档文件授权兼容入口。

阶段 2 已将 AFFAIRS_ARCHIVE 迁入公共文件 resolver registry，并由归档生成器显式写入
biz_type。保留 install() 只是避免旧路由聚合器导入断裂；本模块不再改写 file_service。
"""
from __future__ import annotations

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    _INSTALLED = True
