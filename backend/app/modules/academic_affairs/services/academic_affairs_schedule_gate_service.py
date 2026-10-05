"""课表预发布/正式发布同事务闸门。"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services.db_service import _tid

from .academic_affairs_task_execution_authority import load_execution_handoffs
from . import academic_affairs_schedule_policy as policy
from . import academic_affairs_scheduling_final_service as scheduling_service


def evaluate(db, batch, *, lock=False) -> dict:
    from app.models import AaClassroom, AaCourse, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch, College

    _term, teaching_weeks = policy.term_bounds(db, int(batch.term_id))
    task_batch_query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(batch.term_id),
        AaTeachingTaskBatch.status == "APPROVED",
        AaTeachingTaskBatch.is_deleted.is_(False),
    )
    task_batch_ids = [int(row.id) for row in task_batch_query.all()]
    task_query = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids or [-1]),
        AaTeachingTask.status == "READY",
        AaTeachingTask.no_auto_schedule.is_(False),
        AaTeachingTask.is_deleted.is_(False),
        policy.task_scope_condition(db, batch),
    ).order_by(AaTeachingTask.id)
    tasks = (task_query.with_for_update().populate_existing() if lock else task_query).all()
    handoffs = load_execution_handoffs(db, [row.id for row in tasks], lock=lock)
    tasks = [row for row in tasks if int(row.id) not in handoffs]
    items = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id == int(batch.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()

    task_map = {int(task.id): task for task in tasks}
    pairs = {}
    for task in tasks:
        if getattr(task, "class_id", None):
            pairs.setdefault((int(task.course_id), int(task.class_id)), []).append(task)
    potential_duplicates = {key for key, rows in pairs.items() if len(rows) > 1}
    duplicate_groups = []
    if potential_duplicates:
        # 复用当前方案应开核对，不自行把同课程的多来源条目改成只允许一条。
        from .academic_affairs_archive_rule_evaluator import evaluate_teaching_task
        # 任务批次学院不等于课程开课学院，权威核对必须保留跨批次的同课程任务。
        # 全校计算只用于内部裁决，对外仍投影到本候选可见任务。
        reconciliation = evaluate_teaching_task(db, batch.term_id, include_duplicate_groups=True)
        for row in reconciliation.get("duplicateTaskGroups", []):
            if (int(row["courseId"]), int(row["classId"])) in potential_duplicates:
                duplicate_groups.append({**row,
                    "taskIds": [value for value in row["taskIds"] if int(value) in task_map]})
    duplicate_ids = {task_id for row in duplicate_groups for task_id in row["taskIds"]}
    owned_courses = {int(row.id) for row in db.query(AaCourse).join(
        College, College.id == AaCourse.owner_college_id,
    ).filter(
        AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False),
        AaCourse.id.in_([task.course_id for task in tasks] or [-1]),
        College.tenant_id == _tid(), College.is_deleted.is_(False), College.status == "ACTIVE",
    ).all()}
    missing_owner = [str(task.id) for task in tasks if task.course_id not in owned_courses]
    classroom_ids = sorted({int(item.classroom_id) for item in items if item.classroom_id})
    classroom_query = db.query(AaClassroom).filter(
        AaClassroom.tenant_id == _tid(), AaClassroom.id.in_(classroom_ids or [-1]),
        AaClassroom.is_deleted.is_(False),
    ).order_by(AaClassroom.id).populate_existing()
    if lock:
        classroom_query = classroom_query.with_for_update()
    classrooms = {int(room.id): room for room in classroom_query.all()}
    invalid_classroom_items = [item for item in items if item.classroom_id and (
        int(item.classroom_id) not in classrooms
        or classrooms[int(item.classroom_id)].status != "AVAILABLE"
        or not classrooms[int(item.classroom_id)].allow_schedule
    )]
    counts: dict[int, int] = {}
    task_items: dict[int, list] = {}
    orphan_items = []
    invalid_coordinate_items = []
    for item in items:
        if (
            int(item.weekday or 0) < 1
            or int(item.weekday or 0) > 7
            or int(item.start_week or 0) < 1
            or int(item.end_week or 0) < int(item.start_week or 0)
            or int(item.end_week or 0) > teaching_weeks
        ):
            invalid_coordinate_items.append(item)
        if not item.task_id or int(item.task_id) not in task_map:
            orphan_items.append(item)
            continue
        counts[int(item.task_id)] = counts.get(int(item.task_id), 0) + 1
        task_items.setdefault(int(item.task_id), []).append(item)

    missing = []
    over = []
    invalid_tasks = []
    coverage_rows = []
    duplicate_tasks = []
    for task in tasks:
        expected = int(task.weekly_hours or 0)
        actual = int(counts.get(int(task.id), 0))
        coverage = policy.task_coverage(task, task_items.get(int(task.id), []), teaching_weeks)
        coverage_rows.append(coverage)
        invalid_ids = set(coverage["invalidItemIds"])
        invalid_coordinate_items.extend(row for row in task_items.get(int(task.id), [])
                                        if str(row.id) in invalid_ids and row not in invalid_coordinate_items)
        row = {"taskId": str(task.id), "courseName": task.course_name,
               "expectedSessions": expected, "scheduledSessions": actual,
               "remainingSessions": max(0, expected - actual), **coverage}
        if str(task.id) in duplicate_ids:
            duplicate_tasks.append(row)
        if coverage["invalidTask"]:
            invalid_tasks.append({
                **row,
                "weeklyHours": task.weekly_hours,
                "startWeek": task.start_week,
                "endWeek": task.end_week,
            })
            continue
        if coverage["missingContactHours"]:
            missing.append(row)
        if coverage["excessContactHours"] or coverage["weeklyOverloadCount"]:
            over.append(row)

    conflicts = scheduling_service.conflict_report_in_session(db, batch)
    expected_sessions = sum(max(0, int(task.weekly_hours or 0)) for task in tasks)
    scheduled_sessions = sum(counts.values())
    complete = bool(tasks) and not any((
        missing_owner,
        invalid_tasks,
        missing,
        over,
        orphan_items,
        invalid_coordinate_items,
        invalid_classroom_items,
        conflicts["hardCount"],
        duplicate_groups,
    ))
    return {
        "batchId": str(batch.id),
        "termId": str(batch.term_id),
        "batchStatus": batch.status,
        "teachingWeeks": teaching_weeks,
        "taskBatchCount": len(task_batch_ids),
        "totalTasks": len(tasks),
        "missingOwnerTaskIds": missing_owner,
        "missingOwnerCount": len(missing_owner),
        "duplicateTaskGroupCount": len(duplicate_groups),
        "duplicateTaskGroups": duplicate_groups[:100],
        "duplicateTasks": duplicate_tasks,
        "scheduledTasks": len(counts),
        "expectedSessions": expected_sessions,
        "scheduledSessions": scheduled_sessions,
        "scheduledItemCount": len(items),
        **{key: sum(row[key] for row in coverage_rows) for key in (
            "expectedContactHours", "scheduledContactHours", "missingContactHours",
            "excessContactHours", "weeklyOverloadCount")},
        "derivedTotalTaskCount": sum(row["totalHoursDerived"] for row in coverage_rows),
        "completionRate": round(len(counts) / len(tasks) * 100, 1) if tasks else 0.0,
        "invalidTaskCount": len(invalid_tasks),
        "missingTaskCount": len(missing),
        "overScheduledTaskCount": len(over),
        "orphanItemCount": len(orphan_items),
        "invalidCoordinateItemCount": len(invalid_coordinate_items),
        "invalidClassroomItemCount": len(invalid_classroom_items),
        "invalidClassroomItemIds": [str(item.id) for item in invalid_classroom_items],
        "hardConflicts": conflicts["hardCount"],
        "softConflicts": conflicts["softCount"],
        "invalidTasks": invalid_tasks,
        "missingTasks": missing,
        "overScheduledTasks": over,
        "orphanItemIds": [str(item.id) for item in orphan_items],
        "invalidCoordinateItemIds": [str(item.id) for item in invalid_coordinate_items],
        "hardConflictItems": conflicts["hardConflicts"],
        "softConflictItems": conflicts["softConflicts"],
        "complete": complete,
        "canPrePublish": complete,
        "ruleVersion": "AA_SCHEDULE_RULE_V2",
    }


def require_publishable(db, batch) -> dict:
    result = evaluate(db, batch, lock=True)
    if result["complete"]:
        return result
    reasons = []
    if result["totalTasks"] == 0:
        reasons.append("本学期没有可排的 READY 教学任务")
    if result["invalidTaskCount"]:
        reasons.append(f"教学任务周次/周学时异常 {result['invalidTaskCount']} 条")
    if result["missingOwnerCount"]:
        reasons.append(f"课程尚未配置有效开课单位 {result['missingOwnerCount']} 条")
    if result["duplicateTaskGroupCount"]:
        reasons.append(f"同课程同班任务重复 {result['duplicateTaskGroupCount']} 组，请先核对开课来源")
    if result["missingTaskCount"]:
        reasons.append(f"漏排教学任务 {result['missingTaskCount']} 条")
    if result["overScheduledTaskCount"]:
        reasons.append(f"超排教学任务 {result['overScheduledTaskCount']} 条")
    if result["orphanItemCount"]:
        reasons.append(f"未关联正式教学任务的课表行 {result['orphanItemCount']} 条")
    if result["invalidCoordinateItemCount"]:
        reasons.append(f"周次坐标异常课表行 {result['invalidCoordinateItemCount']} 条")
    if result["invalidClassroomItemCount"]:
        reasons.append(f"教室已停用、删除或未允许排课 {result['invalidClassroomItemCount']} 条")
    if result["hardConflicts"]:
        reasons.append(f"硬冲突 {result['hardConflicts']} 条")
    raise AppException(
        "DATA_CONFLICT",
        "课表尚未达到预发布条件：" + "；".join(reasons),
        details=result,
        http_status=409,
    )


def school_candidate_batches(db, batch, *, lock=False):
    """预检与学校发布使用同一学期、每个责任范围的最新候选。"""
    from app.models import AaScheduleBatch
    from . import academic_affairs_schedule_truth_service as truth

    query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.term_id == batch.term_id,
        AaScheduleBatch.is_deleted.is_(False),
        AaScheduleBatch.status.in_(("DRAFT", "PRE_PUBLISHED", "PUBLISHED")),
    ).order_by(AaScheduleBatch.id)
    candidates = query.with_for_update().populate_existing().all() if lock else query.all()
    by_scope = {truth.scope_of(candidate): candidate for candidate in candidates}
    # 始终核对请求的精确版本，不用同范围另一草稿替代它。
    by_scope[truth.scope_of(batch)] = batch
    return list(by_scope.values())


def evaluate_school_publish(db, batch, *, lock=False) -> dict:
    """正式发布前核验全学期候选；预发布仍只办理本责任范围。"""
    from collections import Counter
    from app.models import AaClassroom, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch
    from .academic_affairs_archive_rule_evaluator import evaluate_teaching_task
    from .academic_affairs_schedule_conflict_index import iter_same_slot_pairs
    from . import academic_affairs_schedule_truth_service as truth

    def rows(query, model):
        query = query.order_by(model.id)
        return query.with_for_update().populate_existing().all() if lock else query.all()

    task_batches = rows(db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == batch.term_id,
        AaTeachingTaskBatch.is_deleted.is_(False)), AaTeachingTaskBatch)
    tasks = rows(db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.batch_id.in_([row.id for row in task_batches])), AaTeachingTask)
    handoffs = load_execution_handoffs(db, [row.id for row in tasks], lock=lock)
    tasks = [row for row in tasks if int(row.id) not in handoffs]
    required = {row.id for row in tasks if row.status != "MERGED" and not row.no_auto_schedule}
    blockers = []

    def block(code, message):
        blockers.append({"code": code, "message": message})

    reconciliation = evaluate_teaching_task(db, batch.term_id)
    if reconciliation.get("result") != "PASS":
        block("TEACHING_TASK_NOT_READY", reconciliation.get("summary") or "学期应开课程与教学任务尚未全部核对完成")
    if not required:
        block("SCHOOL_SCHEDULE_EMPTY", "本学期没有可正式发布的教学任务")
    selected, covered = [], Counter()
    for candidate in school_candidate_batches(db, batch, lock=lock):
        ids = {value for (value,) in db.query(AaTeachingTask.id).filter(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.id.in_(required),
            policy.task_scope_condition(db, candidate)).all()}
        if not ids:
            continue
        selected.append(candidate)
        covered.update(ids)
        if candidate.status not in {"PRE_PUBLISHED", "PUBLISHED"}:
            block("SCHOOL_UNIT_NOT_PREPARED", f"{candidate.batch_name or '排课批次'}尚未完成预发布核对")
        elif candidate.status == "PUBLISHED" and truth.batch_truth(db, candidate).get("isCurrent") is not True:
            block("SCHOOL_FORMAL_HEAD_UNRESOLVED", "已发布课表缺少当前有效版本依据")
    missing = len(required.difference(covered))
    duplicates = sum(count > 1 for count in covered.values())
    if missing:
        block("SCHOOL_SCHEDULE_BATCH_MISSING", f"公共课或学院课程仍有{missing}个教学任务缺少排课责任批次")
    if duplicates:
        block("SCHOOL_SCHEDULE_SCOPE_OVERLAP", f"{duplicates}个教学任务同时落入多个发布范围，请先核对责任批次")
    items = rows(db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(), AaScheduleItem.is_deleted.is_(False),
        AaScheduleItem.batch_id.in_([row.id for row in selected]),
        AaScheduleItem.status == "EFFECTIVE"), AaScheduleItem)
    if lock:
        rows(db.query(AaClassroom).filter(AaClassroom.tenant_id == _tid(),
            AaClassroom.id.in_({row.classroom_id for row in items if row.classroom_id})), AaClassroom)
    for candidate in selected:
        check = evaluate(db, candidate, lock=lock)
        if not check["complete"]:
            block("SCHOOL_UNIT_NOT_READY", f"{candidate.batch_name or '排课批次'}仍有漏排、资源或硬冲突问题")
    objections = sum(row.objection_status == "PENDING" for row in items)
    if objections:
        block("SCHOOL_OBJECTIONS_PENDING", f"全校候选课表仍有{objections}条教师异议待处理")
    conflicts = 0
    for left, right in iter_same_slot_pairs(items):
        if left.batch_id == right.batch_id or not truth._weeks_overlap(left, right):
            continue
        if {(kind, value) for kind, value, _label in truth._resources(left)} & {
                (kind, value) for kind, value, _label in truth._resources(right)}:
            conflicts += 1
    if conflicts:
        block("SCHOOL_CANDIDATE_CONFLICT", f"公共课与学院候选课表之间存在{conflicts}项共享资源硬冲突")
    return {"ready": not blockers, "termId": str(batch.term_id), "blockers": blockers,
            "requiredBatchIds": [str(row.id) for row in selected], "missingTaskCount": missing,
            "hardConflicts": conflicts, "teachingTaskReconciliation": reconciliation}


def require_school_publishable(db, batch) -> dict:
    result = evaluate_school_publish(db, batch, lock=True)
    if not result["ready"]:
        raise AppException("DATA_CONFLICT", "学校正式发布条件未通过：" + "；".join(
            row["message"] for row in result["blockers"]), details=result, http_status=409)
    return result
