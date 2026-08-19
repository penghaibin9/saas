"""C15-13/C15-18 workload reconciliation over formal teacher relations.

The existing workload guard already gives us term-scoped SQL reads, formal
ScopeHead/PUBLISHED/EFFECTIVE schedule evidence, confirmed invigilation evidence and
approved declaration aggregates.  This adapter changes only *who owns the formal
teaching coverage evidence*:

- projected teaching classes use ACTIVE ``AaTeachingClassTeacher`` relations;
- start/end-week windows are intersected with the formal recurrence patterns;
- PRIMARY and CO_TEACHER may both cover the same occurrence.  Coverage is evidence
  of assignment participation, **not payroll hours**, so overlapping teachers are
  not auto-split or de-duplicated across different people;
- multiple overlapping relations for the same teacher are unioned before counting;
- no teaching-class projection => legacy ``AaTeachingTask.teacher_key`` migration
  fallback; a projected class with no formal relation is a source conflict;
- legacy ``totalHours/taskCount/combinedHours`` remain unchanged for compatibility.

No payroll coefficient, HR settlement rule, TeachingClass write, schedule write or
invigilation write is owned here.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, exists, func, or_, select

from app.core.exceptions import AppException

from . import academic_affairs_workload_stats_guard as base

_COVERAGE_MODE = "ASSIGNMENT_COVERAGE_NOT_PAYROLL"
_AUTHORITY_POLICY = "FORMAL_TEACHER_RELATION_SCHEDULE_AND_CONFIRMED_INVIGILATION"


def _task_conditions(term_id, class_ids):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    conditions = [
        AaTeachingTask.tenant_id == base.stats._tid(),
        AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.status != "MERGED",
    ]
    if class_ids is not None:
        conditions.append(AaTeachingTask.class_id.in_(list(class_ids) or [-1]))
    if term_id:
        batch_ids = select(AaTeachingTaskBatch.id).where(
            AaTeachingTaskBatch.tenant_id == base.stats._tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        conditions.append(AaTeachingTask.batch_id.in_(batch_ids))
    return conditions


def _merge_windows(windows) -> list[tuple[int, int]]:
    values = sorted({(int(start), int(end)) for start, end in windows})
    merged: list[list[int]] = []
    for start, end in values:
        if start <= 0 or end <= 0 or end < start:
            raise AppException(
                "DATA_CONFLICT",
                "正式教师关系存在非法有效周次，工作量来源无法对账",
                details={"startWeek": start, "endWeek": end},
                http_status=409,
            )
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _count_pattern_windows(pattern: dict, windows) -> int:
    start = int(pattern.get("startWeek") or 0)
    end = int(pattern.get("endWeek") or 0)
    if start <= 0 or end <= 0 or end < start:
        raise AppException(
            "DATA_CONFLICT",
            "正式课表存在非法教学周范围，工作量来源无法对账",
            details={"scheduleItemId": str(pattern.get("scheduleItemId") or "")},
            http_status=409,
        )
    parity = str(pattern.get("weekParity") or "ALL").upper()
    if parity not in {"ALL", "ODD", "EVEN"}:
        raise AppException(
            "DATA_CONFLICT",
            "正式课表存在未知单双周配置，工作量来源无法对账",
            details={"scheduleItemId": str(pattern.get("scheduleItemId") or ""), "weekParity": parity},
            http_status=409,
        )
    covered = 0
    for week in range(start, end + 1):
        if parity == "ODD" and week % 2 == 0:
            continue
        if parity == "EVEN" and week % 2 == 1:
            continue
        if any(w_start <= week <= w_end for w_start, w_end in windows):
            covered += 1
    return covered


def _relations_for_tasks(db, task_ids):
    from app.models import AaTeachingClass, AaTeachingClassTeacher

    ids = sorted({int(value) for value in task_ids if value})
    if not ids:
        return {}, {}
    classes = db.scalars(select(AaTeachingClass).where(
        AaTeachingClass.tenant_id == base.stats._tid(),
        AaTeachingClass.teaching_task_id.in_(ids),
        AaTeachingClass.is_deleted.is_(False),
    )).all()
    class_by_task = {int(row.teaching_task_id): row for row in classes}
    relations_by_task = defaultdict(list)
    class_ids = sorted({int(row.id) for row in classes})
    if class_ids:
        relations = db.scalars(select(AaTeachingClassTeacher).where(
            AaTeachingClassTeacher.tenant_id == base.stats._tid(),
            AaTeachingClassTeacher.teaching_class_id.in_(class_ids),
            AaTeachingClassTeacher.status == "ACTIVE",
            AaTeachingClassTeacher.is_deleted.is_(False),
        )).all()
        task_by_class = {int(row.id): int(row.teaching_task_id) for row in classes}
        for relation in relations:
            task_id = task_by_class.get(int(relation.teaching_class_id))
            if task_id:
                relations_by_task[task_id].append(relation)
    return class_by_task, relations_by_task


def _relation_windows_by_teacher(relations, teaching_weeks: int | None):
    default_end = int(teaching_weeks or 0) or 9999
    raw = defaultdict(list)
    meta = defaultdict(lambda: {"teacherName": "", "relationIds": [], "roleTypes": set(), "windows": []})
    for relation in relations or []:
        key = str(relation.teacher_key or "").strip()
        if not key:
            continue
        start = int(relation.start_week) if relation.start_week is not None else 1
        end = int(relation.end_week) if relation.end_week is not None else default_end
        raw[key].append((start, end))
        item = meta[key]
        if relation.teacher_name and not item["teacherName"]:
            item["teacherName"] = relation.teacher_name
        item["relationIds"].append(str(relation.id))
        item["roleTypes"].add(str(relation.role_type or "PRIMARY").upper())
        item["windows"].append({"startWeek": start, "endWeek": end})
    result = {}
    for key, windows in raw.items():
        result[key] = {
            **meta[key],
            "mergedWindows": _merge_windows(windows),
            "roleTypes": sorted(meta[key]["roleTypes"]),
        }
    return result


def _add_issue(by_teacher: dict, key: str, name: str, *, task, message: str, status="CONFLICT") -> None:
    if not key:
        return
    item = by_teacher.setdefault(key, {
        "teacherName": name or "",
        "formalTeachingPeriods": 0,
        "formalTaskCount": 0,
        "sourceIssueCount": 0,
        "sourceIssues": [],
        "authoritySources": set(),
        "relationIds": set(),
    })
    if name and not item["teacherName"]:
        item["teacherName"] = name
    item["sourceIssueCount"] += 1
    if len(item["sourceIssues"]) < 20:
        item["sourceIssues"].append({
            "taskId": str(task.id),
            "courseName": task.course_name or "",
            "status": status,
            "message": message,
        })


def relation_formal_teaching_facts(db, tasks) -> tuple[dict[str, dict], dict[int, dict]]:
    """Formal schedule coverage attributed through TeachingClassTeacher relation windows."""
    from app.models import AaTeachingTaskBatch, AaTerm
    from . import academic_affairs_attendance_occurrence_consumer as occurrence

    task_list = list(tasks or [])
    if not task_list:
        return {}, {}
    class_by_task, relations_by_task = _relations_for_tasks(db, [task.id for task in task_list])
    batch_ids = sorted({int(task.batch_id) for task in task_list if task.batch_id})
    batches = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == base.stats._tid(),
        AaTeachingTaskBatch.id.in_(batch_ids or [-1]),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()
    batch_by_id = {int(row.id): row for row in batches}
    term_ids = sorted({int(row.term_id) for row in batches if row.term_id})
    terms = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == base.stats._tid(),
        AaTerm.id.in_(term_ids or [-1]),
        AaTerm.is_deleted.is_(False),
    )).all()
    term_by_id = {int(row.id): row for row in terms}

    grouped = defaultdict(list)
    by_teacher: dict[str, dict] = {}
    by_task: dict[int, dict] = {}
    for task in task_list:
        batch = batch_by_id.get(int(task.batch_id or 0))
        if not batch or not batch.term_id:
            fallback_key = str(task.teacher_key or "").strip()
            _add_issue(
                by_teacher, fallback_key, task.teacher_name or "",
                task=task, message="教学任务缺少有效学期批次，无法回链正式课表",
            )
            by_task[int(task.id)] = {
                "status": "CONFLICT", "formalPeriods": 0,
                "issue": "教学任务缺少有效学期批次，无法回链正式课表",
                "authoritySource": "UNKNOWN", "teacherCoverage": {},
            }
            continue
        grouped[int(batch.term_id)].append((task, batch))

    for term_id, bindings in grouped.items():
        term = term_by_id.get(term_id)
        if not term:
            for task, _batch in bindings:
                fallback_key = str(task.teacher_key or "").strip()
                _add_issue(
                    by_teacher, fallback_key, task.teacher_name or "",
                    task=task, message="教学任务学期不存在或已删除，无法回链正式课表",
                )
                by_task[int(task.id)] = {
                    "status": "CONFLICT", "formalPeriods": 0,
                    "issue": "教学任务学期不存在或已删除，无法回链正式课表",
                    "authoritySource": "UNKNOWN", "teacherCoverage": {},
                }
            continue

        projections = occurrence.formal_schedule_patterns_for_tasks(db, bindings, term)
        teaching_weeks = int(term.teaching_weeks or 0) or None
        for task, _batch in bindings:
            task_id = int(task.id)
            projection = projections.get(task_id) or {
                "status": "CONFLICT", "issue": "无法读取当前正式课次投影", "patterns": [],
            }
            status = str(projection.get("status") or "CONFLICT").upper()
            teaching_class = class_by_task.get(task_id)
            relations = relations_by_task.get(task_id, [])
            coverage = {}

            if teaching_class is not None:
                authority_source = "TEACHING_CLASS_TEACHER"
                if not relations:
                    by_task[task_id] = {
                        "status": "CONFLICT", "formalPeriods": 0,
                        "issue": "正式教学班没有 ACTIVE 教师关系，工作量来源不可归属",
                        "authoritySource": authority_source, "teacherCoverage": {},
                        "teachingClassId": str(teaching_class.id),
                    }
                    continue
                relation_meta = _relation_windows_by_teacher(relations, teaching_weeks)
            else:
                authority_source = "TEACHING_TASK_MIGRATION_FALLBACK"
                key = str(task.teacher_key or "").strip()
                if not key:
                    by_task[task_id] = {
                        "status": "CONFLICT", "formalPeriods": 0,
                        "issue": "未投影教学班且教学任务缺少教师工号，工作量来源不可归属",
                        "authoritySource": authority_source, "teacherCoverage": {},
                    }
                    continue
                relation_meta = {
                    key: {
                        "teacherName": task.teacher_name or "",
                        "relationIds": [],
                        "roleTypes": ["MIGRATION_FALLBACK"],
                        "windows": [{"startWeek": 1, "endWeek": int(teaching_weeks or 9999)}],
                        "mergedWindows": [(1, int(teaching_weeks or 9999))],
                    }
                }

            if status != "READY":
                message = projection.get("issue") or "当前教学任务没有可消费的正式课次"
                for key, meta in relation_meta.items():
                    _add_issue(by_teacher, key, meta.get("teacherName") or "", task=task, message=message, status=status)
                    teacher_item = by_teacher[key]
                    teacher_item["authoritySources"].add(authority_source)
                    teacher_item["relationIds"].update(meta.get("relationIds") or [])
                by_task[task_id] = {
                    "status": status, "formalPeriods": 0, "issue": message,
                    "authoritySource": authority_source, "teacherCoverage": {},
                    "teachingClassId": str(teaching_class.id) if teaching_class else None,
                }
                continue

            patterns = projection.get("patterns") or []
            for key, meta in relation_meta.items():
                periods = sum(
                    _count_pattern_windows(pattern, meta["mergedWindows"])
                    for pattern in patterns
                )
                coverage[key] = {
                    "teacherName": meta.get("teacherName") or "",
                    "formalPeriods": int(periods),
                    "relationIds": list(meta.get("relationIds") or []),
                    "roleTypes": list(meta.get("roleTypes") or []),
                    "windows": list(meta.get("windows") or []),
                }
                teacher_item = by_teacher.setdefault(key, {
                    "teacherName": meta.get("teacherName") or "",
                    "formalTeachingPeriods": 0,
                    "formalTaskCount": 0,
                    "sourceIssueCount": 0,
                    "sourceIssues": [],
                    "authoritySources": set(),
                    "relationIds": set(),
                })
                if meta.get("teacherName") and not teacher_item["teacherName"]:
                    teacher_item["teacherName"] = meta["teacherName"]
                teacher_item["authoritySources"].add(authority_source)
                teacher_item["relationIds"].update(meta.get("relationIds") or [])
                if periods > 0:
                    teacher_item["formalTeachingPeriods"] += int(periods)
                    teacher_item["formalTaskCount"] += 1

            by_task[task_id] = {
                "status": "READY",
                "formalPeriods": int(sum(base._pattern_period_count(row) for row in patterns)),
                "issue": "",
                "authoritySource": authority_source,
                "teacherCoverage": coverage,
                "teachingClassId": str(teaching_class.id) if teaching_class else None,
            }

    for item in by_teacher.values():
        item["authoritySources"] = sorted(item["authoritySources"])
        item["relationIds"] = sorted(item["relationIds"])
    return by_teacher, by_task


def workload_stats(user, term_id=None, college_id=None) -> dict:
    """Keep legacy workload numbers but replace formal teaching evidence attribution."""
    result = base.workload_stats(user, term_id, college_id)
    with base.stats.session() as db:
        scope = base.stats._resolve_scope(user, db)
        base.stats._validate_college_param(scope, college_id)
        class_ids = base.stats._class_ids_scope(db, scope, college_id)
        if class_ids is not None and not class_ids:
            result["sourcePolicy"] = _AUTHORITY_POLICY
            result["formalCoverageMode"] = _COVERAGE_MODE
            return result
        from app.models import AaTeachingTask

        tasks = db.scalars(select(AaTeachingTask).where(*_task_conditions(term_id, class_ids))).all()
        teaching_facts, _task_facts = relation_formal_teaching_facts(db, tasks)

    rows_by_key = {str(row.get("teacherKey") or ""): row for row in result.get("ranking") or [] if row.get("teacherKey")}
    for key, fact in teaching_facts.items():
        if key not in rows_by_key:
            rows_by_key[key] = {
                "teacherKey": key,
                "teacherName": fact.get("teacherName") or "",
                "totalHours": 0,
                "taskCount": 0,
                "declaredHours": 0.0,
                "combinedHours": 0.0,
                "confirmedInvigilationCount": 0,
                "confirmedInvigilationMinutes": 0,
                "declaredByCategory": {},
            }

    for key, row in rows_by_key.items():
        fact = teaching_facts.get(key) or {}
        if fact.get("teacherName") and not row.get("teacherName"):
            row["teacherName"] = fact["teacherName"]
        row["formalTeachingPeriods"] = int(fact.get("formalTeachingPeriods") or 0)
        row["formalTaskCount"] = int(fact.get("formalTaskCount") or 0)
        row["sourceIssueCount"] = int(fact.get("sourceIssueCount") or 0)
        row["sourceIssues"] = fact.get("sourceIssues") or []
        row["sourceStatus"] = "CONFLICT" if row["sourceIssueCount"] else "READY"
        row["formalTeacherAuthoritySources"] = fact.get("authoritySources") or []
        row["teacherRelationIds"] = fact.get("relationIds") or []
        row["formalCoverageMode"] = _COVERAGE_MODE

    ranking = list(rows_by_key.values())
    ranking.sort(key=lambda row: (-float(row.get("combinedHours") or 0), str(row.get("teacherKey") or "")))
    result["ranking"] = ranking
    result["sourcePolicy"] = _AUTHORITY_POLICY
    result["formalCoverageMode"] = _COVERAGE_MODE
    result["sourceNote"] = (
        "正式授课课次按 TeachingClassTeacher 有效周次归属；PRIMARY/CO_TEACHER 重叠表示共同覆盖，"
        "仅作来源对账，不自动拆分或叠加为薪酬工时。已确认监考同样只作事实证据，学校折算系数未冻结前不换算绩效。"
    )
    return result


workload_stats._workload_teacher_relation_guard = True


def _detail_query(db, teacher_key: str, class_ids, term_id=None):
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch

    relation_task_ids = select(AaTeachingClass.teaching_task_id).join(
        AaTeachingClassTeacher,
        and_(
            AaTeachingClassTeacher.teaching_class_id == AaTeachingClass.id,
            AaTeachingClassTeacher.tenant_id == AaTeachingClass.tenant_id,
        ),
    ).where(
        AaTeachingClass.tenant_id == base.stats._tid(),
        AaTeachingClass.is_deleted.is_(False),
        AaTeachingClassTeacher.tenant_id == base.stats._tid(),
        AaTeachingClassTeacher.teacher_key == str(teacher_key),
        AaTeachingClassTeacher.status == "ACTIVE",
        AaTeachingClassTeacher.is_deleted.is_(False),
    )
    if term_id:
        relation_task_ids = relation_task_ids.where(AaTeachingClass.term_id == int(term_id))

    projected_exists = exists(select(AaTeachingClass.id).where(
        AaTeachingClass.tenant_id == base.stats._tid(),
        AaTeachingClass.teaching_task_id == AaTeachingTask.id,
        AaTeachingClass.is_deleted.is_(False),
    ))
    conditions = [
        AaTeachingTask.tenant_id == base.stats._tid(),
        AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.status != "MERGED",
        or_(
            AaTeachingTask.id.in_(relation_task_ids),
            and_(~projected_exists, AaTeachingTask.teacher_key == str(teacher_key)),
        ),
    ]
    if class_ids is not None:
        conditions.append(AaTeachingTask.class_id.in_(list(class_ids) or [-1]))
    if term_id:
        batch_ids = select(AaTeachingTaskBatch.id).where(
            AaTeachingTaskBatch.tenant_id == base.stats._tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        conditions.append(AaTeachingTask.batch_id.in_(batch_ids))
    return select(AaTeachingTask).where(*conditions)


def workload_detail(user, teacher_key, college_id=None, page=1, page_size=20, term_id=None):
    """Teacher detail includes co-teaching/week-split task coverage, SQL-paged."""
    key = str(teacher_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "teacherKey 必填")
    page_no, size = base._page_values(page, page_size)
    with base.stats.session() as db:
        scope = base.stats._resolve_scope(user, db)
        base.stats._validate_college_param(scope, college_id)
        class_ids = base.stats._class_ids_scope(db, scope, college_id)
        if class_ids is not None and not class_ids:
            return [], 0
        q = _detail_query(db, key, class_ids, term_id)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        tasks = db.scalars(
            q.order_by(q.selected_columns.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        _by_teacher, task_facts = relation_formal_teaching_facts(db, tasks)
        items = []
        for task in tasks:
            fact = task_facts.get(int(task.id)) or {
                "status": "CONFLICT", "issue": "无法读取当前正式课次投影",
                "authoritySource": "UNKNOWN", "teacherCoverage": {},
            }
            coverage = (fact.get("teacherCoverage") or {}).get(key) or {}
            items.append({
                "taskId": str(task.id),
                "courseName": task.course_name,
                "teachingClassName": task.teaching_class_name,
                "weeklyHours": task.weekly_hours,
                # Legacy planned value kept as a reference only; do not split it here.
                "totalHours": task.total_hours,
                "status": task.status,
                "formalPeriods": int(coverage.get("formalPeriods") or 0),
                "sourceStatus": fact.get("status") or "CONFLICT",
                "sourceIssue": fact.get("issue") or "",
                "teacherAuthoritySource": fact.get("authoritySource") or "UNKNOWN",
                "teachingClassId": fact.get("teachingClassId"),
                "teacherRelationIds": coverage.get("relationIds") or [],
                "teacherRoleTypes": coverage.get("roleTypes") or [],
                "teacherRelationWindows": coverage.get("windows") or [],
                "formalCoverageMode": _COVERAGE_MODE,
            })
        return items, total


workload_detail._workload_teacher_relation_guard = True


def install() -> None:
    """Patch the legacy stats module dynamically consumed by the public wrapper/router."""
    stats = base.stats
    if not hasattr(stats, "_workload_teacher_relation_original_stats"):
        stats._workload_teacher_relation_original_stats = stats.workload_stats
    if not hasattr(stats, "_workload_teacher_relation_original_detail"):
        stats._workload_teacher_relation_original_detail = stats.workload_detail
    stats.workload_stats = workload_stats
    stats.workload_detail = workload_detail
