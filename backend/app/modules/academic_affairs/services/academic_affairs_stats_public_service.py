"""教务统计统一公开 Service。

所有带学院筛选的统计、下钻和导出在进入旧聚合实现前再次校验数据范围，避免受限角色
在未配置任何学院/班级范围时通过主动传入 ``collegeId`` 扩大权限。统计域为只读聚合，
因此前置范围校验与实际查询分离不会产生写事务一致性问题。
"""
from __future__ import annotations

import importlib

from app.core.affairs_security import _derive_keys, no_data_scope

_legacy = importlib.import_module(
    ".academic_affairs_stats_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_legacy, name)


def _validate_college_param(scope, college_id):
    if getattr(scope, "blocked", False):
        raise no_data_scope("当前身份未配置任何可管理学院或班级范围")
    if college_id and not getattr(scope, "all", False):
        allowed_colleges = set(getattr(scope, "college_ids", set()) or set())
        allowed_classes = set(getattr(scope, "class_ids", set()) or set())
        if allowed_colleges and int(college_id) not in allowed_colleges:
            raise no_data_scope("该学院不在您的数据范围内")
        if not allowed_colleges and not allowed_classes:
            raise no_data_scope("当前身份没有可验证的学院数据范围")


def _precheck(user, college_id=None):
    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        return scope


def overview(user, term_id=None, college_id=None, major_id=None):
    _precheck(user, college_id)
    return _legacy.overview(user, term_id, college_id, major_id)


def registration_unregistered(user, term_id=None, college_id=None, major_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.registration_unregistered(user, term_id, college_id, major_id, page, page_size)


def status_change_detail(user, change_type=None, term_id=None, college_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.status_change_detail(user, change_type, term_id, college_id, page, page_size)


def warning_detail(user, level=None, source=None, college_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.warning_detail(user, level, source, college_id, page, page_size)


def export_stats_xlsx(user, domain="overview", term_id=None, college_id=None, major_id=None, purpose=""):
    _precheck(user, college_id)
    return _legacy.export_stats_xlsx(user, domain, term_id, college_id, major_id, purpose)


def status_change_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.status_change_stats(user, term_id, college_id)


def registration_stats(user, term_id=None, college_id=None, major_id=None):
    _precheck(user, college_id)
    return _legacy.registration_stats(user, term_id, college_id, major_id)


def course_stats(user, category=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.course_stats(user, category, college_id)


def course_detail(user, category=None, college_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.course_detail(user, category, college_id, page, page_size)


def teaching_task_stats(user, college_id=None, term_id=None):
    _precheck(user, college_id)
    return _legacy.teaching_task_stats(user, college_id, term_id)


def teaching_task_pending(user, college_id=None, term_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.teaching_task_pending(user, college_id, term_id, page, page_size)


def schedule_stats(user, college_id=None, term_id=None):
    _precheck(user, college_id)
    return _legacy.schedule_stats(user, college_id, term_id)


def schedule_conflicts(user, college_id=None, term_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.schedule_conflicts(user, college_id, term_id, page, page_size)


def grade_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.grade_stats(user, term_id, college_id)


def grade_detail(user, term_id=None, college_id=None, course_name=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.grade_detail(user, term_id, college_id, course_name, page, page_size)


def warning_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.warning_stats(user, term_id, college_id)


def graduation_stats(user, batch_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.graduation_stats(user, batch_id, college_id)


def graduation_abnormal(user, batch_id=None, college_id=None, item_type=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.graduation_abnormal(user, batch_id, college_id, item_type, page, page_size)


def workload_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.workload_stats(user, term_id, college_id)


def workload_detail(user, teacher_key, college_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role == "ACADEMIC_TEACHER":
        keys = {str(value) for value in (_derive_keys(user) or set()) if str(value).strip()}
        if not keys or str(teacher_key or "") not in keys:
            raise no_data_scope("任课教师仅可查看本人的工作量明细")
    return _legacy.workload_detail(user, teacher_key, college_id, page, page_size)


def course_selection_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.course_selection_stats(user, term_id, college_id)


def course_selection_detail(user, term_id=None, college_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.course_selection_detail(user, term_id, college_id, page, page_size)


def exam_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    return _legacy.exam_stats(user, term_id, college_id)


def exam_detail(user, term_id=None, college_id=None, incident_type=None, page=1, page_size=20):
    _precheck(user, college_id)
    return _legacy.exam_detail(user, term_id, college_id, incident_type, page, page_size)


# 不带学院筛选的只读入口直接公开。
filters = _legacy.filters
resource_stats = _legacy.resource_stats
resource_detail = _legacy.resource_detail
