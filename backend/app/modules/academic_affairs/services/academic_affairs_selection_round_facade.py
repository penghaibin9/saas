"""选课轮次历史兼容入口。

正式轮次状态机、归档写保护、并发锁和确定性摇号统一由
``academic_affairs_selection_round_service`` 持有。本模块只保留旧 import 路径，
不得再维护第二套轮次写事务。
"""
from __future__ import annotations

import importlib

_canonical = importlib.import_module(
    ".academic_affairs_selection_round_service",
    package=__package__,
)
# 保留历史属性名，避免旧脚本/测试按 ``_legacy`` 读取时失效。
_legacy = _canonical

MODES = _canonical.MODES
create_round = _canonical.create_round
open_round = _canonical.open_round
close_round = _canonical.close_round
draw_round = _canonical.draw_round


def __getattr__(name):
    """其它只读 DTO、常量和兼容 helper 透明转给正式 Round Service。"""
    return getattr(_canonical, name)
