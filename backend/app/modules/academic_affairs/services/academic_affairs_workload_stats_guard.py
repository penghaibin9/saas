"""教师工作量统计的学期口径与大校规模安全层。

只接管教务统计的 workload 聚合/下钻读取：教学任务通过 AaTeachingTaskBatch.term_id 过滤，
审核通过的申报工时通过 AaTerm 对应 term_code 候选过滤；教师聚合在 SQL 完成。申报/审核写链、
教学任务事实和人事正式核算均保持既有 owner。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException

from . import academic_affairs_stats_service as stats
from .academic_affairs_production_audit_guard import _bounded_page_size


def _page_values(page, page_size) -> tuple[int, int]:
    try:
        page_no = int(1 if page is None else page)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    if page_no < 1:
        raise AppException("VALIDATION_ERROR", "page 必须大于等于 1")
    return page_no, _bounded_page_size(page_size, default=20)


def _task_conditions(term_id, class_ids, teacher_key=None):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    conditions = [
        AaTeachingTask.tenant_id == stats._tid(),
        AaTeachingTask.is_deleted.is_(False),
    ]
    if teacher_key is None:
        conditions.append(AaTeachingTask.teacher_key.isnot(None))
    else:
        conditions.append(AaTeachingTask.teacher_key == teacher_key)
    if class_ids is not None:
        conditions.append(AaTeachingTask.class_id.in_(list(class_ids) or [-1]))
    if term_id:
        batch_ids = select(AaTeachingTaskBatch.id).where(
            AaTeachingTaskBatch.tenant_id == stats._tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        conditions.append(AaTeachingTask.batch_id.in_(batch_ids))
    return conditions


def _declared_hours_by_teacher(db, term_id=None) -> dict[str, float]:
    from app.models import AaWorkloadDeclaration

    conditions = [
        AaWorkloadDeclaration.tenant_id == stats._tid(),
        AaWorkloadDeclaration.status == "APPROVED",
        AaWorkloadDeclaration.is_deleted.is_(False),
        AaWorkloadDeclaration.teacher_key.isnot(None),
    ]
    term_codes = stats._term_codes(db, term_id)
    if term_codes is not None:
        if not term_codes:
            return {}
        conditions.append(AaWorkloadDeclaration.term_code.in_(list(term_codes)))
    rows = db.execute(
        select(
            AaWorkloadDeclaration.teacher_key,
            func.coalesce(func.sum(AaWorkloadDeclaration.hours), 0),
        )
        .where(*conditions)
        .group_by(AaWorkloadDeclaration.teacher_key)
    ).all()
    return {str(teacher_key): float(hours or 0) for teacher_key, hours in rows if teacher_key}


def workload_stats(user, term_id=None, college_id=None) -> dict:
    """教师工作量聚合：学期口径真实生效，基础任务和申报工时均不跨学期串账。"""
    from app.models import AaTeachingTask

    with stats.session() as db:
        scope = stats._resolve_scope(user, db)
        stats._validate_college_param(scope, college_id)
        class_ids = stats._class_ids_scope(db, scope, college_id)
        if class_ids is not None and not class_ids:
            return {
                "ranking": [],
                "disclaimer": stats._WORKLOAD_DISCLAIMER,
                "scope": {"blocked": scope.blocked},
            }

        rows = db.execute(
            select(
                AaTeachingTask.teacher_key,
                func.max(AaTeachingTask.teacher_name),
                func.coalesce(func.sum(AaTeachingTask.total_hours), 0),
                func.count(AaTeachingTask.id),
            )
            .where(*_task_conditions(term_id, class_ids))
            .group_by(AaTeachingTask.teacher_key)
        ).all()
        declared = _declared_hours_by_teacher(db, term_id)
        ranking = []
        for teacher_key, teacher_name, total_hours, task_count in rows:
            key = str(teacher_key or "")
            base_hours = int(total_hours or 0)
            declared_hours = round(declared.get(key, 0.0), 1)
            ranking.append({
                "teacherKey": key,
                "teacherName": teacher_name or "",
                "totalHours": base_hours,
                "taskCount": int(task_count or 0),
                "declaredHours": declared_hours,
                "combinedHours": round(base_hours + declared_hours, 1),
            })
        ranking.sort(key=lambda row: (-row["combinedHours"], row["teacherKey"]))
        return {
            "ranking": ranking,
            "disclaimer": stats._WORKLOAD_DISCLAIMER,
            "scope": {"blocked": scope.blocked},
        }


workload_stats._workload_term_sql_guard = True


def workload_detail(user, teacher_key, college_id=None, page=1, page_size=20, term_id=None):
    """单教师授课明细；term_id 新增为尾部可选参数，旧位置参数调用保持兼容。"""
    if not str(teacher_key or "").strip():
        raise AppException("VALIDATION_ERROR", "teacherKey 必填")
    page_no, size = _page_values(page, page_size)
    from app.models import AaTeachingTask

    with stats.session() as db:
        scope = stats._resolve_scope(user, db)
        stats._validate_college_param(scope, college_id)
        class_ids = stats._class_ids_scope(db, scope, college_id)
        if class_ids is not None and not class_ids:
            return [], 0
        q = select(AaTeachingTask).where(
            *_task_conditions(term_id, class_ids, str(teacher_key))
        )
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(
            q.order_by(AaTeachingTask.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [{
            "taskId": str(task.id),
            "courseName": task.course_name,
            "teachingClassName": task.teaching_class_name,
            "weeklyHours": task.weekly_hours,
            "totalHours": task.total_hours,
            "status": task.status,
        } for task in rows], total


workload_detail._workload_term_sql_guard = True


def install() -> None:
    if not hasattr(stats, "_workload_stats_guard_original_stats"):
        stats._workload_stats_guard_original_stats = stats.workload_stats
    if not hasattr(stats, "_workload_stats_guard_original_detail"):
        stats._workload_stats_guard_original_detail = stats.workload_detail
    stats.workload_stats = workload_stats
    stats.workload_detail = workload_detail
