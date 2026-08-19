"""教师工作量统计的学期口径、规模安全与正式来源对账层。

只接管教务统计的 workload 聚合/下钻读取：
- legacy 计划学时继续保留，避免破坏既有统计/导出合同；
- 正式授课来源只消费 C-C1/B-C1 已冻结的 ScopeHead -> PUBLISHED -> EFFECTIVE
  occurrence projection，停课/调课后的旧课位不会继续作为当前来源；
- 正式监考来源只消费已确认监考 + 正式考试批次，不把 ASSIGNED/草稿当已发生工作量；
- 审核通过的人工申报仍独立展示，不反向成为教学关系 Authority，也不擅自把监考分钟
  折算为绩效课时（学校系数规则尚未冻结）。

申报/审核写链、教学任务、课表、考务和人事正式核算均保持既有 owner。公开 service
继续持有 dataScope / 教师本人门禁，本层只替换读模型并保持旧调用兼容。
"""
from __future__ import annotations

import importlib
from collections import defaultdict

from sqlalchemy import func, select

from app.core.affairs_security import _derive_keys, no_data_scope
from app.core.exceptions import AppException

stats = importlib.import_module(
    ".academic_affairs_stats_service",
    package=__package__,
)
public_stats = importlib.import_module(
    ".academic_affairs_stats_public_service",
    package=__package__,
)
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
        AaTeachingTask.status != "MERGED",
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


def _declared_facts_by_teacher(db, term_id=None) -> dict[str, dict]:
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
            func.max(AaWorkloadDeclaration.teacher_name),
            AaWorkloadDeclaration.category,
            func.coalesce(func.sum(AaWorkloadDeclaration.hours), 0),
        )
        .where(*conditions)
        .group_by(AaWorkloadDeclaration.teacher_key, AaWorkloadDeclaration.category)
    ).all()
    result: dict[str, dict] = {}
    for teacher_key, teacher_name, category, hours in rows:
        if not teacher_key:
            continue
        key = str(teacher_key)
        item = result.setdefault(key, {
            "teacherName": teacher_name or "",
            "approvedHours": 0.0,
            "byCategory": {},
        })
        if teacher_name and not item["teacherName"]:
            item["teacherName"] = teacher_name
        value = float(hours or 0)
        item["approvedHours"] += value
        item["byCategory"][str(category or "OTHER")] = value
    for item in result.values():
        item["approvedHours"] = round(item["approvedHours"], 1)
    return result


def _declared_hours_by_teacher(db, term_id=None) -> dict[str, float]:
    """Backward-compatible helper retained for existing callers/tests."""
    return {
        key: float(value.get("approvedHours") or 0)
        for key, value in _declared_facts_by_teacher(db, term_id).items()
    }


def _pattern_period_count(pattern: dict) -> int:
    """Count concrete teaching periods represented by one formal recurrence pattern."""
    start = int(pattern.get("startWeek") or 0)
    end = int(pattern.get("endWeek") or 0)
    if start <= 0 or end <= 0 or end < start:
        raise AppException(
            "DATA_CONFLICT",
            "正式课表存在非法教学周范围，工作量来源无法对账",
            http_status=409,
        )
    parity = str(pattern.get("weekParity") or "ALL").upper()
    if parity not in {"ALL", "ODD", "EVEN"}:
        raise AppException(
            "DATA_CONFLICT",
            "正式课表存在未知单双周配置，工作量来源无法对账",
            http_status=409,
        )
    count = 0
    for week in range(start, end + 1):
        if parity == "ODD" and week % 2 == 0:
            continue
        if parity == "EVEN" and week % 2 == 1:
            continue
        count += 1
    return count


