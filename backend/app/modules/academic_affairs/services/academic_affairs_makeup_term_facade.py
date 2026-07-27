"""补考、清考、重修、免修学期写保护历史兼容入口。

正式事务与学期门禁已经合并到 ``academic_affairs_makeup_service``。
本文件仅保留旧导入路径，不再包装或覆盖 core Service。
"""
from __future__ import annotations

from . import academic_affairs_makeup_service as _canonical

_base = _canonical
_legacy = _canonical

_term_code = _canonical._term_code
_guard_term_id = _canonical._guard_term_id
_guard_code = _canonical._guard_code
_current_term = _canonical._current_term
_selected_term = _canonical._selected_term
_guard_batch = _canonical._guard_batch

create_makeup_batch = _canonical.create_makeup_batch
create_clearance_batch = _canonical.create_clearance_batch
link_exam_batch = _canonical.link_exam_batch
publish_makeup_batch = _canonical.publish_makeup_batch
enter_makeup_score = _canonical.enter_makeup_score
college_review_scores = _canonical.college_review_scores
finish_makeup_batch = _canonical.finish_makeup_batch
retake_apply = _canonical.retake_apply
retake_review = _canonical.retake_review
retake_enroll = _canonical.retake_enroll
exemption_apply = _canonical.exemption_apply
exemption_review = _canonical.exemption_review
merge_deferred = _canonical.merge_deferred


def __getattr__(name):
    return getattr(_canonical, name)
