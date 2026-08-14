"""教务统计学生级下钻的统一分页边界。

保持原查询、dataScope、审计 owner 与已冻结的授权展示口径不变：学号属于校内业务编码，
授权教务下钻继续展示原 studentNo；本层只在内部 service 调用层补 page/pageSize fail-closed。
适用于当前仍由公开 stats 持有的注册、预警、学籍异动、成绩挂科四条学生级下钻；
考务与毕业继续由各自 canonical guard 持有。
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_stats_service as stats
from .academic_affairs_production_audit_guard import _bounded_page_size


_ORIGINAL_REGISTRATION = getattr(
    stats, "_stats_privacy_original_registration_unregistered", stats.registration_unregistered
)
_ORIGINAL_WARNING = getattr(
    stats, "_stats_privacy_original_warning_detail", stats.warning_detail
)
_ORIGINAL_STATUS_CHANGE = getattr(
    stats, "_stats_privacy_original_status_change_detail", stats.status_change_detail
)
_ORIGINAL_GRADE = getattr(
    stats, "_stats_privacy_original_grade_detail", stats.grade_detail
)


def _page_values(page, page_size) -> tuple[int, int]:
    try:
        page_no = int(1 if page is None else page)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    if page_no < 1:
        raise AppException("VALIDATION_ERROR", "page 必须大于等于 1")
    return page_no, _bounded_page_size(page_size, default=20)


def registration_unregistered(user, term_id=None, college_id=None, major_id=None,
                              page=1, page_size=20):
    page_no, size = _page_values(page, page_size)
    return _ORIGINAL_REGISTRATION(user, term_id, college_id, major_id, page_no, size)


registration_unregistered._stats_student_privacy_guard = True


def warning_detail(user, level=None, source=None, college_id=None, page=1, page_size=20):
    page_no, size = _page_values(page, page_size)
    return _ORIGINAL_WARNING(user, level, source, college_id, page_no, size)


warning_detail._stats_student_privacy_guard = True


def status_change_detail(user, change_type=None, term_id=None, college_id=None,
                         page=1, page_size=20):
    page_no, size = _page_values(page, page_size)
    return _ORIGINAL_STATUS_CHANGE(user, change_type, term_id, college_id, page_no, size)


status_change_detail._stats_student_privacy_guard = True


def grade_detail(user, term_id=None, college_id=None, course_name=None,
                 page=1, page_size=20):
    page_no, size = _page_values(page, page_size)
    return _ORIGINAL_GRADE(user, term_id, college_id, course_name, page_no, size)


grade_detail._stats_student_privacy_guard = True


def install() -> None:
    bindings = (
        ("registration_unregistered", "_stats_privacy_original_registration_unregistered", registration_unregistered),
        ("warning_detail", "_stats_privacy_original_warning_detail", warning_detail),
        ("status_change_detail", "_stats_privacy_original_status_change_detail", status_change_detail),
        ("grade_detail", "_stats_privacy_original_grade_detail", grade_detail),
    )
    for public_name, original_name, wrapper in bindings:
        if not hasattr(stats, original_name):
            setattr(stats, original_name, getattr(stats, public_name))
        if not getattr(getattr(stats, public_name), "_stats_student_privacy_guard", False):
            setattr(stats, public_name, wrapper)
