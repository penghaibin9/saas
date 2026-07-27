"""成绩正式名单历史兼容入口。

名单展示、录入、导入和提交已收口到 ``academic_affairs_grade_service``。
本文件仅保留旧导入路径，不再覆盖任何模块函数。
"""
from __future__ import annotations

from . import academic_affairs_grade_service as _canonical

_base = _canonical
_legacy = _canonical

_official_roster = _canonical._official_roster
_require_ready_roster = _canonical._require_ready_roster
roster = _canonical.roster
enter_score = _canonical.enter_score
grade_import_dry_run = _canonical.grade_import_dry_run
grade_import_confirm = _canonical.grade_import_confirm
submit_task = _canonical.submit_task


def __getattr__(name):
    return getattr(_canonical, name)
