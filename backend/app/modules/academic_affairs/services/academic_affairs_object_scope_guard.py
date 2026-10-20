"""教务对象级数据范围最终安全门。

包 3 独立止血项：
- 成绩单查询与导出必须先裁决目标学生对象范围；
- 学院审核遇到无行政班教学任务时，必须回溯教学任务批次/课程开课学院，
  无法证明归属时 fail-closed，禁止把空 ``class_id`` 当作全校权限。

本模块只收口读取与审核范围，不修改正式成绩、有效成绩策略或工作流事务。
"""
from __future__ import annotations

from functools import wraps

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException

from . import academic_affairs_grade_core_service as grade_core
from . import academic_affairs_grade_service as grade_service


def _positive_id(value, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}必须是有效正整数") from exc
    if parsed <= 0:
        raise AppException("VALIDATION_ERROR", f"{label}必须是有效正整数")
    return parsed


def require_student_scope(db, user: dict | None, student_id):
    """统一裁决成绩单目标学生；不存在、跨租户和越范围均不继续读取。"""
    sid = _positive_id(student_id, "studentId")
    context = build_affairs_context(user or {}, db)
    return context.require_student(db, sid)


def _resolve_target_college_ids(db, task) -> set[int]:
    from .academic_affairs_grade_correction_command import _task_college_id
    college_id = _task_college_id(db, task)
    return {college_id} if college_id else set()


def strict_check_college_scope(db, task, user: dict | None):
    """复用成绩核心当前范围；行政班不决定开课审核责任。"""
    return grade_core._check_college_scope(db, task, user or {})


_ORIGINAL_TRANSCRIPT = getattr(
    grade_service,
    "_package3_original_transcript",
    grade_service.transcript,
)


@wraps(_ORIGINAL_TRANSCRIPT)
def scoped_transcript(student_id, user, page=None, page_size=50, *, term=None):
    with grade_core.session() as db:
        require_student_scope(db, user, student_id)
    if page is None:
        return _ORIGINAL_TRANSCRIPT(student_id, user)
    return _ORIGINAL_TRANSCRIPT(
        student_id,
        user,
        page=page,
        page_size=page_size,
        term=term,
    )


scoped_transcript._academic_object_scope_guard = True


def install() -> None:
    """幂等安装到成绩公开服务与既有 core 审核入口。"""
    if not hasattr(grade_service, "_package3_original_transcript"):
        grade_service._package3_original_transcript = grade_service.transcript
    if not getattr(grade_service.transcript, "_academic_object_scope_guard", False):
        grade_service.transcript = scoped_transcript