def _formal_teaching_facts(db, tasks) -> tuple[dict[str, dict], dict[int, dict]]:
    """Resolve current formal schedule evidence for a bounded set of TeachingTasks.

    The occurrence consumer already owns ScopeHead/PUBLISHED/EFFECTIVE/change validation;
    this read model only aggregates its returned recurrence patterns.  A task with missing or
    conflicting current schedule is surfaced as an issue instead of silently falling back to
    historical EFFECTIVE rows or planned ``total_hours``.
    """
    from app.models import AaTeachingTaskBatch, AaTerm
    from . import academic_affairs_attendance_occurrence_consumer as occurrence

    task_list = list(tasks or [])
    if not task_list:
        return {}, {}
    batch_ids = sorted({int(task.batch_id) for task in task_list if task.batch_id})
    batches = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == stats._tid(),
        AaTeachingTaskBatch.id.in_(batch_ids or [-1]),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()
    batch_by_id = {int(row.id): row for row in batches}
    term_ids = sorted({int(row.term_id) for row in batches if row.term_id})
    terms = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == stats._tid(),
        AaTerm.id.in_(term_ids or [-1]),
        AaTerm.is_deleted.is_(False),
    )).all()
    term_by_id = {int(row.id): row for row in terms}

    by_teacher: dict[str, dict] = {}
    by_task: dict[int, dict] = {}
    grouped: dict[int, list] = defaultdict(list)
    for task in task_list:
        batch = batch_by_id.get(int(task.batch_id or 0))
        if not batch or not batch.term_id:
            by_task[int(task.id)] = {
                "status": "CONFLICT",
                "formalPeriods": 0,
                "issue": "教学任务缺少有效学期批次，无法回链正式课表",
            }
            continue
        grouped[int(batch.term_id)].append((task, batch))

    for term_id, bindings in grouped.items():
        term = term_by_id.get(term_id)
        if not term:
            for task, _batch in bindings:
                by_task[int(task.id)] = {
                    "status": "CONFLICT",
                    "formalPeriods": 0,
                    "issue": "教学任务学期不存在或已删除，无法回链正式课表",
                }
            continue
        projections = occurrence.formal_schedule_patterns_for_tasks(db, bindings, term)
        for task, _batch in bindings:
            task_id = int(task.id)
            projection = projections.get(task_id) or {
                "status": "CONFLICT",
                "issue": "无法读取当前正式课次投影",
                "patterns": [],
            }
            status = str(projection.get("status") or "CONFLICT").upper()
            periods = 0
            if status == "READY":
                periods = sum(_pattern_period_count(row) for row in projection.get("patterns") or [])
            fact = {
                "status": status,
                "formalPeriods": int(periods),
                "issue": projection.get("issue") or "",
            }
            by_task[task_id] = fact
            teacher_key = str(task.teacher_key or "").strip()
            if not teacher_key:
                continue
            teacher = by_teacher.setdefault(teacher_key, {
                "formalTeachingPeriods": 0,
                "formalTaskCount": 0,
                "sourceIssueCount": 0,
                "sourceIssues": [],
            })
            if status == "READY":
                teacher["formalTeachingPeriods"] += int(periods)
                teacher["formalTaskCount"] += 1
            else:
                teacher["sourceIssueCount"] += 1
                if len(teacher["sourceIssues"]) < 20:
                    teacher["sourceIssues"].append({
                        "taskId": str(task_id),
                        "courseName": task.course_name or "",
                        "status": status,
                        "message": projection.get("issue") or "当前教学任务没有可消费的正式课次",
                    })
    return by_teacher, by_task


