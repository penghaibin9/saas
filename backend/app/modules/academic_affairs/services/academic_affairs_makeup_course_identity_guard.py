"""补考重修免修最终安全历史兼容入口。

稳定身份、数据范围、正式成绩来源与学期门禁已收口到
``academic_affairs_makeup_service``。本文件不再覆盖任何模块函数。
"""
from __future__ import annotations

from . import academic_affairs_makeup_service as _canonical

_base = _canonical
_scope = _canonical
_term = _canonical
_grade = _canonical.grade_service
_legacy = _canonical

makeup_pending = _canonical.makeup_pending
clearance_scan = _canonical.clearance_scan
retake_apply = _canonical.retake_apply
retake_list = _canonical.retake_list
exemption_apply = _canonical.exemption_apply
exemption_review = _canonical.exemption_review
exemption_list = _canonical.exemption_list
merge_deferred = _canonical.merge_deferred
finish_makeup_batch = _canonical.finish_makeup_batch


def __getattr__(name):
    return getattr(_canonical, name)
