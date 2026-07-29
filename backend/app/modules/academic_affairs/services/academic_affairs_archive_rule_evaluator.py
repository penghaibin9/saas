"""V2归档P0第一批语义规则评估器。

不新增归档表，不改变现有批次状态机；只把 PROGRAM / TEACHING_TASK / SCHEDULE / GRADE
从“有记录”升级为可解释的业务门禁，并返回统一结构化证据。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from app.services.db_service import _tid

from .academic_affairs_program_binding_quality_service import validate_program_db
from .student_program_resolution_service import resolve_student_program


_ROUTE = {
    "PROGRAM": "/admin/academic-affairs/programs",
    "TEACHING_TASK": "/admin/academic-affairs/teaching-tasks",
    "SCHEDULE": "/admin/academic-affairs/scheduling",
    "GRADE": "/admin/academic-affairs/grade-tasks",
}


def rule_result(code: str, *, passed: bool, record_count=0, blocker_count=0,
                rule_code="", summary="", evidence=None, route=None) -> dict:
    return {
        "recordCount": int(record_count or 0),
        "present": bool(passed),
        "remark": summary,
        "result": "PASS" if passed else "BLOCKED",
        "ruleCode": rule_code or f"{code}_SEMANTIC_GATE",
        "summary": summary,
        "blockingCount": int(blocker_count or 0),
        "route": route or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck"),
        "evidence": list(evidence or []),
    }


def normalize_legacy_result(code: str, result: dict) -> dict:
    source = dict(result or {})
    passed = bool(source.get("present"))
    summary = str(source.get("remark") or "")
    return {
        **source,
        "result": source.get("result") or ("PASS" if passed else "BLOCKED"),
        "ruleCode": source.get("ruleCode") or f"{code}_SEMANTIC_GATE",
        "summary": source.get("summary") or summary,
        "blockingCount": int(source.get("blockingCount") or (0 if passed else 1)),
        "route": source.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck"),
        "evidence": list(source.get("evidence") or []),
    }


def evaluate_program(db, *, college_ids=None) -> dict:
    """所有在读学生均能解析到方案，且涉及方案的BLOCKER为0。"""
    from app.models import StudentProfile
    from .academic_affairs_status_service import is_enrolled

    query = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )
    if college_ids:
        query = query.filter(StudentProfile.college_id.in_(list(college_ids)))
    students = [row for row in query.all() if is_enrolled(getattr(row, "student_status", None))]
    if not students:
        return rule_result(
            "PROGRAM", passed=False, rule_code="PROGRAM_NO_ENROLLED_STUDENT",
            summary="当前范围没有可核验的在读学生，不能证明培养方案覆盖率",
            blocker_count=1,
        )

    unresolved = []
    resolved = []
    for student in students:
        resolution = resolve_student_program(db, student, tenant_id=_tid())
        if resolution.status != "RESOLVED" or not resolution.program:
            unresolved.append({
                "studentId": str(student.id),
                "studentNo": getattr(student, "student_no", None),
                "majorId": str(getattr(student, "major_id", None) or ""),
                "grade": getattr(student, "grade", None),
                "classId": str(getattr(student, "class_id", None) or ""),
                "status": resolution.status,
                "rule": resolution.rule,
                "message": resolution.message,
            })
        else:
            resolved.append((student, resolution))

    program_ids = sorted({int(resolution.program.id) for _student, resolution in resolved})
    validation_blockers = []
    for program_id in program_ids:
        validation = validate_program_db(db, program_id)
        for issue in validation.get("issues") or []:
            if str(issue.get("level") or issue.get("severity") or "").upper() != "BLOCKER":
                continue
            validation_blockers.append({
                "programId": str(program_id),
                "code": issue.get("code"),
                "message": issue.get("message"),
                "objectId": str(issue.get("objectId") or ""),
                "fixRoute": issue.get("fixRoute") or f"/admin/academic-affairs/programs/{program_id}",
            })

    blockers = len(unresolved) + len(validation_blockers)
    coverage = round((len(resolved) / len(students)) * 100, 2) if students else 0
    evidence = [
        {
            "type": "PROGRAM_COVERAGE",
            "enrolledStudents": len(students),
            "resolvedStudents": len(resolved),
            "coveragePercent": coverage,
            "programIds": [str(value) for value in program_ids],
        },
        *unresolved[:30],
        *validation_blockers[:30],
    ]
    return rule_result(
        "PROGRAM",
        passed=blockers == 0 and coverage == 100,
        record_count=len(students),
        blocker_count=blockers,
        rule_code="PROGRAM_COVERAGE_AND_VALIDATION",
        summary=(
            f"在读学生方案覆盖率100%，{len(program_ids)}个生效方案均无BLOCKER"
            if blockers == 0 and coverage == 100
            else f"方案覆盖率{coverage}%，未解析学生{len(unresolved)}人，方案BLOCKER {len(validation_blockers)}项"
        ),
        evidence=evidence,
    )


def _expected_opening(db, term, *, college_ids=None):
    from app.models import AaProgram, AaProgramBinding, AaProgramCourse, SchoolClass
    from .academic_affairs_program_opening_closure_service import _plan_term_no

    programs = db.query(AaProgram).filter(
        AaProgram.tenant_id == _tid(),
        AaProgram.status.in_(["PUBLISHED", "ENABLED", "FROZEN"]),
        AaProgram.is_deleted.is_(False),
    ).all()
    bindings = db.query(AaProgramBinding).filter(
        AaProgramBinding.tenant_id == _tid(),
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    ).all()
    binding_by_program = defaultdict(list)
    for binding in bindings:
        binding_by_program[int(binding.program_id)].append(binding)

    expected = []
    structural = []
    for program in programs:
        for binding in binding_by_program.get(int(program.id), []):
            grade = binding.grade_year or program.grade_year
            plan_term = _plan_term_no(term.year_code, term.term_no, grade)
            if plan_term is None:
                structural.append({
                    "type": "TERM_UNRESOLVED", "programId": str(program.id),
                    "bindingId": str(binding.id), "gradeYear": grade,
                })
                continue
            if binding.class_id:
                classes = db.query(SchoolClass).filter(
                    SchoolClass.id == int(binding.class_id),
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.class_status == "NORMAL",
                    SchoolClass.is_deleted.is_(False),
                ).all()
            else:
                classes = db.query(SchoolClass).filter(
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.major_id == binding.major_id,
                    SchoolClass.grade == grade,
                    SchoolClass.class_status == "NORMAL",
                    SchoolClass.is_deleted.is_(False),
                ).all()
            if college_ids:
                classes = [row for row in classes if getattr(row, "college_id", None) in set(college_ids)]
            if not classes:
                structural.append({
                    "type": "NO_CLASS", "programId": str(program.id),
                    "bindingId": str(binding.id), "gradeYear": grade,
                })
                continue
            courses = db.query(AaProgramCourse).filter(
                AaProgramCourse.tenant_id == _tid(),
                AaProgramCourse.program_id == int(program.id),
                AaProgramCourse.open_term_no == int(plan_term),
                AaProgramCourse.is_deleted.is_(False),
            ).all()
            for clazz in classes:
                for course in courses:
                    if not course.course_id:
                        structural.append({
                            "type": "COURSE_UNRESOLVED", "programId": str(program.id),
                            "programCourseId": str(course.id), "classId": str(clazz.id),
                        })
                        continue
                    expected.append({
                        "key": (int(course.course_id), int(clazz.id)),
                        "programId": str(program.id),
                        "programCourseId": str(course.id),
                        "courseId": str(course.course_id),
                        "classId": str(clazz.id),
                    })
    return expected, structural


def evaluate_teaching_task(db, term_id, *, college_ids=None) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm

    if not term_id:
        return rule_result(
            "TEACHING_TASK", passed=False, blocker_count=1,
            rule_code="TASK_TERM_REQUIRED", summary="未指定学期，无法核对方案应开与教学任务",
        )
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id), AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return rule_result(
            "TEACHING_TASK", passed=False, blocker_count=1,
            rule_code="TASK_TERM_NOT_FOUND", summary="学期不存在，无法核对教学任务",
        )

    batch_query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term_id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )
    if college_ids:
        batch_query = batch_query.filter(AaTeachingTaskBatch.college_id.in_(list(college_ids)))
    batches = batch_query.all()
    batch_ids = [int(row.id) for row in batches]
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(batch_ids or [0]),
        AaTeachingTask.status != "MERGED",
        AaTeachingTask.is_deleted.is_(False),
    ).all()

    expected, structural = _expected_opening(db, term, college_ids=college_ids)
    expected_counter = Counter(item["key"] for item in expected)
    actual_map = defaultdict(list)
    for task in tasks:
        actual_map[(int(task.course_id), int(task.class_id or 0))].append(task)

    missing = [item for item in expected if not actual_map.get(item["key"])]
    duplicate = [
        {"type": "DUPLICATE_TASK", "courseId": str(key[0]), "classId": str(key[1]),
         "taskIds": [str(row.id) for row in rows]}
        for key, rows in actual_map.items() if len(rows) > expected_counter.get(key, 0) and expected_counter.get(key, 0) > 0
    ]
    extra = [
        {"type": "OVER_OPENED", "courseId": str(key[0]), "classId": str(key[1]),
         "taskIds": [str(row.id) for row in rows]}
        for key, rows in actual_map.items() if key not in expected_counter
    ]
    unconfirmed = [
        {"type": "TASK_NOT_READY", "taskId": str(task.id), "status": task.status,
         "courseId": str(task.course_id), "classId": str(task.class_id or "")}
        for task in tasks if str(task.status or "").upper() != "READY"
    ]
    no_teacher = [
        {"type": "TASK_NO_TEACHER", "taskId": str(task.id), "courseId": str(task.course_id)}
        for task in tasks if not str(task.teacher_key or "").strip()
    ]
    unfinished_batches = [
        {"type": "BATCH_NOT_APPROVED", "batchId": str(batch.id), "status": batch.status}
        for batch in batches if str(batch.status or "").upper() not in {"APPROVED", "ARCHIVED"}
    ]

    blockers = structural + missing + duplicate + extra + unconfirmed + no_teacher + unfinished_batches
    evidence = [
        {"type": "TASK_RECONCILIATION", "expected": len(expected), "actual": len(tasks)},
        *structural[:20],
        *[{"type": "MISSING_TASK", **item} for item in missing[:20]],
        *duplicate[:20], *extra[:20], *unconfirmed[:20], *no_teacher[:20], *unfinished_batches[:20],
    ]
    return rule_result(
        "TEACHING_TASK",
        passed=not blockers,
        record_count=len(tasks),
        blocker_count=len(blockers),
        rule_code="TASK_OPENING_RECONCILIATION",
        summary=(
            f"应开{len(expected)}项与{len(tasks)}条教学任务一致，教师确认完成"
            if not blockers
            else f"教学任务阻断{len(blockers)}项：漏开{len(missing)}、重复{len(duplicate)}、多开{len(extra)}、未确认{len(unconfirmed)}"
        ),
        evidence=evidence,
    )


def _weeks_overlap(left, right) -> bool:
    if int(left.start_week or 1) > int(right.end_week or 999):
        return False
    if int(right.start_week or 1) > int(left.end_week or 999):
        return False
    lp = str(left.week_parity or "ALL").upper()
    rp = str(right.week_parity or "ALL").upper()
    return lp == "ALL" or rp == "ALL" or lp == rp


def hard_schedule_conflicts(items) -> list[dict]:
    grouped = defaultdict(list)
    for item in items or []:
        grouped[(int(item.batch_id), int(item.weekday), int(item.slot_no))].append(item)
    conflicts = []
    for (_batch, _weekday, _slot), rows in grouped.items():
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                if not _weeks_overlap(left, right):
                    continue
                kinds = []
                if left.teacher_key and right.teacher_key and left.teacher_key == right.teacher_key:
                    kinds.append("TEACHER")
                if left.class_id and right.class_id and int(left.class_id) == int(right.class_id):
                    kinds.append("CLASS")
                left_room = left.classroom_id or str(left.classroom_text or "").strip()
                right_room = right.classroom_id or str(right.classroom_text or "").strip()
                if left_room and right_room and left_room == right_room:
                    kinds.append("CLASSROOM")
                if kinds:
                    conflicts.append({
                        "type": "HARD_CONFLICT",
                        "kinds": kinds,
                        "itemIds": [str(left.id), str(right.id)],
                        "batchId": str(left.batch_id),
                        "weekday": left.weekday,
                        "slotNo": left.slot_no,
                    })
    return conflicts


def evaluate_schedule(db, term_id, previous_result: dict, *, college_ids=None) -> dict:
    from app.models import AaScheduleBatch, AaScheduleItem, AaSchedulePublish, AaTeachingTask, AaTeachingTaskBatch

    base = normalize_legacy_result("SCHEDULE", previous_result)
    if not term_id:
        return rule_result(
            "SCHEDULE", passed=False, blocker_count=1,
            rule_code="SCHEDULE_TERM_REQUIRED", summary="未指定学期，无法核验正式课表",
        )
    batch_query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == int(term_id),
        AaScheduleBatch.is_deleted.is_(False),
    )
    if college_ids:
        batch_query = batch_query.filter(AaScheduleBatch.college_id.in_(list(college_ids)))
    batches = batch_query.all()
    batch_ids = [int(row.id) for row in batches]
    voided = {
        int(row.batch_id) for row in db.query(AaSchedulePublish).filter(
            AaSchedulePublish.tenant_id == _tid(),
            AaSchedulePublish.batch_id.in_(batch_ids or [0]),
            AaSchedulePublish.action == "VOID_REISSUE",
            AaSchedulePublish.is_deleted.is_(False),
        ).all()
    }
    formal_ids = [
        int(row.id) for row in batches
        if str(row.status or "").upper() == "PUBLISHED"
        or (str(row.status or "").upper() == "ARCHIVED" and int(row.id) not in voided)
    ]
    items = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(formal_ids or [0]),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()

    task_batches = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term_id),
        AaTeachingTaskBatch.status.in_(["APPROVED", "ARCHIVED"]),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).all()
    task_batch_ids = [int(row.id) for row in task_batches]
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids or [0]),
        AaTeachingTask.status == "READY",
        AaTeachingTask.no_auto_schedule.is_(False),
        AaTeachingTask.is_deleted.is_(False),
    ).all()
    scheduled_task_ids = {int(row.task_id) for row in items if row.task_id}
    missing = [
        {"type": "UNSCHEDULED_TASK", "taskId": str(task.id), "courseId": str(task.course_id),
         "classId": str(task.class_id or "")}
        for task in tasks if int(task.id) not in scheduled_task_ids
    ]
    conflicts = hard_schedule_conflicts(items)
    inherited_blockers = 0 if base["present"] else max(1, int(base.get("blockingCount") or 1))
    blockers = inherited_blockers + len(missing) + len(conflicts)
    evidence = [
        {"type": "SCHEDULE_RECONCILIATION", "formalBatchIds": [str(value) for value in formal_ids],
         "readyTasks": len(tasks), "effectiveItems": len(items), "baseSummary": base["summary"]},
        *missing[:30], *conflicts[:30],
    ]
    return rule_result(
        "SCHEDULE",
        passed=blockers == 0,
        record_count=len(items),
        blocker_count=blockers,
        rule_code="SCHEDULE_PUBLISHED_CONFLICT_AND_COVERAGE",
        summary=(
            f"正式课表已发布，{len(tasks)}个应排任务全部落课，HARD冲突0"
            if blockers == 0
            else f"课表阻断{blockers}项：漏排{len(missing)}、HARD冲突{len(conflicts)}；{base['summary']}"
        ),
        evidence=evidence,
    )


def evaluate_grade(db, term_code, previous_result: dict) -> dict:
    from app.models import AaGradeRecheck, AaGradeRecord, AaGradeTask, AcademicGrade, WorkflowInstance

    task_query = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False),
    )
    if term_code:
        task_query = task_query.filter(AaGradeTask.term_code == term_code)
    tasks = task_query.all()
    unfinished = [row for row in tasks if str(row.status or "").upper() not in {"PUBLISHED", "ARCHIVED"}]

    recheck_query = db.query(AaGradeRecheck).join(
        AcademicGrade, AcademicGrade.id == AaGradeRecheck.acad_grade_id,
    ).filter(
        AaGradeRecheck.tenant_id == _tid(),
        AaGradeRecheck.status == "SUBMITTED",
        AaGradeRecheck.is_deleted.is_(False),
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.is_deleted.is_(False),
    )
    if term_code:
        recheck_query = recheck_query.filter(AcademicGrade.term == term_code)
    active_rechecks = int(recheck_query.count() or 0)

    change_query = db.query(WorkflowInstance).join(
        AaGradeRecord, AaGradeRecord.id == WorkflowInstance.source_biz_id,
    ).join(AaGradeTask, AaGradeTask.id == AaGradeRecord.task_id).filter(
        WorkflowInstance.tenant_id == _tid(),
        WorkflowInstance.source_module == "academic-affairs",
        WorkflowInstance.source_biz_type == "AA_GRADE_CHANGE",
        WorkflowInstance.status == "RUNNING",
        WorkflowInstance.is_deleted.is_(False),
        AaGradeRecord.tenant_id == _tid(),
        AaGradeRecord.is_deleted.is_(False),
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if term_code:
        change_query = change_query.filter(AaGradeTask.term_code == term_code)
    active_changes = int(change_query.count() or 0)

    blockers = len(unfinished) + active_rechecks + active_changes + (1 if not tasks else 0)
    base = normalize_legacy_result("GRADE", previous_result)
    evidence = [{
        "type": "GRADE_CLOSURE",
        "taskCount": len(tasks),
        "unpublishedTaskIds": [str(row.id) for row in unfinished[:50]],
        "activeRechecks": active_rechecks,
        "activeChanges": active_changes,
        "baseSummary": base["summary"],
    }]
    rule_code = (
        "GRADE_TASK_MISSING" if not tasks else
        "GRADE_TASK_UNPUBLISHED" if unfinished else
        "GRADE_RECHECK_ACTIVE" if active_rechecks else
        "GRADE_CHANGE_ACTIVE" if active_changes else
        "GRADE_CLOSED"
    )
    return rule_result(
        "GRADE",
        passed=blockers == 0,
        record_count=len(tasks),
        blocker_count=blockers,
        rule_code=rule_code,
        summary=(
            "应录成绩任务全部发布，且在途复查/更正为0"
            if blockers == 0
            else f"成绩阻断{blockers}项：未发布任务{len(unfinished)}、在途复查{active_rechecks}、在途更正{active_changes}"
        ),
        evidence=evidence,
    )


def evaluate_first_batch(db, term_id, term_code, previous: dict, *, college_ids=None) -> dict:
    results = {code: normalize_legacy_result(code, value) for code, value in (previous or {}).items()}
    results["PROGRAM"] = evaluate_program(db, college_ids=college_ids)
    results["TEACHING_TASK"] = evaluate_teaching_task(db, term_id, college_ids=college_ids)
    results["SCHEDULE"] = evaluate_schedule(
        db, term_id, results.get("SCHEDULE") or {}, college_ids=college_ids,
    )
    results["GRADE"] = evaluate_grade(db, term_code, results.get("GRADE") or {})
    return results