def _formal_invigilation_facts(db, scope, college_id=None, term_id=None) -> dict[str, dict]:
    """Aggregate confirmed invigilation from formal exam facts without inventing pay coefficients."""
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    conditions = [
        AaExamInvigilator.tenant_id == stats._tid(),
        AaExamInvigilator.is_deleted.is_(False),
        AaExamInvigilator.confirm_status == "CONFIRMED",
        AaExamRoom.tenant_id == stats._tid(),
        AaExamRoom.is_deleted.is_(False),
        AaExamRoom.status == "ACTIVE",
        AaExamCourse.tenant_id == stats._tid(),
        AaExamCourse.is_deleted.is_(False),
        AaExamCourse.status == "CONFIRMED",
        AaExamBatch.tenant_id == stats._tid(),
        AaExamBatch.is_deleted.is_(False),
        AaExamBatch.status.in_(["PUBLISHED", "FINISHED", "ARCHIVED"]),
    ]
    if term_id:
        conditions.append(AaExamBatch.term_id == int(term_id))
    colleges = stats._college_ids_scope(db, scope, college_id)
    if colleges is not None:
        if not colleges:
            return {}
        conditions.append(AaExamCourse.college_id.in_(list(colleges)))

    rows = db.execute(
        select(
            AaExamInvigilator.teacher_key,
            func.max(AaExamInvigilator.teacher_name),
            func.count(AaExamInvigilator.id),
            func.coalesce(func.sum(AaExamCourse.duration_minutes), 0),
        )
        .select_from(AaExamInvigilator)
        .join(AaExamRoom, AaExamRoom.id == AaExamInvigilator.exam_room_id)
        .join(AaExamCourse, AaExamCourse.id == AaExamRoom.exam_course_id)
        .join(AaExamBatch, AaExamBatch.id == AaExamCourse.batch_id)
        .where(*conditions)
        .group_by(AaExamInvigilator.teacher_key)
    ).all()
    return {
        str(teacher_key): {
            "teacherName": teacher_name or "",
            "confirmedCount": int(count or 0),
            "confirmedMinutes": int(minutes or 0),
        }
        for teacher_key, teacher_name, count, minutes in rows
        if teacher_key
    }


def workload_stats(user, term_id=None, college_id=None) -> dict:
    """教师工作量聚合：legacy 数字兼容 + current formal-source reconciliation。"""
    from app.models import AaTeachingTask

    with stats.session() as db:
        scope = stats._resolve_scope(user, db)
        stats._validate_college_param(scope, college_id)
        class_ids = stats._class_ids_scope(db, scope, college_id)
        if class_ids is not None and not class_ids:
            return {
                "ranking": [],
                "disclaimer": stats._WORKLOAD_DISCLAIMER,
                "sourcePolicy": "FORMAL_SCHEDULE_AND_CONFIRMED_INVIGILATION",
                "scope": {"blocked": scope.blocked},
            }

        task_query = select(AaTeachingTask).where(*_task_conditions(term_id, class_ids))
        tasks = db.scalars(task_query).all()
        teaching_facts, _task_facts = _formal_teaching_facts(db, tasks)
        invigilation_facts = _formal_invigilation_facts(db, scope, college_id, term_id)
        declared_facts = _declared_facts_by_teacher(db, term_id)

        planned: dict[str, dict] = {}
        for task in tasks:
            key = str(task.teacher_key or "").strip()
            if not key:
                continue
            item = planned.setdefault(key, {
                "teacherName": task.teacher_name or "",
                "totalHours": 0,
                "taskCount": 0,
            })
            if task.teacher_name and not item["teacherName"]:
                item["teacherName"] = task.teacher_name
            item["totalHours"] += int(task.total_hours or 0)
            item["taskCount"] += 1

        ranking = []
        teacher_keys = sorted(set(planned) | set(teaching_facts) | set(invigilation_facts) | set(declared_facts))
        for key in teacher_keys:
            planned_item = planned.get(key) or {}
            teaching = teaching_facts.get(key) or {}
            invigilation = invigilation_facts.get(key) or {}
            declared = declared_facts.get(key) or {}
            teacher_name = (
                planned_item.get("teacherName")
                or invigilation.get("teacherName")
                or declared.get("teacherName")
                or ""
            )
            base_hours = int(planned_item.get("totalHours") or 0)
            declared_hours = round(float(declared.get("approvedHours") or 0), 1)
            issue_count = int(teaching.get("sourceIssueCount") or 0)
            source_status = "CONFLICT" if issue_count else "READY"
            ranking.append({
                "teacherKey": key,
                "teacherName": teacher_name,
                # Legacy/reference fields kept stable for existing consumers.
                "totalHours": base_hours,
                "taskCount": int(planned_item.get("taskCount") or 0),
                "declaredHours": declared_hours,
                "combinedHours": round(base_hours + declared_hours, 1),
                # C-W4 formal-source reconciliation fields.
                "formalTeachingPeriods": int(teaching.get("formalTeachingPeriods") or 0),
                "formalTaskCount": int(teaching.get("formalTaskCount") or 0),
                "confirmedInvigilationCount": int(invigilation.get("confirmedCount") or 0),
                "confirmedInvigilationMinutes": int(invigilation.get("confirmedMinutes") or 0),
                "declaredByCategory": declared.get("byCategory") or {},
                "sourceStatus": source_status,
                "sourceIssueCount": issue_count,
                "sourceIssues": teaching.get("sourceIssues") or [],
            })
        ranking.sort(key=lambda row: (-row["combinedHours"], row["teacherKey"]))
        return {
            "ranking": ranking,
            "disclaimer": stats._WORKLOAD_DISCLAIMER,
            "sourcePolicy": "FORMAL_SCHEDULE_AND_CONFIRMED_INVIGILATION",
            "sourceNote": "正式课表课次与已确认监考仅作来源对账；未冻结学校折算系数前不自动换算绩效课时",
            "scope": {"blocked": scope.blocked},
        }


