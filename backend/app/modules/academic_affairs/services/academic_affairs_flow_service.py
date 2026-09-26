"""V5 学期责任接力只读投影；业务状态仍由各领域命令与模型维护。"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from types import SimpleNamespace

from sqlalchemy import func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.permissions import _match
from app.services.db_service import _tid, session

from . import academic_affairs_dashboard_readiness_service as readiness
from . import academic_affairs_responsibility_service as responsibility


STAGES = (
    ("F10_TERM_SETUP", "学期基础", "terms", "term.view"),
    ("F20_REGISTRATION", "注册学籍", "registration", "registration.view"),
    ("F30_PROGRAM_COURSE", "培养方案与课程", "programs", "program.view"),
    ("F40_TEACHING_TASK", "教学任务落实", "teaching-tasks", "teachingTask.view"),
    ("F50_SCHEDULE", "排课与课表", "scheduling", "schedule.view"),
    ("F60_SELECTION", "选课与名单", "selection", "selection.view"),
    ("F70_TEACHING_OPERATION", "日常教学运行", "attendance-stats", "attendance.view"),
    ("F80_EXAM", "考务组织", "exam", "exam.view"),
    ("F90_GRADE", "成绩闭环", "grade-overview", "grade.view"),
    ("F100_GRADUATION", "学业与毕业", "graduation/audit-console", "graduation.view"),
    ("F110_QUALITY", "质量与统计", "stats", "stats.view"),
    ("F120_ARCHIVE", "学期归档", "archive", "archive.view"),
)
FLOW_STATUSES = {"NOT_STARTED", "ACTION_REQUIRED", "BLOCKED", "READY", "DONE", "NOT_APPLICABLE"}
_COMPLETE = {"READY", "DONE", "NOT_APPLICABLE"}
_BASE = "/admin/academic-affairs/"
_SCHOOL_PERMISSIONS = {
    0: "term.manage", 2: "program.review", 3: "teachingTask.confirm", 4: "schedule.edit",
    5: "selection.manage", 7: "exam.publish", 8: "grade.publish", 9: "graduation.final",
    10: "evaluation.batch.manage", 11: "archive.manage",
}


def _school_resolver(db, cache):
    def resolve(permission):
        key = ("SCHOOL", permission)
        if key not in cache:
            cache[key] = responsibility.resolve_school(db, permission_code="academicAffairs." + permission, cache=cache)
        return cache[key]
    return resolve


def _program_responsibility(db, program, *, college_id=None, cache=None):
    return responsibility.resolve_program(db, program, college_id=college_id, cache=cache)


def _relation_self_actor(db, user, ctx, *, source, permission):
    """仅由已经核验归属本人的正式课次/监考关系调用，不把普通查看者当办理人。"""
    from app.models import User
    from .academic_affairs_teacher_today_work_service import _resolve_user_id
    uid = _resolve_user_id(db, user)
    person = _query(db, User, User.id == uid, User.status == "ACTIVE").first() if uid else None
    people = [person] if person and _match(permission, ctx.permission_codes) else []
    return responsibility._payload("USER", uid, "任课教师", ("TEACHER",), people,
        source=source if people else "UNRESOLVED", role_codes=("ACADEMIC_TEACHER",),
        reason="" if people else "正式任务对应教师账号或当前办理权限已失效")


def _problem(code, message, route=None):
    return {"code": code, "message": message, **({"route": route} if route else {})}


def _counts_state(counts, *, done=(), ready=(), known=()):
    """空记录不等于完成；未知业务枚举不得推定通过。"""
    total = sum(counts.values())
    if not total:
        return "NOT_STARTED"
    if set(counts) - set(done) - set(ready) - set(known):
        return "BLOCKED"
    if sum(counts.get(key, 0) for key in done) == total:
        return "DONE"
    if sum(counts.get(key, 0) for key in (*done, *ready)) == total:
        return "READY"
    return "ACTION_REQUIRED"


def _aggregate_status(stages):
    states = [row["status"] for row in stages]
    if not states:
        return "NOT_STARTED"
    for state in ("BLOCKED", "ACTION_REQUIRED", "NOT_STARTED"):
        if state in states:
            return state
    if all(state == "NOT_APPLICABLE" for state in states):
        return "NOT_APPLICABLE"
    return "DONE" if all(state in {"DONE", "NOT_APPLICABLE"} for state in states) else "READY"


def _grade_status(counts, *, teacher=False):
    from .academic_affairs_grade_service import _EDITABLE
    review = ("SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW")
    return _counts_state(counts, done=("PUBLISHED", "ARCHIVED"),
                         ready=review if teacher else (), known=(*_EDITABLE, *review))


def _current(stages):
    applicable = [row for row in stages if row["status"] != "NOT_APPLICABLE"]
    return next((row for row in applicable if row["status"] not in _COMPLETE), applicable[-1] if applicable else None)


def _term_date(value):
    # AaTerm 使用 DateTime 列；日历、监考接口消费日期，不能把含时分秒的值当日期字符串。
    return value.date() if isinstance(value, datetime) else value if isinstance(value, date) else None


def _gate(stage_code, label, units, *, complete_scope, extra_blockers=()):
    rows = [next(row for row in unit["stages"] if row["stageCode"] == stage_code) for unit in units]
    ready = sum(row["status"] in _COMPLETE for row in rows)
    blocked = sum(row["status"] == "BLOCKED" for row in rows)
    blockers = list(extra_blockers)
    if not complete_scope:
        blockers.append(_problem("SCHOOL_GATE_SCOPE_INCOMPLETE", "当前范围不足以核验全校发布门禁"))
    if not rows or ready != len(rows):
        blockers.append(_problem("COLLEGE_NOT_READY", f"教学单位已就绪 {ready}/{len(rows)}，请先处理未完成单位"))
    return {"stageCode": stage_code, "label": label, "required": True,
            "ready": bool(rows) and ready == len(rows) and not blockers,
            "readyUnitCount": ready, "blockedUnitCount": blocked,
            "totalUnitCount": len(rows), "blockers": blockers}


def _stage(index, term, *, status="NOT_STARTED", responsible=None, blockers=(), evidence=None,
           current_object=None, ctx=None, college_id=None):
    code, label, path, permission = STAGES[index]
    route = _BASE + path
    params = []
    if term:
        params.append(f"termId={term.id}")
    if college_id:
        params.append(f"collegeId={college_id}")
    if params:
        route += "?" + "&".join(params)
    issues = list(blockers)
    if responsible and not responsible["resolved"] and status not in {"DONE", "NOT_APPLICABLE", "NOT_STARTED"}:
        issues.append(_problem(responsible.get("blockerCode") or "RESPONSIBILITY_UNRESOLVED",
                               responsible["reason"], "/admin/system/staff-affiliations"))
        status = "BLOCKED"
    if status == "BLOCKED" and not issues:
        issues.append(_problem("FLOW_EVIDENCE_UNRESOLVED", "当前业务状态或完成证据无法确认，请进入原工作区核对", route))
    can_view = ctx is not None and _match("academicAffairs." + permission, ctx.permission_codes)
    next_step = {"code": STAGES[index + 1][0], "label": STAGES[index + 1][1]} if index < len(STAGES) - 1 else None
    return {"stageCode": code, "label": label, "status": status,
            "termId": str(term.id) if term else None, "responsibility": responsible,
            "blockers": issues, "risks": [],
            "primaryAction": {"label": f"查看{label}", "route": route} if can_view else None,
            "nextStep": next_step, "currentObject": current_object, "evidence": evidence or {}}


def _query(db, model, *conditions):
    return db.query(model).filter(model.tenant_id == _tid(), model.is_deleted.is_(False), *conditions)


def _counts(query, model):
    return {str(state or "UNKNOWN"): int(count) for state, count in
            query.with_entities(model.status, func.count()).group_by(model.status).all()}


def _semantic(row):
    result = str(row.get("result") or ("PASS" if row.get("present") else "UNKNOWN"))
    if result == "PASS":
        return "DONE", []
    if result == "NOT_APPLICABLE":
        return "NOT_APPLICABLE", []
    return "BLOCKED", [_problem(row.get("ruleCode") or "FLOW_EVIDENCE_UNRESOLVED",
                                row.get("summary") or row.get("remark") or "当前业务证据不足，不能判定完成",
                                row.get("route"))]


def _task_projection(db, term, college_id, *, task_ids=None, cache=None):
    from app.models import AaTeachingClass, AaTeachingTask as Task, AaTeachingTaskBatch as Batch
    from .academic_affairs_task_service import _summary_counts

    batch_query = _query(db, Batch, Batch.term_id == term.id)
    if college_id:
        batch_query = batch_query.filter(Batch.college_id == college_id)
    batch_ids = batch_query.with_entities(Batch.id).subquery()
    tasks = _query(db, Task, Task.batch_id.in_(select(batch_ids.c.id)), Task.status != "MERGED")
    if task_ids is not None:
        tasks = tasks.filter(Task.id.in_(task_ids or {-1}))
    counts = _counts(tasks, Task)
    missing = tasks.filter(func.trim(func.coalesce(Task.teacher_key, "")) == "").count() if task_ids is None else 0
    summary = _summary_counts(counts, missing)
    blockers = [_problem(row["code"], row["message"], row["route"]) for row in summary["blockers"]]
    batch_counts = _counts(batch_query, Batch)
    state = _counts_state(counts, ready=("READY", "TEACHER_CONFIRMED"),
                          known=("PENDING_ASSIGN", "ASSIGNED", "REJECTED_BY_TEACHER"))
    if blockers:
        state = "BLOCKED" if counts.get("PENDING_ASSIGN") or counts.get("REJECTED_BY_TEACHER") or missing else "ACTION_REQUIRED"
    if task_ids is None and summary["taskTotal"]:
        projected = tasks.join(AaTeachingClass, (AaTeachingClass.teaching_task_id == Task.id)
                               & (AaTeachingClass.tenant_id == _tid())
                               & AaTeachingClass.is_deleted.is_(False)
                               & (AaTeachingClass.status == "ACTIVE")).count()
        summary["teachingClassCount"] = projected
        if projected != summary["taskTotal"]:
            blockers.append(_problem("TEACHING_CLASS_UNRESOLVED", "教学任务尚未完整形成正式教学班"))
            state = "BLOCKED"
        if state == "READY" and any(key not in {"APPROVED", "ARCHIVED"} for key in batch_counts):
            state = "ACTION_REQUIRED"
        if state == "READY" and set(counts) != {"READY"}:
            state = "ACTION_REQUIRED"
        if state == "READY":
            from .academic_affairs_archive_rule_evaluator import evaluate_teaching_task
            reconciliation = evaluate_teaching_task(db, term.id, college_ids={college_id} if college_id else None, cache=cache)
            summary["openingReconciliation"] = {"result": reconciliation["result"],
                                                 "summary": reconciliation["summary"]}
            if reconciliation["result"] != "PASS":
                blockers.append(_problem(reconciliation["ruleCode"], reconciliation["summary"]))
                state = "BLOCKED"
    task = tasks.order_by(Task.id).first()
    batch = batch_query.order_by(Batch.id.desc()).first()
    summary["batchByStatus"] = batch_counts
    return state, blockers, summary, task, batch


def _task_stage_responsibility(summary, org, school):
    batches = set(summary.get("batchByStatus", {}))
    if batches and batches <= {"COLLEGE_CONFIRMED", "APPROVED", "ARCHIVED"}:
        return school("teachingTask.confirm")
    permission = "academicAffairs.teachingTask.confirm" if summary.get("canAdvance") else "academicAffairs.teachingTask.manage"
    return org(permission)


def _schedule_task_ids(db, term, batch, college_id, cache):
    """与正式排课候选使用同一责任策略；共享批次再交集本院开课范围。"""
    from app.models import AaTeachingTask as Task, AaTeachingTaskBatch as TaskBatch
    from . import academic_affairs_schedule_policy as policy
    key = ("SCHEDULE_TASK_IDS", _tid(), int(term.id), batch.college_id, college_id)
    if key not in cache:
        conditions = [policy.task_scope_condition(db, batch)]
        if college_id and not batch.college_id:
            conditions.append(policy.task_scope_condition(db, SimpleNamespace(college_id=college_id),
                                                           include_centralized_public=True))
        cache[key] = set(db.scalars(select(Task.id).join(TaskBatch, TaskBatch.id == Task.batch_id).where(
            Task.tenant_id == _tid(), Task.is_deleted.is_(False), Task.status == "READY",
            Task.no_auto_schedule.is_(False), TaskBatch.tenant_id == _tid(),
            TaskBatch.term_id == term.id, TaskBatch.status == "APPROVED",
            TaskBatch.is_deleted.is_(False), *conditions)).all())
    return cache[key]


def _schedule_batch_projection(db, term, batch, college_id, cache):
    from app.models import AaCourse, AaScheduleItem, AaScheduleScopeHead
    from . import academic_affairs_schedule_gate_service as gate
    from . import academic_affairs_schedule_truth_service as truth
    key = ("SCHEDULE_GATE", int(batch.id))
    if key not in cache:
        cache[key] = gate.evaluate(db, batch)
    check = dict(cache[key])
    cross_key = ("SCHEDULE_CROSS", int(batch.id))
    if cross_key not in cache:
        cache[cross_key] = len(truth.validate_school_wide_conflicts(db, batch, lock=False)["problems"])
    cross_count = cache[cross_key]
    if college_id and not batch.college_id:
        task_ids = _schedule_task_ids(db, term, batch, college_id, cache)
        own_items = _query(db, AaScheduleItem, AaScheduleItem.batch_id == batch.id,
                           AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.task_id.in_(task_ids or {-1})).all()
        item_ids = {str(row.id) for row in own_items}
        for field in ("invalidTasks", "missingTasks", "overScheduledTasks"):
            check[field] = [row for row in check[field] if int(row["taskId"]) in task_ids]
        missing_owner = task_ids.intersection(int(value) for value in check.get("missingOwnerTaskIds", []))
        hard = [row for row in check["hardConflictItems"]
                if row["itemA"]["id"] in item_ids or row["itemB"]["id"] in item_ids]
        invalid_items = any(item_ids.intersection(check[field]) for field in (
            "orphanItemIds", "invalidCoordinateItemIds", "invalidClassroomItemIds"))
        check.update(totalTasks=len(task_ids), scheduledTasks=len({row.task_id for row in own_items}),
                     missingTaskCount=len(check["missingTasks"]), hardConflicts=len(hard))
        check["complete"] = bool(task_ids) and not any((missing_owner, check["invalidTasks"], check["missingTasks"],
            check["overScheduledTasks"], hard, invalid_items)) and check["scheduledTasks"] == len(task_ids)
        # 全校批次分院进度只核本院课程；其它学院的缺课不能回退本院。
        from .academic_affairs_schedule_conflict_index import iter_same_slot_pairs
        other_items = truth._items(db, truth._live_batch_ids(db, term.id, batch.id, lock=False))
        own_ids = {int(row.id) for row in own_items}
        conflicts = []
        for left, right in iter_same_slot_pairs([*own_items, *other_items]):
            if (int(left.id) in own_ids) == (int(right.id) in own_ids) or not truth._weeks_overlap(left, right):
                continue
            left_resources = {(kind, resource) for kind, resource, _label in truth._resources(left)}
            right_resources = {(kind, resource) for kind, resource, _label in truth._resources(right)}
            if left_resources & right_resources:
                conflicts.append(True)
        cross_count = len(conflicts)
    blockers = []
    if not check["complete"]:
        blockers.append(_problem("SCHEDULE_NOT_READY", "课表仍有漏排、资源或硬冲突问题，请进入排课工作区处理"))
    if cross_count:
        blockers.append(_problem("CROSS_COLLEGE_CONFLICT", f"存在 {cross_count} 项跨教学单位资源冲突，请校教务协调"))
    owner_missing = _query(db, AaScheduleItem, AaScheduleItem.batch_id == batch.id,
                          AaScheduleItem.status == "EFFECTIVE").outerjoin(AaCourse,
        (AaCourse.id == AaScheduleItem.course_id) & (AaCourse.tenant_id == _tid())
        & AaCourse.is_deleted.is_(False)).filter(AaCourse.owner_college_id.is_(None)).count()
    if owner_missing and batch.college_id:
        blockers.append(_problem("OFFERING_UNIT_UNRESOLVED", f"{owner_missing} 条课程未配置开课单位，不能判定排课责任已落实"))
    state = "BLOCKED" if blockers else "READY"
    if batch.status == "PUBLISHED" and not blockers:
        official = db.scalar(select(AaScheduleScopeHead.id).where(
            AaScheduleScopeHead.tenant_id == _tid(), AaScheduleScopeHead.term_id == term.id,
            AaScheduleScopeHead.active_batch_id == batch.id, AaScheduleScopeHead.is_deleted.is_(False),
        ).limit(1))
        state = "DONE" if official else "BLOCKED"
        if not official:
            blockers.append(_problem("SCHEDULE_FORMAL_HEAD_UNRESOLVED", "课表缺少当前正式版本依据，不能判定已完成发布"))
    evidence = {key: check[key] for key in ("totalTasks", "scheduledTasks", "missingTaskCount", "hardConflicts")}
    evidence["crossCollegeConflictCount"] = cross_count
    evidence["responsibleOrgType"] = "COLLEGE" if batch.college_id else "SCHOOL"
    return state, blockers, evidence, batch


def _merge_schedule_projections(parts, mode):
    """公共课与专业课都需有真实完成依据，任一未完成均不能被另一集合遮住。"""
    status = _aggregate_status([{"status": part[0]} for part in parts])
    applicable = [part for part in parts if part[0] != "NOT_APPLICABLE"] or parts
    chosen = next((part for part in applicable if part[0] not in _COMPLETE),
                  next((part for part in applicable if part[0] == "READY"), applicable[0]))
    evidence = {"publicScheduleMode": mode, "responsibleOrgType": chosen[2].get("responsibleOrgType"),
        "components": [{"status": part[0], "batchId": str(part[3].id) if part[3] else None, **part[2]} for part in parts]}
    for key in ("totalTasks", "scheduledTasks", "missingTaskCount", "hardConflicts", "crossCollegeConflictCount"):
        evidence[key] = sum(part[2].get(key, 0) for part in parts)
    return status, [row for part in parts for row in part[1]], evidence, chosen[3]


def _empty_schedule_check(check):
    return not any(check.get(key) for key in ("totalTasks", "scheduledTasks", "missingOwnerTaskIds",
        "invalidTasks", "missingTasks", "overScheduledTasks", "hardConflicts", "orphanItemIds",
        "invalidCoordinateItemIds", "invalidClassroomItemIds"))


def _schedule_projection(db, term, college_id, cache):
    from app.models import AaScheduleBatch as Batch
    from . import academic_affairs_schedule_policy as policy
    mode_key = ("PUBLIC_SCHEDULE_MODE", _tid())
    if mode_key not in cache:
        cache[mode_key] = policy.public_schedule_mode(db)
    mode = cache[mode_key]
    query = _query(db, Batch, Batch.term_id == term.id,
                   Batch.status.in_(("DRAFT", "PRE_PUBLISHED", "PUBLISHED")))
    if college_id:
        query = query.filter(or_(Batch.college_id == college_id, Batch.college_id.is_(None)))
    else:
        query = query.filter(Batch.college_id.is_(None))
    batches = query.order_by(Batch.id.desc()).all()
    own = [row for row in batches if row.college_id == college_id] if college_id else []
    school = [row for row in batches if not row.college_id]
    # 统排模式按两套正式责任集合核验。其它模式延续学院批次优先、学校批次承接的现行规则。
    groups = ([(college_id, own), (None, school)] if college_id and mode == "SCHOOL_CENTRALIZED"
              else [(college_id if own else None, own or school)])
    parts = []
    for owner, candidates in groups:
        reference = SimpleNamespace(college_id=owner)
        needed = _schedule_task_ids(db, term, reference, college_id, cache) if mode == "SCHOOL_CENTRALIZED" else None
        if needed is not None and not needed:
            # 无应排任务时仍核验已有条目是否违反现行责任模式，不能把历史误排静默算完成。
            if not candidates or college_id and owner is None:
                parts.append(("NOT_APPLICABLE", [], {"totalTasks": 0}, None))
                continue
        if not candidates:
            if needed:
                parts.append(("BLOCKED", [_problem("SCHEDULE_BATCH_MISSING", "学校公共课尚未建立统排批次" if owner is None else "本院专业课尚未建立排课批次")],
                              {"totalTasks": len(needed), "missingTaskCount": len(needed), "responsibleOrgType": "SCHOOL" if owner is None else "COLLEGE"}, None))
            else:
                parts.append(("NOT_APPLICABLE" if college_id is None else "NOT_STARTED", [], {}, None))
            continue
        batch = next((row for row in candidates if row.status != "PUBLISHED"), candidates[0])
        part = _schedule_batch_projection(db, term, batch, college_id, cache)
        if needed is not None and not needed and _empty_schedule_check(cache[("SCHEDULE_GATE", int(batch.id))]):
            part = ("NOT_APPLICABLE", [], {"totalTasks": 0}, None)
        parts.append(part)
    return _merge_schedule_projections(parts, mode)


def _student_unit_progress(db, term, college_id, student_ids, task_ids):
    from app.models import (
        AaEvaluationAppeal, AaEvaluationBatch, AaEvaluationResult, AaEvaluationTask,
        AaGraduationAuditBatch, AaGraduationAuditResult, AaSelectionBatch, AaSelectionRecord,
    )

    selection = _query(db, AaSelectionRecord, AaSelectionRecord.student_id.in_(student_ids)).join(
        AaSelectionBatch, (AaSelectionBatch.id == AaSelectionRecord.batch_id)
        & (AaSelectionBatch.tenant_id == _tid()) & AaSelectionBatch.is_deleted.is_(False)
    ).filter(AaSelectionBatch.term_id == term.id)
    selection_counts = _counts(selection, AaSelectionRecord)
    selection_state = _counts_state(selection_counts, done=("LOCKED", "DROPPED", "COURSE_CANCELLED"),
                                     known=("SELECTED", "PENDING_LOTTERY"))
    if not _query(db, AaSelectionBatch, AaSelectionBatch.term_id == term.id).count():
        selection_state = "NOT_APPLICABLE"
    result = {5: (selection_state, [], {
        "byStatus": selection_counts,
        "scopeNote": "仅统计本院学生选课记录，学院协同核对本院异常；批次开放、关闭和名单锁定由校教务办理",
    })}

    if not term.start_date or not term.end_date:
        result[9] = ("BLOCKED", [_problem("GRADUATION_TERM_SCOPE_UNKNOWN", "学期起止日期不完整，无法核验本院毕业结果")], {})
    else:
        start = datetime.combine(term.start_date, time.min)
        end = datetime.combine(term.end_date, time.max)
        batches = _query(db, AaGraduationAuditBatch,
            func.coalesce(AaGraduationAuditBatch.generate_at, AaGraduationAuditBatch.created_at).between(start, end))
        batch_ids = batches.with_entities(AaGraduationAuditBatch.id).subquery()
        graduation = _query(db, AaGraduationAuditResult,
            AaGraduationAuditResult.batch_id.in_(select(batch_ids.c.id)),
            AaGraduationAuditResult.student_id.in_(student_ids))
        counts = _counts(graduation, AaGraduationAuditResult)
        state = _counts_state(counts, done=("GRADUATED", "COMPLETED", "DELAYED", "ARCHIVED"),
            known=("WAIT_PRECHECK", "SYSTEM_PASSED", "SYSTEM_ABNORMAL", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "REJECTED"))
        if not batches.count():
            state = "NOT_APPLICABLE"
        result[9] = (state, [], {"byStatus": counts})

    evaluation = _query(db, AaEvaluationTask, AaEvaluationTask.teaching_task_id.in_(task_ids)).join(
        AaEvaluationBatch, (AaEvaluationBatch.id == AaEvaluationTask.batch_id)
        & (AaEvaluationBatch.tenant_id == _tid()) & AaEvaluationBatch.is_deleted.is_(False)
    ).filter(AaEvaluationBatch.term_id == term.id)
    counts = _counts(evaluation, AaEvaluationTask)
    results = _query(db, AaEvaluationResult, AaEvaluationResult.teaching_task_id.in_(task_ids)).join(
        AaEvaluationBatch, (AaEvaluationBatch.id == AaEvaluationResult.batch_id)
        & (AaEvaluationBatch.tenant_id == _tid()) & AaEvaluationBatch.is_deleted.is_(False)
    ).filter(AaEvaluationBatch.term_id == term.id)
    result_ids = results.with_entities(AaEvaluationResult.id).subquery()
    appeals = _query(db, AaEvaluationAppeal,
        AaEvaluationAppeal.result_id.in_(select(result_ids.c.id)),
        AaEvaluationAppeal.status.in_(("SUBMITTED", "COLLEGE_REVIEW"))).count()
    unfinished_batches = evaluation.filter(AaEvaluationBatch.status.notin_(("RESULT_READY", "ARCHIVED"))).count()
    missing_results = evaluation.outerjoin(AaEvaluationResult,
        (AaEvaluationResult.tenant_id == _tid()) & AaEvaluationResult.is_deleted.is_(False)
        & (AaEvaluationResult.batch_id == AaEvaluationTask.batch_id)
        & (AaEvaluationResult.teaching_task_id == AaEvaluationTask.teaching_task_id)
    ).filter(AaEvaluationTask.submitted_count > 0, AaEvaluationResult.id.is_(None)).count()
    state = _counts_state(counts, done=("SUBMITTED",), known=("PENDING",))
    blockers = []
    if appeals or missing_results or unfinished_batches:
        state = "BLOCKED"
        blockers.append(_problem("QUALITY_CLOSURE_REQUIRED", "本院评教窗口、结果或申诉尚未全部收口"))
    if not _query(db, AaEvaluationBatch, AaEvaluationBatch.term_id == term.id).count():
        state = "NOT_APPLICABLE"
    result[10] = (state, blockers, {"byStatus": counts, "pendingAppealCount": appeals,
                                 "missingResultCount": missing_results})
    return result


def _student_stage_responsibility(index, evidence, org, school_responsible):
    if index == 5:
        # 学院可核对自己的学生记录，但现行选课批次命令只允许学校范围。
        return school_responsible("selection.manage")
    if index == 9 and set(evidence.get("byStatus", {})) <= {
        "ACADEMIC_REVIEW", "GRADUATED", "COMPLETED", "DELAYED", "ARCHIVED",
    }:
        return school_responsible("graduation.final")
    permission = {9: "graduation.collegeReview", 10: "evaluation.appeal.review"}[index]
    return org("academicAffairs." + permission)


def _schedule_change_groups(db, term, *, college_id=None, teacher_keys=None):
    """只聚合当前范围的在途单据；多条待审任务保留为异常，不任取第一人。"""
    from app.models import AaScheduleChange as Change, WorkflowInstance, WorkflowTask
    from .academic_affairs_schedule_change_service import _offering_college_expression
    pending = select(WorkflowTask.instance_id, WorkflowTask.node_code,
        func.count(WorkflowTask.id).label("task_count"), func.min(WorkflowTask.assignee_id).label("assignee_id")).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.is_deleted.is_(False),
        WorkflowTask.status == "PENDING").group_by(WorkflowTask.instance_id, WorkflowTask.node_code).subquery()
    offering = _offering_college_expression()
    query = _query(db, Change, Change.term_id == term.id,
        Change.status.in_(("SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "APPROVED")))
    if college_id is not None:
        query = query.filter(offering == college_id)
    if teacher_keys is not None:
        query = query.filter(Change.teacher_key.in_(teacher_keys))
    query = query.outerjoin(WorkflowInstance,
        (WorkflowInstance.id == Change.workflow_instance_id) & (WorkflowInstance.tenant_id == _tid())
        & WorkflowInstance.is_deleted.is_(False) & (WorkflowInstance.status == "RUNNING")
        & (WorkflowInstance.workflow_code == "ACAD_SCHEDULE_CHANGE")
        & (WorkflowInstance.current_node == Change.current_node)
        & (WorkflowInstance.source_module == "academic-affairs")
        & (WorkflowInstance.source_biz_type == "AA_SCHEDULE_CHANGE")
        & (WorkflowInstance.source_biz_id == Change.id)).outerjoin(pending,
        (pending.c.instance_id == WorkflowInstance.id) & (pending.c.node_code == Change.current_node))
    details = query.with_entities(Change.status, Change.current_node, offering.label("college_id"),
        pending.c.task_count, pending.c.assignee_id, Change.id.label("change_id"), Change.course_name).subquery()
    # 先完成范围与归属关联，再按明细列聚合；MySQL 严格分组不接受直接按相关标量子查询分组。
    return db.query(details.c.status, details.c.current_node, details.c.college_id,
        details.c.task_count, details.c.assignee_id, func.count(details.c.change_id).label("change_count"),
        func.min(details.c.change_id).label("change_id"), func.min(details.c.course_name).label("course_name")).group_by(
        details.c.status, details.c.current_node, details.c.college_id, details.c.task_count, details.c.assignee_id).all()


def _schedule_change_projection(db, term, *, college_id=None, teacher_keys=None, cache=None):
    from app.models import User
    groups = _schedule_change_groups(db, term, college_id=college_id, teacher_keys=teacher_keys)
    total = sum(int(row.change_count) for row in groups)
    if not total:
        return None
    ids = {int(row.assignee_id) for row in groups if row.assignee_id and row.task_count == 1}
    users = responsibility._cached(cache, ("CHANGE_ASSIGNEES", tuple(sorted(ids))), lambda: _query(
        db, User, User.id.in_(ids or {-1}), User.status == "ACTIVE").all())
    by_id = {int(row.id): row for row in users}
    people, unresolved = {}, 0
    for group in groups:
        node = group.current_node
        permission = {"COLLEGE_REVIEW": "scheduleChange.collegeReview",
                      "ACADEMIC_REVIEW": "scheduleChange.academicReview"}.get(node)
        person = by_id.get(int(group.assignee_id or 0))
        if (group.status == "APPROVED" or group.task_count != 1 or not permission
                or not person or not group.college_id):
            unresolved += int(group.change_count)
            continue
        school = node == "ACADEMIC_REVIEW"
        allowed = responsibility._scoped_holders(db, [person], "SCHOOL" if school else "COLLEGE",
            None if school else SimpleNamespace(id=int(group.college_id)), "academicAffairs." + permission, cache=cache)
        if allowed:
            people[int(person.id)] = person
        else:
            unresolved += int(group.change_count)
    orgs = {("SCHOOL", _tid()) if row.current_node == "ACADEMIC_REVIEW" else ("COLLEGE", int(row.college_id))
            for row in groups if row.current_node == "ACADEMIC_REVIEW"
            or (row.current_node == "COLLEGE_REVIEW" and row.college_id)}
    org_type, org_id = next(iter(orgs)) if len(orgs) == 1 else ("USER", None)
    org_name = {"SCHOOL": "校教务处调停课审核", "COLLEGE": "开课学院调停课审核"}.get(org_type, "调停课当前受理人")
    actor = responsibility._payload(org_type, org_id, org_name, (),
        [people[key] for key in sorted(people)], source="WORKFLOW_TASK" if people else "UNRESOLVED",
        reason="" if people else "在途调停课缺少唯一有效且有当前办理权限的受理人")
    route = _BASE + f"schedule-change?termId={term.id}"
    current = None
    if total == 1:
        row = groups[0]
        route += f"&changeId={row.change_id}"
        current = {"type": "SCHEDULE_CHANGE", "id": str(row.change_id), "label": row.course_name or "调停课申请"}
    return {"count": total, "unresolvedCount": unresolved, "responsibility": actor,
            "route": route, "currentObject": current}


def _with_schedule_changes(stage, projection, ctx, *, keep_attendance_responsibility=False):
    if not projection:
        return stage
    row = dict(stage)
    row["evidence"] = {**stage["evidence"], "pendingScheduleChangeCount": projection["count"],
        "unresolvedScheduleChangeCount": projection["unresolvedCount"],
        "scopeNote": "本范围仍有调停课等待审批或生效，考勤已提交不代表日常教学事项全部收口"}
    row["status"] = "BLOCKED" if projection["unresolvedCount"] or stage["status"] == "BLOCKED" else "ACTION_REQUIRED"
    row["blockers"] = list(stage["blockers"])
    if projection["unresolvedCount"]:
        row["blockers"].append(_problem("SCHEDULE_CHANGE_RESPONSIBILITY_UNRESOLVED",
            f"{projection['unresolvedCount']} 条调停课的当前审批或生效责任待核验，请核对原单与审批任务", projection["route"]))
    if not keep_attendance_responsibility:
        row["responsibility"] = projection["responsibility"]
        row["currentObject"] = projection["currentObject"]
        row["primaryAction"] = {"label": "查看待处理调停课", "route": projection["route"]} if _match(
            "academicAffairs.scheduleChange.view", ctx.permission_codes) else None
    return row


def _with_missing_teacher_grade_tasks(db, term, user, ctx, stage):
    from .academic_affairs_teacher_today_work_service import current_term_workbench
    start, end = _term_date(getattr(term, "start_date", None)), _term_date(getattr(term, "end_date", None))
    work = current_term_workbench(db, user, term_id=int(term.id),
        term_start_date=start.isoformat() if start else "", term_end_date=end.isoformat() if end else "")
    missing = [row for row in work.get("actionItems", []) if row.get("kind") == "GRADE_SETUP"]
    if not missing:
        return stage
    first = missing[0]
    actor = _relation_self_actor(db, user, ctx, source="CURRENT_TERM_FORMAL_TEACHER_FACTS",
        permission="academicAffairs.grade.input")
    result = _stage(8, term, ctx=ctx, status="BLOCKED", responsible=actor,
        blockers=[*stage["blockers"], _problem("GRADE_TASK_NOT_CREATED",
            f"本人 {len(missing)} 门正式授课课程尚未建立成绩任务，请从教师工作台继续处理", first.get("path"))],
        evidence={**stage["evidence"], "missingGradeTaskCount": len(missing)},
        current_object={"type": "TEACHING_TASK", "id": str(first["id"]), "label": first.get("title") or "待建成绩任务课程"})
    result["primaryAction"] = {"label": "处理待建成绩任务", "route": first["path"]} if actor["resolved"] and first.get("path") else None
    return result


def _college_grade_task_ids(term, college_id):
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    return select(AaTeachingTask.id).join(AaTeachingTaskBatch,
        AaTeachingTaskBatch.id == AaTeachingTask.batch_id).join(AaCourse, AaCourse.id == AaTeachingTask.course_id).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term.id,
        AaTeachingTaskBatch.is_deleted.is_(False), AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False),
        func.coalesce(AaCourse.owner_college_id, AaTeachingTaskBatch.college_id) == college_id)


def _with_missing_college_grade_tasks(db, term, college_id, ctx, stage, *, cache=None):
    from app.models import AaGradeTask, AaTeachingTask
    # 沿教师学期工作台的应建口径：READY 教学任务且本学期尚无成绩任务。
    # 学院按真实开课归属核验全量缺项，办理人再由正式授课关系与当前权限解析。
    has_grade = select(AaGradeTask.id).where(
        AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False),
        AaGradeTask.term_id == term.id, AaGradeTask.teaching_task_id == AaTeachingTask.id).exists()
    missing = _query(db, AaTeachingTask, AaTeachingTask.id.in_(_college_grade_task_ids(term, college_id)),
        AaTeachingTask.status == "READY", ~has_grade)
    count = missing.count()
    if not count:
        return stage
    first = missing.order_by(AaTeachingTask.id).first()
    actor = responsibility.resolve_teacher(db, first, permission_code="academicAffairs.grade.input", cache=cache) if first else None
    return _stage(8, term, ctx=ctx, college_id=college_id, status="BLOCKED", responsible=actor,
        blockers=[*stage["blockers"], _problem("GRADE_TASK_NOT_CREATED",
            f"本院 {count} 门已落实授课课程尚未建立成绩任务，请联系当前任课教师从教师工作台处理")],
        evidence={**stage["evidence"], "missingGradeTaskCount": count},
        current_object={"type": "TEACHING_TASK", "id": str(first.id), "label": first.course_name or "待建成绩任务课程"} if first else None)


def _unit_stages(db, term, ctx, college, school_responsible, resolver_cache):
    from app.models import (
        AaAttendanceSession, AaCourse, AaExamBatch, AaExamCourse, AaGradeTask, AaRegistration,
        AaProgram, AaRegistrationBatch, AaTeachingTask, AaTeachingTaskBatch, Major, StudentProfile,
    )
    from . import academic_affairs_archive_rule_evaluator as semantic

    cid = int(college.id)
    def org(permission="academicAffairs.teachingTask.manage"):
        key = (cid, permission)
        if key not in resolver_cache:
            resolver_cache[key] = responsibility.resolve_organization(db, "COLLEGE", cid, permission_code=permission, cache=resolver_cache)
        return resolver_cache[key]
    rows = [_stage(i, term, ctx=ctx, college_id=cid) for i in range(len(STAGES))]
    def put(i, **kwargs):
        rows[i] = _stage(i, term, ctx=ctx, college_id=cid, **kwargs)
    setup = readiness._term_setup_items(db, term)
    put(0, status="BLOCKED" if setup else "DONE", responsible=school_responsible("term.manage"),
        blockers=[_problem(row["ruleCode"], row["summary"], row["route"]) for row in setup])
    if not term:
        return rows
    student_ids = select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.college_id == cid,
        StudentProfile.is_deleted.is_(False))
    registrations = _query(db, AaRegistration).join(AaRegistrationBatch,
        (AaRegistrationBatch.id == AaRegistration.batch_id) & (AaRegistrationBatch.tenant_id == _tid())
        & AaRegistrationBatch.is_deleted.is_(False)).filter(
            AaRegistrationBatch.term_id == term.id, AaRegistration.student_id.in_(student_ids))
    counts = _counts(registrations, AaRegistration)
    put(1, status=_counts_state(counts, done=("REGISTERED",), known=("PENDING_REGISTER", "UNREGISTERED")),
        responsible=org("academicAffairs.registration.manage"), evidence={"byStatus": counts})
    program = semantic.evaluate_program(db, term, college_ids={cid})
    state, blockers = _semantic(program)
    pending_program = _query(db, AaProgram, AaProgram.status.in_(("DRAFT", "RETURNED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"))).join(
        Major, (Major.id == AaProgram.major_id) & (Major.tenant_id == _tid())
        & Major.is_deleted.is_(False)).filter(Major.college_id == cid).order_by(AaProgram.id).first()
    put(2, status=state, blockers=blockers, responsible=_program_responsibility(db, pending_program, college_id=cid, cache=resolver_cache),
        current_object={"type": "PROGRAM", "id": str(pending_program.id), "label": pending_program.program_name} if pending_program else None,
        evidence={"recordCount": program["recordCount"], "summary": program["summary"]})
    state, blockers, evidence, task, batch = _task_projection(db, term, cid, cache=resolver_cache)
    actor = _task_stage_responsibility(evidence, org, school_responsible)
    if state == "ACTION_REQUIRED" and evidence["waitingTeacherCount"] and task:
        pending = _query(db, AaTeachingTask, AaTeachingTask.batch_id.in_(select(AaTeachingTaskBatch.id).where(
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term.id,
            AaTeachingTaskBatch.college_id == cid, AaTeachingTaskBatch.is_deleted.is_(False))),
            AaTeachingTask.status == "ASSIGNED").order_by(AaTeachingTask.id).first()
        actor = responsibility.resolve_teacher(db, pending, cache=resolver_cache) if pending else actor
    put(3, status=state, blockers=blockers, evidence=evidence, responsible=actor,
        current_object={"type": "TEACHING_TASK_BATCH", "id": str(batch.id), "label": batch.batch_name} if batch else None)
    state, blockers, evidence, schedule = _schedule_projection(db, term, cid, resolver_cache)
    put(4, status=state, blockers=blockers, evidence=evidence,
        responsible=school_responsible("schedule.edit") if state == "READY" or evidence.get("responsibleOrgType") == "SCHOOL" else org("academicAffairs.schedule.edit"),
        current_object={"type": "SCHEDULE_BATCH", "id": str(schedule.id), "label": schedule.batch_name} if schedule else None)
    task_ids = select(AaTeachingTask.id).join(AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term.id,
        AaTeachingTaskBatch.college_id == cid, AaTeachingTaskBatch.is_deleted.is_(False))
    offering_task_ids = select(AaTeachingTask.id).join(AaTeachingTaskBatch,
        AaTeachingTaskBatch.id == AaTeachingTask.batch_id).join(AaCourse, AaCourse.id == AaTeachingTask.course_id).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term.id,
        AaTeachingTaskBatch.is_deleted.is_(False), AaCourse.tenant_id == _tid(),
        AaCourse.owner_college_id == cid, AaCourse.is_deleted.is_(False))
    # 学院只读本院学生/正式授课关系，批次与最终发布权仍由原业务命令裁决。
    for index, (state, blockers, evidence) in _student_unit_progress(db, term, cid, student_ids, task_ids).items():
        actor = _student_stage_responsibility(index, evidence, org, school_responsible)
        put(index, status=state, blockers=blockers, responsible=actor, evidence=evidence)
    attendance = _query(db, AaAttendanceSession, AaAttendanceSession.term_code == readiness._term_code(term),
                        AaAttendanceSession.teaching_task_id.in_(task_ids))
    attendance_counts = _counts(attendance, AaAttendanceSession)
    attendance_state = "ACTION_REQUIRED" if sum(attendance_counts.values()) else "NOT_STARTED"
    term_end = _term_date(term.end_date)
    if attendance_counts and set(attendance_counts) == {"SUBMITTED"} and term_end and term_end < readiness._local_today(db):
        attendance_state = "DONE" if term.status == "ARCHIVED" else "READY"
    changes = _schedule_change_projection(db, term, college_id=cid, cache=resolver_cache)
    put(6, status=attendance_state,
        responsible=None if changes else org("academicAffairs.attendance.view"),
        evidence={"byStatus": attendance_counts, "scopeNote": "日常教学持续运行，单次考勤提交不代表整个学期完成"})
    rows[6] = _with_schedule_changes(rows[6], changes, ctx)
    exams = _query(db, AaExamCourse, AaExamCourse.teaching_task_id.in_(offering_task_ids)).join(AaExamBatch,
        (AaExamBatch.id == AaExamCourse.batch_id) & (AaExamBatch.tenant_id == _tid())
        & AaExamBatch.is_deleted.is_(False)).filter(AaExamBatch.term_id == term.id, AaExamCourse.status != "REMOVED")
    exam_counts = _counts(exams, AaExamCourse)
    unfinished_exams = exams.filter(AaExamBatch.status.notin_(("FINISHED", "ARCHIVED"))).count()
    put(7, status=("DONE" if exam_counts and not unfinished_exams else _counts_state(
        exam_counts, ready=("CONFIRMED",), known=("PENDING_CONFIRM",))),
        responsible=org("academicAffairs.exam.manage"), evidence={"byStatus": exam_counts})
    grades = _query(db, AaGradeTask, AaGradeTask.term_id == term.id,
        AaGradeTask.teaching_task_id.in_(_college_grade_task_ids(term, cid)))
    grade_counts = _counts(grades, AaGradeTask)
    grade_actor = org("academicAffairs.grade.collegeReview")
    if set(grade_counts) <= {"ACADEMIC_REVIEW", "PUBLISHED", "ARCHIVED"}:
        grade_actor = school_responsible("grade.publish")
    elif set(grade_counts) & {"NOT_STARTED", "INPUTTING", "RETURNED"}:
        grade = grades.filter(AaGradeTask.status.in_(("NOT_STARTED", "INPUTTING", "RETURNED"))).order_by(AaGradeTask.id).first()
        teaching_task = _query(db, AaTeachingTask, AaTeachingTask.id == grade.teaching_task_id).first() if grade else None
        if teaching_task:
            grade_actor = responsibility.resolve_teacher(db, teaching_task, permission_code="academicAffairs.grade.input", cache=resolver_cache)
    put(8, status=_grade_status(grade_counts),
        responsible=grade_actor, evidence={"byStatus": grade_counts})
    rows[8] = _with_missing_college_grade_tasks(db, term, cid, ctx, rows[8], cache=resolver_cache)
    pending = [row for row in rows[1:11] if row["status"] not in _COMPLETE]
    put(11, status="BLOCKED" if pending else "DONE" if term.status == "ARCHIVED" else "READY", responsible=org("academicAffairs.archive.manage"),
        blockers=[_problem("COLLEGE_NOT_READY", "本院仍有待核验或未完成事项，请从对应工作区补齐") ] if pending else [],
        evidence={"scopeNote": "学院仅负责补齐本院材料，学校正式封存由校教务执行"})
    return rows


def _school_stages(db, term, ctx, units, school_responsible, *, complete_scope, cache=None):
    from app.models import AaArchiveBatch
    from . import academic_affairs_archive_service as archive
    from . import academic_affairs_archive_domain_policy as policy

    rows = []
    for index in range(len(STAGES)):
        unit_rows = [unit["stages"][index] for unit in units]
        blockers = [_problem("COLLEGE_NOT_READY", f"{unit['collegeName']}：{unit['stages'][index]['label']}仍有阻断")
                    for unit in units if unit["stages"][index]["status"] == "BLOCKED"]
        rows.append(_stage(index, term, ctx=ctx, status=_aggregate_status(unit_rows), blockers=blockers,
                           responsible=school_responsible(_SCHOOL_PERMISSIONS[index]) if index in _SCHOOL_PERMISSIONS else None,
                           evidence={"unitCount": len(unit_rows)}))
    setup = readiness._term_setup_items(db, term)
    rows[0] = _stage(0, term, ctx=ctx, status="BLOCKED" if setup else "DONE", responsible=school_responsible("term.manage"),
                     blockers=[_problem(row["ruleCode"], row["summary"], row["route"]) for row in setup])
    if not term or not complete_scope:
        return rows
    rows[6] = _with_schedule_changes(rows[6], _schedule_change_projection(db, term, cache=cache), ctx)
    school_schedule = _schedule_projection(db, term, None, cache if cache is not None else {})
    state, schedule_blockers, evidence, schedule = school_schedule
    rows[4] = _stage(4, term, ctx=ctx,
        status=_aggregate_status([rows[4], {"status": state}]),
        blockers=[*rows[4]["blockers"], *schedule_blockers],
        responsible=school_responsible("schedule.edit"),
        evidence={"unitCount": len(units), "schoolSchedule": evidence},
        current_object={"type": "SCHEDULE_BATCH", "id": str(schedule.id), "label": schedule.batch_name} if schedule else None)
    for index, evaluator in ((5, policy.evaluate_selection), (9, policy.evaluate_graduation), (10, policy.evaluate_evaluation)):
        result = evaluator(db, term.id)
        state, blockers = _semantic(result)
        rows[index] = _stage(index, term, ctx=ctx, status=state, blockers=blockers,
                             responsible=school_responsible(_SCHOOL_PERMISSIONS[index]),
                             evidence={"recordCount": result.get("recordCount", 0),
                                       "summary": result.get("summary") or result.get("remark", "")})
    batch = _query(db, AaArchiveBatch, AaArchiveBatch.term_id == term.id, AaArchiveBatch.status != "CANCELLED").first()
    current_archive = {"type": "ARCHIVE_BATCH", "id": str(batch.id), "label": batch.batch_name} if batch else None
    archive_status = batch.status if batch else None
    pending = [row for row in rows[:11] if row["status"] not in _COMPLETE]
    if pending and term.status != "ARCHIVED":
        # 未达前置条件的学期无需重复执行全量封存核查；保留真实批次，明确哪些领域尚未核查。
        rows[11] = _stage(11, term, ctx=ctx, status="BLOCKED",
            responsible=school_responsible("archive.manage"),
            blockers=[_problem("ARCHIVE_PREREQUISITE_PENDING", f"{row['label']}尚未就绪，请先完成该阶段") for row in pending],
            evidence={"checkedDomainCount": 0, "archiveBatchStatus": archive_status,
                      "scopeNote": "前置阶段尚未就绪，本次未执行完整归档领域核查"}, current_object=current_archive)
        return rows
    domains = archive._evaluate_domains(db, term.id, readiness._term_code(term))
    problems = [_problem(row.get("ruleCode") or "ARCHIVE_NOT_READY", row.get("summary") or "归档资料未完成", row.get("route"))
                for row in domains.values() if row.get("result") not in {"PASS", "NOT_APPLICABLE"}]
    archived = term.status == "ARCHIVED" and batch and batch.status == "ARCHIVED"
    rows[11] = _stage(11, term, ctx=ctx, status="BLOCKED" if problems else "DONE" if archived else "READY",
                      responsible=school_responsible("archive.manage"), blockers=problems,
                      evidence={"checkedDomainCount": len(domains), "archiveBatchStatus": archive_status},
                      current_object=current_archive)
    return rows


def _teacher_stages(db, term, user, ctx):
    from app.models import AaAttendanceSession, AaExamBatch, AaGradeTask
    from .academic_affairs_teacher_relation_authority import relation_scope
    from .academic_affairs_teacher_today_service import teacher_today_projection
    from .academic_affairs_invigilation_workbench_service import project_my_invigilations

    resolver_cache = {}
    rows = [_stage(i, term, ctx=ctx, status="NOT_APPLICABLE",
                   evidence={"scopeNote": "该阶段由学校或学院负责，任课教师不承担其管理责任"}) for i in range(len(STAGES))]
    if not term:
        rows[0] = _stage(0, term, ctx=ctx, status="BLOCKED", blockers=[_problem("CURRENT_TERM_MISSING", "尚未设置当前学期")])
        return rows
    scope = relation_scope(db, user, term_id=int(term.id))
    task_ids = scope["taskIds"]
    state, blockers, evidence, task, _batch = _task_projection(db, term, None, task_ids=task_ids, cache=resolver_cache)
    actor = responsibility.resolve_teacher(db, task, cache=resolver_cache) if task else None
    rows[3] = _stage(3, term, ctx=ctx, status=state, blockers=blockers, responsible=actor, evidence=evidence)
    today = teacher_today_projection(user)
    if str(today.get("termId") or "") != str(term.id):
        for index in (4, 6):
            rows[index] = _stage(index, term, ctx=ctx, status="BLOCKED", blockers=[
                _problem("TEACHER_TERM_EVIDENCE_UNAVAILABLE", "教师课表来源只支持当前学期，所选学期需在原工作区核验")])
    else:
        schedule_items = today.get("items") or []
        issues = [_problem("TEACHER_SCHEDULE_UNRESOLVED", "本人正式课表存在待核验事项，请查看教师课表")]
        rows[4] = _stage(4, term, ctx=ctx,
            status="BLOCKED" if today.get("issues") else "READY" if schedule_items else "NOT_STARTED",
            blockers=issues if today.get("issues") else [],
            evidence={"formalScheduleItemCount": len(schedule_items), "source": "TEACHER_FORMAL_SCHEDULE"})
        today_items = today.get("todayItems") or []
        sessions = _query(db, AaAttendanceSession,
            AaAttendanceSession.term_code == readiness._term_code(term),
            AaAttendanceSession.teaching_task_id.in_(task_ids or {-1}),
            AaAttendanceSession.session_date == today["todayDate"],
            AaAttendanceSession.source_type == "FORMAL_TEACHING").all()
        submitted = {(int(row.teaching_task_id), int(row.slot_no or 0)) for row in sessions if row.status == "SUBMITTED"}
        pending = [row for row in today_items if (int(row["teachingTaskId"]), int(row["slotNo"])) not in submitted]
        blocked = any(not row.get("attendanceExecutable") for row in pending)
        rows[6] = _stage(6, term, ctx=ctx,
            status="BLOCKED" if blocked else "ACTION_REQUIRED" if pending else "READY" if today_items else "NOT_STARTED",
            responsible=_relation_self_actor(db, user, ctx, source="TEACHER_FORMAL_OCCURRENCE",
                permission="academicAffairs.teachingTask.view") if today_items else None,
            blockers=[_problem("TEACHER_ATTENDANCE_UNAVAILABLE", "今日课次尚未满足正式考勤条件，请先处理教师工作台提示")] if blocked else [],
            evidence={"todayDate": today["todayDate"], "todayCourseCount": len(today_items),
                      "pendingAttendanceCount": len(pending), "scopeNote": "按今日真实课次核验，不代表整个学期教学已结束"})
    from .academic_affairs_schedule_change_service import _derive_keys
    rows[6] = _with_schedule_changes(rows[6], _schedule_change_projection(
        db, term, teacher_keys=set(_derive_keys(user)), cache=resolver_cache), ctx,
        keep_attendance_responsibility=bool(rows[6]["evidence"].get("pendingAttendanceCount")))
    term_start = _term_date(term.start_date)
    if not term_start:
        rows[7] = _stage(7, term, ctx=ctx, status="BLOCKED", blockers=[
            _problem("EXAM_TERM_SCOPE_UNKNOWN", "学期起始日期缺失，无法核验本人监考范围")])
    else:
        invigilations = project_my_invigilations(db, user, from_date=term_start.isoformat())
        batch_ids = set(str(value) for value in db.scalars(select(AaExamBatch.id).where(
            AaExamBatch.tenant_id == _tid(), AaExamBatch.term_id == term.id, AaExamBatch.is_deleted.is_(False))).all())
        my_exams = [row for row in invigilations["items"] if row["batchId"] in batch_ids]
        counts = dict(Counter(row["workStatus"] for row in my_exams))
        rows[7] = _stage(7, term, ctx=ctx,
            status=_counts_state(counts, done=("FINISHED",), known=("UPCOMING",)) if my_exams else "NOT_APPLICABLE",
            responsible=_relation_self_actor(db, user, ctx, source="AA_EXAM_INVIGILATOR",
                permission="academicAffairs.exam.view") if my_exams else None,
            evidence={"byStatus": counts, "source": "AA_EXAM_INVIGILATOR", "scopeNote": "仅本人正式监考安排"})
    grades = _query(db, AaGradeTask, AaGradeTask.term_id == term.id, AaGradeTask.teaching_task_id.in_(task_ids or {-1}))
    counts = _counts(grades, AaGradeTask)
    rows[8] = _stage(8, term, ctx=ctx, status=_grade_status(counts, teacher=True),
        responsible=responsibility.resolve_teacher(db, task, permission_code="academicAffairs.grade.input", cache=resolver_cache) if task else None,
        evidence={"byStatus": counts})
    rows[8] = _with_missing_teacher_grade_tasks(db, term, user, ctx, rows[8])
    return rows


def _major_scope(db, user, ctx):
    from app.models import RoleAssignmentScope
    if ctx.scope_type != "CLASS":
        return set()
    uid = str(ctx.user_id or "").removeprefix("db-")
    if not uid.isdigit():
        return set()
    now = datetime.utcnow()
    return set(db.scalars(select(RoleAssignmentScope.scope_id).where(
        RoleAssignmentScope.tenant_id == _tid(), RoleAssignmentScope.user_id == int(uid),
        RoleAssignmentScope.role_code == str(user.get("currentRoleCode") or ""),
        RoleAssignmentScope.scope_type == "MAJOR", RoleAssignmentScope.status == "ACTIVE",
        RoleAssignmentScope.is_deleted.is_(False), RoleAssignmentScope.effective_at <= now,
        or_(RoleAssignmentScope.expires_at.is_(None), RoleAssignmentScope.expires_at > now),
    )).all())


def _major_stages(db, term, ctx, major_ids):
    from app.models import AaProgram, Major
    rows = [_stage(i, term, ctx=ctx, status="NOT_APPLICABLE",
                   evidence={"scopeNote": "该阶段由学院或学校统筹，专业岗位不承担全院管理职责"}) for i in range(len(STAGES))]
    programs = _query(db, AaProgram, AaProgram.major_id.in_(major_ids),
                      AaProgram.status.notin_(("DISABLED", "ARCHIVED")))
    counts = _counts(programs, AaProgram)
    active = programs.filter(AaProgram.status.in_(("DRAFT", "RETURNED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"))).order_by(AaProgram.id).first()
    major_id = int(active.major_id) if active else next(iter(sorted(major_ids)))
    major = _query(db, Major, Major.id == major_id).first()
    actor = _program_responsibility(db, active, college_id=major.college_id if major else None)
    from .academic_affairs_program_activation_service import CURRENT_EFFECTIVE_PROGRAM_STATUSES
    rows[2] = _stage(2, term, ctx=ctx, status=_counts_state(counts,
        done=CURRENT_EFFECTIVE_PROGRAM_STATUSES, known=("DRAFT", "RETURNED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW")),
        responsible=actor, evidence={"byStatus": counts, "majorIds": [str(value) for value in sorted(major_ids)],
            "programCount": sum(counts.values()), "summary": f"本专业范围已配置 {sum(counts.values())} 个未停用、未归档培养方案"},
        current_object={"type": "PROGRAM", "id": str(active.id), "label": active.program_name} if active else None)
    if not term:
        rows[0] = _stage(0, term, ctx=ctx, status="BLOCKED", blockers=[_problem("CURRENT_TERM_MISSING", "尚未设置当前学期")])
        rows[3] = _stage(3, term, status="BLOCKED", blockers=[_problem("CURRENT_TERM_MISSING", "尚未设置当前学期，无法核验本专业开课准备")])
        return rows
    from .academic_affairs_archive_rule_evaluator import evaluate_teaching_task
    result = evaluate_teaching_task(db, term.id, major_ids=major_ids)
    fact = next((row for row in result.get("evidence", []) if row.get("type") == "TASK_RECONCILIATION"), None)
    status, blockers = _semantic(result)
    if fact is None:
        status = "BLOCKED"
        blockers.append(_problem("MAJOR_TASK_EVIDENCE_UNAVAILABLE", "本专业应开与教学任务核验结果不完整，请重新核对学期与培养方案"))
    elif result.get("result") == "PASS":
        status = "READY" if fact.get("expected") or fact.get("actual") else "NOT_STARTED"
    rows[3] = _stage(3, term, status=status, blockers=blockers,
        evidence={"majorIds": [str(value) for value in sorted(major_ids)], "readOnly": True,
            "summary": result.get("summary", "本专业教学任务准备情况待核验"),
            "expectedCourseCount": fact.get("expected") if fact else None, "actualTaskCount": fact.get("actual") if fact else None,
            "pendingTeacherCount": fact.get("pendingTeacherCount") if fact else None,
            "blockerCount": result.get("blockingCount")})
    return rows


def _global_gate_blockers(db, term, cache, *, run_final_reconciliation=True):
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    if not term:
        return [_problem("CURRENT_TERM_MISSING", "尚未设置当前学期")]
    rows = _query(db, AaTeachingTask, AaTeachingTask.status != "MERGED").join(AaTeachingTaskBatch,
        (AaTeachingTaskBatch.id == AaTeachingTask.batch_id) & (AaTeachingTaskBatch.tenant_id == _tid())
        & AaTeachingTaskBatch.is_deleted.is_(False)).filter(AaTeachingTaskBatch.term_id == term.id)
    missing_batch = rows.filter(AaTeachingTaskBatch.college_id.is_(None)).count()
    missing_owner = rows.outerjoin(AaCourse, (AaCourse.id == AaTeachingTask.course_id)
        & (AaCourse.tenant_id == _tid()) & AaCourse.is_deleted.is_(False)).filter(AaCourse.owner_college_id.is_(None)).count()
    blockers = []
    from .academic_affairs_archive_rule_evaluator import _expected_opening, evaluate_teaching_task
    if run_final_reconciliation:
        reconciliation = evaluate_teaching_task(db, term.id, cache=cache)
        evidence = reconciliation.get("evidence", [])
        if reconciliation.get("result") != "PASS":
            blockers.append(_problem("SCHOOL_TASK_RECONCILIATION_NOT_READY",
                reconciliation.get("summary") or "全校应开课程与教学任务最终对账尚未通过"))
    else:
        # 学院尚未就绪时暂缓全校任务对账；无法归院的方案/学期等治理异常仍须对学校可见。
        _expected, evidence = _expected_opening(db, term, cache=cache)
    unowned = [row for row in evidence
               if row.get("type") in {"PROGRAM_UNRESOLVED", "TERM_UNRESOLVED", "COURSE_UNRESOLVED"}]
    if unowned:
        blockers.append(_problem("SCHOOL_OPENING_SCOPE_UNRESOLVED", "存在无法归属开课单位的班级、方案或课程基础问题，须由学校核验"))
    if missing_batch:
        blockers.append(_problem("RESPONSIBILITY_UNRESOLVED", f"{missing_batch} 条教学任务缺少批次责任学院"))
    if missing_owner:
        blockers.append(_problem("OFFERING_UNIT_UNRESOLVED", f"{missing_owner} 条课程未配置正式开课单位"))
    if any(not value["complete"] and not _empty_schedule_check(value) for key, value in cache.items() if key[0] == "SCHEDULE_GATE"):
        blockers.append(_problem("SCHOOL_GATE_NOT_READY", "课表完整性、资源或硬冲突检查尚未通过"))
    if any(value for key, value in cache.items() if key[0] == "SCHEDULE_CROSS"):
        blockers.append(_problem("CROSS_COLLEGE_CONFLICT", "存在跨教学单位课表冲突，须由校教务协调"))
    return blockers


def flow(user, term_id=None, college_id=None):
    from app.models import College

    with session() as db:
        ctx = build_affairs_context(user, db)
        role = str((user or {}).get("currentRoleCode") or "").upper()
        teacher = role == "ACADEMIC_TEACHER"
        all_school = ctx.scope_type == "TENANT_ALL" and not teacher
        permitted = {int(value) for value in ctx.college_ids}
        major_ids = _major_scope(db, user, ctx) if not teacher and not all_school else set()
        if college_id and not all_school and (teacher or int(college_id) not in permitted):
            raise no_data_scope("不能查看其他学院的教务责任与进度")
        if not teacher and not all_school and not major_ids and (ctx.scope_type != "COLLEGE" or not permitted):
            raise no_data_scope("当前身份尚未配置可查看教务流程的学院或授课范围")
        term = readiness._load_term(db, term_id)
        viewer = {"roleCode": role, "scopeType": "ASSIGNED" if teacher else ctx.scope_type,
                  "collegeIds": [str(value) for value in sorted(permitted)],
                  "majorIds": [str(value) for value in sorted(major_ids)],
                  "assignments": responsibility.viewer_assignments(db, ctx.user_id)}
        units, gates = [], []
        if teacher:
            stages = _teacher_stages(db, term, user, ctx)
        elif major_ids:
            stages = _major_stages(db, term, ctx, major_ids)
        else:
            college_query = _query(db, College, College.status == "ACTIVE")
            if college_id:
                college_query = college_query.filter(College.id == int(college_id))
            elif not all_school:
                college_query = college_query.filter(College.id.in_(permitted))
            colleges = college_query.order_by(College.sort_order, College.id).all()
            resolver_cache = {}
            school = _school_resolver(db, resolver_cache)
            for college in colleges:
                unit_stages = _unit_stages(db, term, ctx, college, school, resolver_cache)
                current = _current(unit_stages)
                units.append({"collegeId": str(college.id), "collegeName": college.college_name,
                              "status": current["status"], "stages": unit_stages,
                              "blockers": current["blockers"], "responsibility": current["responsibility"]})
            stages = _school_stages(db, term, ctx, units, school, complete_scope=all_school and not college_id, cache=resolver_cache)
            if not all_school and len(units) == 1:
                stages = units[0]["stages"]
            if all_school:
                global_blockers = _global_gate_blockers(db, term, resolver_cache,
                    run_final_reconciliation=bool(units) and not college_id
                    and all(unit["stages"][3]["status"] in _COMPLETE for unit in units))
                for index in (3, 4, 11):
                    extra = stages[index]["blockers"] if index == 11 else [*global_blockers, *(stages[4]["blockers"] if index == 4 else [])]
                    if index == 3:
                        extra = [row for row in extra if row["code"] not in {"SCHOOL_GATE_NOT_READY", "CROSS_COLLEGE_CONFLICT"}]
                    gates.append(_gate(STAGES[index][0], STAGES[index][1] + "学校门禁", units,
                                       complete_scope=not college_id, extra_blockers=extra))
        uid = str(ctx.user_id or "").removeprefix("db-")
        related = [row for row in [*stages, *(stage for unit in units for stage in unit["stages"]) ]
                   if uid in (row.get("responsibility") or {}).get("assigneeUserIds", [])
                   and row["status"] not in {"DONE", "NOT_APPLICABLE"}]
        # 统一对象用阶段/组织键去重，不把所有学院的录入事项复制给校级账号。
        related = list({(row["stageCode"], (row.get("responsibility") or {}).get("orgId"),
            tuple(row["responsibility"].get("assigneeUserIds", [])) if row["responsibility"].get("source") == "WORKFLOW_TASK" else ()): row
            for row in related}.values())
        return {"term": {"termId": str(term.id), "termLabel": readiness._term_label(term), "status": term.status} if term else {},
                "viewer": viewer, "schoolStage": _current(stages) if all_school else None,
                "myStage": _current(related or stages), "unitProgress": units,
                "currentResponsibilities": related, "stages": stages, "schoolGates": gates,
                "generatedAt": datetime.utcnow().isoformat()}
