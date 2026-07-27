"""补考、清考、重修、免修稳定课程身份历史兼容入口。

正式能力已合并到 ``academic_affairs_makeup_service``。本文件只保留旧导入路径，
不再维护第二套状态机或修改任何模块函数。
"""
from __future__ import annotations

from . import academic_affairs_makeup_service as _canonical

_base = _canonical
_term = _canonical
_grade = _canonical.grade_service
_legacy = _canonical

_academic_student_for_profile = _canonical._academic_student_for_profile
_effective_failed_grade = _canonical._effective_failed_grade
enroll_makeup_by_grade = _canonical.enroll_makeup_by_grade
enroll_makeup = _canonical.enroll_makeup
clearance_scan = _canonical.clearance_scan
finish_makeup_batch = _canonical.finish_makeup_batch
retake_apply = _canonical.retake_apply
retake_review = _canonical.retake_review
retake_enroll = _canonical.retake_enroll
exemption_apply = _canonical.exemption_apply
exemption_review = _canonical.exemption_review
merge_deferred = _canonical.merge_deferred


def __getattr__(name):
    return getattr(_canonical, name)
