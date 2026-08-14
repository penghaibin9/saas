"""教务统计统一公开 Service。

所有带学院筛选的统计、下钻和导出在进入旧聚合实现前再次校验数据范围，避免受限角色
在未配置任何学院/班级范围时通过主动传入 ``collegeId`` 扩大权限。08/09/14 三个新增统计域
直接消费 canonical contract，避免历史同名函数覆盖或 import 顺序再次让页面与 xlsx 口径漂移。
"""
from __future__ import annotations

import importlib
from datetime import datetime

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


def _canonical_export(user, domain, term_id, college_id, purpose):
    """08/09/14 三个新增统计域直接按 canonical 数据结构生成查询件并保留水印/审计。"""
    from app.core.exceptions import AppException
    from app.services.xlsx_util import build_ledger_xlsx
    from . import academic_affairs_stats_contract_facade as canonical

    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    user_ctx = _legacy._cur_user()
    watermark = (
        f"导出人：{user_ctx.get('realName') or user_ctx.get('loginName') or '-'}  "
        f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}"
    )
    if domain == "courseSelection":
        title = "选课统计"
        data = canonical.course_selection_stats(user, term_id, college_id)
        headers = ["批次状态", "批次数"]
        rows = [[item["key"], item["count"]] for item in data["byBatchStatus"]]
    elif domain == "exam":
        title = "考务统计"
        data = canonical.exam_stats(user, term_id, college_id)
        headers = ["课程总数", "已确认数", "确认率(%)", "缺考人次", "违纪人次"]
        rows = [[
            data["courseTotal"], data["confirmedCount"], data["confirmRate"],
            data["absentCount"], data["violationCount"],
        ]]
    elif domain == "resource":
        title = "教学资源统计"
        data = canonical.resource_stats(user)
        headers = ["教室状态", "数量"]
        rows = [[item["key"], item["count"]] for item in data["byStatus"]]
    else:
        raise AppException("VALIDATION_ERROR", f"未知 canonical 导出维度：{domain}")

    content = build_ledger_xlsx(title, headers, rows, watermark=watermark)
    with _legacy.session() as db:
        _legacy._audit(db, "STATS_EXPORT", f"{title} 导出 用途={purpose[:100]}")
        db.commit()
    return content


def export_stats_xlsx(user, domain="overview", term_id=None, college_id=None, major_id=None, purpose=""):
    _precheck(user, college_id)
    if domain in {"courseSelection", "exam", "resource"}:
        return _canonical_export(user, domain, term_id, college_id, purpose)
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


def workload_detail(user, teacher_key, college_id=None, page=1, page_size=20, term_id=None):
    _precheck(user, college_id)
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role == "ACADEMIC_TEACHER":
        keys = {str(value) for value in (_derive_keys(user) or set()) if str(value).strip()}
        if not keys or str(teacher_key or "") not in keys:
            raise no_data_scope("任课教师仅可查看本人的工作量明细")
    return _legacy.workload_detail(user, teacher_key, college_id, page, page_size, term_id)


def course_selection_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    from .academic_affairs_stats_contract_facade import course_selection_stats as canonical
    return canonical(user, term_id, college_id)


def course_selection_detail(user, term_id=None, college_id=None, page=1, page_size=20):
    _precheck(user, college_id)
    from .academic_affairs_stats_contract_facade import course_selection_detail as canonical
    return canonical(user, term_id, college_id, page, page_size)


def exam_stats(user, term_id=None, college_id=None):
    _precheck(user, college_id)
    from .academic_affairs_stats_contract_facade import exam_stats as canonical
    return canonical(user, term_id, college_id)


def exam_detail(user, term_id=None, college_id=None, incident_type=None, page=1, page_size=20):
    _precheck(user, college_id)
    from .academic_affairs_stats_contract_facade import exam_detail as canonical
    return canonical(user, term_id, college_id, incident_type, page, page_size)


def resource_stats(user):
    from .academic_affairs_stats_contract_facade import resource_stats as canonical
    return canonical(user)


def resource_detail(user, page=1, page_size=20):
    from .academic_affairs_stats_contract_facade import resource_detail as canonical
    return canonical(user, page, page_size)


filters = _legacy.filters