workload_stats._workload_term_sql_guard = True
workload_stats._workload_formal_source_reconciliation = True


def workload_detail(user, teacher_key, college_id=None, page=1, page_size=20, term_id=None):
    """单教师授课任务明细，同时给出当前正式课次来源状态。"""
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
        _by_teacher, task_facts = _formal_teaching_facts(db, rows)
        items = []
        for task in rows:
            fact = task_facts.get(int(task.id)) or {
                "status": "CONFLICT",
                "formalPeriods": 0,
                "issue": "无法读取当前正式课次投影",
            }
            items.append({
                "taskId": str(task.id),
                "courseName": task.course_name,
                "teachingClassName": task.teaching_class_name,
                "weeklyHours": task.weekly_hours,
                "totalHours": task.total_hours,
                "status": task.status,
                "formalPeriods": int(fact.get("formalPeriods") or 0),
                "sourceStatus": fact.get("status") or "CONFLICT",
                "sourceIssue": fact.get("issue") or "",
            })
        return items, total


workload_detail._workload_term_sql_guard = True
workload_detail._workload_formal_source_reconciliation = True


def public_workload_detail(user, teacher_key, college_id=None, page=1, page_size=20, term_id=None):
    """公开 workload detail：先做范围/本人裁决，再进入 SQL/formal-source guard。"""
    public_stats._precheck(user, college_id)
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role == "ACADEMIC_TEACHER":
        keys = {str(value) for value in (_derive_keys(user) or set()) if str(value).strip()}
        if not keys or str(teacher_key or "") not in keys:
            raise no_data_scope("任课教师仅可查看本人的工作量明细")
    if term_id is None:
        return stats.workload_detail(user, teacher_key, college_id, page, page_size)
    return stats.workload_detail(user, teacher_key, college_id, page, page_size, term_id)


public_workload_detail._workload_public_scope_guard = True


def install() -> None:
    if not hasattr(stats, "_workload_stats_guard_original_stats"):
        stats._workload_stats_guard_original_stats = stats.workload_stats
    if not hasattr(stats, "_workload_stats_guard_original_detail"):
        stats._workload_stats_guard_original_detail = stats.workload_detail
    stats.workload_stats = workload_stats
    stats.workload_detail = workload_detail

    if not hasattr(public_stats, "_workload_stats_guard_original_public_detail"):
        public_stats._workload_stats_guard_original_public_detail = public_stats.workload_detail
    public_stats.workload_detail = public_workload_detail
