"""教务对象级数据范围最终安全门。

包 3 独立止血项：
- 成绩单查询与导出必须先裁决目标学生对象范围；
- 学院审核遇到无行政班教学任务时，必须回溯教学任务批次/课程开课学院，
  无法证明归属时 fail-closed，禁止把空 ``class_id`` 当作全校权限。

本模块只收口读取与审核范围，不修改正式成绩、有效成绩策略或工作流事务。
"""
from __future__ import annotations

from functools import wraps

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
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
    """从稳定教学任务、批次和课程身份解析成绩任务所属学院。"""
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    from app.services.db_service import _tid

    tenant_id = _tid()
    college_ids: set[int] = set()
    teaching_task = None
    course_id = getattr(task, "course_id", None)

    teaching_task_id = getattr(task, "teaching_task_id", None)
    if teaching_task_id:
        teaching_task = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.id == int(teaching_task_id),
            AaTeachingTask.tenant_id == tenant_id,
            AaTeachingTask.is_deleted.is_(False),
        )).first()
        if not teaching_task:
            raise no_data_scope("成绩任务关联的教学任务不存在或不在当前租户")
        course_id = course_id or teaching_task.course_id
        if teaching_task.batch_id:
            batch = db.scalars(select(AaTeachingTaskBatch).where(
                AaTeachingTaskBatch.id == int(teaching_task.batch_id),
                AaTeachingTaskBatch.tenant_id == tenant_id,
                AaTeachingTaskBatch.is_deleted.is_(False),
            )).first()
            if batch and batch.college_id:
                college_ids.add(int(batch.college_id))

    if course_id:
        course = db.scalars(select(AaCourse).where(
            AaCourse.id == int(course_id),
            AaCourse.tenant_id == tenant_id,
            AaCourse.is_deleted.is_(False),
        )).first()
        if not course:
            raise no_data_scope("成绩任务关联的课程版本不存在或不在当前租户")
        if course.owner_college_id:
            college_ids.add(int(course.owner_college_id))

    if len(college_ids) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务批次学院与课程开课学院不一致，禁止继续审核；请先修复任务归属",
            details={"collegeIds": sorted(college_ids)},
            http_status=409,
        )
    return college_ids


def strict_check_college_scope(db, task, user: dict | None):
    """学院审核范围：行政班优先；无行政班时必须证明唯一开课学院。"""
    current = user or {}
    role = str(current.get("currentRoleCode") or "").upper()
    if role in grade_core._REVIEW_ROLES or current.get("userType") == "PLATFORM_SUPER_ADMIN":
        return

    context = build_affairs_context(current, db)
    allowed_class_ids = context.allowed_class_ids(db)
    if allowed_class_ids is None:
        return

    class_id = getattr(task, "class_id", None)
    if class_id:
        if int(class_id) not in {int(value) for value in allowed_class_ids}:
            raise no_data_scope("该录入任务不在您的学院范围内")
        return

    target_college_ids = _resolve_target_college_ids(db, task)
    if not target_college_ids:
        raise no_data_scope("该成绩任务未绑定行政班或唯一开课学院，无法证明对象范围")

    allowed_college_ids = {int(value) for value in (context.college_ids or set())}
    if not allowed_college_ids or target_college_ids.isdisjoint(allowed_college_ids):
        raise no_data_scope("该无行政班成绩任务不在您的开课学院范围内")


_ORIGINAL_TRANSCRIPT = getattr(
    grade_service,
    "_package3_original_transcript",
    grade_service.transcript,
)


@wraps(_ORIGINAL_TRANSCRIPT)
def scoped_transcript(student_id, user):
    with grade_core.session() as db:
        require_student_scope(db, user, student_id)
    return _ORIGINAL_TRANSCRIPT(student_id, user)


scoped_transcript._academic_object_scope_guard = True


def install() -> None:
    """幂等安装到成绩公开服务与既有 core 审核入口。"""
    if not hasattr(grade_service, "_package3_original_transcript"):
        grade_service._package3_original_transcript = grade_service.transcript
    if not getattr(grade_service.transcript, "_academic_object_scope_guard", False):
        grade_service.transcript = scoped_transcript
    grade_core._check_college_scope = strict_check_college_scope
