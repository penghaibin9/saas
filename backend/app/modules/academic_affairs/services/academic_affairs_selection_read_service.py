"""D6 选课读侧 compatibility owner。

Selection Final / AaSelectionRecord / TeachingRoster 仍是唯一业务事实与写链。
D6 已有 SQL 分页、scope 和聚合优化原样保存在 ``academic_affairs_selection_read_core_service``；
本模块保持原公开/内部属性兼容，唯独学生选课列表必须消费 B-W5 Final projection，禁止
包初始化时用旧 ``_course_dto`` 覆盖 ``statusLabel/allowedActions/reselect`` 等 B-C3 合同。
"""
from __future__ import annotations

import importlib

from . import academic_affairs_selection_read_core_service as _read_core


# 完整保留 D6 read-service 既有函数与内部 helper；production_audit_guard / round guard
# 仍可访问 _core/_scope_values/_require_batch_visible 等内部兼容属性。
for _name in dir(_read_core):
    if _name.startswith("__") or _name == "student_courses":
        continue
    globals()[_name] = getattr(_read_core, _name)


# services.__init__ 在 import 本模块之后才把 Final.student_courses 绑定到本 wrapper。
# 此处先捕获 Final 原始 B-C3 projection 函数对象，避免后续 monkey-patch 形成递归。
_final = importlib.import_module(
    ".academic_affairs_selection_final_service",
    package=__package__,
)
_final_student_courses_projection = _final.student_courses


def student_courses(user, batch_id=None):
    """学生列表只返回 OPEN，或本人真实具备补选资格的 CLOSED B-C3 projection。"""
    # Final evaluator 会复用 canonical term guard。列表只读必须显式切换为 non-locking
    # term validation，避免大量学生刷新列表时争抢同一 AaTerm 排他锁。
    with _final.selection_readonly_term_guard():
        groups = _final_student_courses_projection(user, batch_id) or []
    visible = []
    for group in groups:
        batch = dict(group.get("batch") or {})
        courses = list(group.get("courses") or [])
        status = str(batch.get("status") or "").upper()
        if status == "OPEN":
            visible.append(group)
            continue
        if status == "CLOSED" and any(bool(course.get("reselect")) for course in courses):
            visible.append(group)
    return visible
