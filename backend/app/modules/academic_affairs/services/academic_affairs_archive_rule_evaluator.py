"""V2归档P0第一批语义规则评估器。

不新增归档表，不改变现有批次状态机；只把 PROGRAM / TEACHING_TASK / SCHEDULE / GRADE
从“有记录”升级为可解释的业务门禁，并返回统一结构化证据。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from app.services.db_service import _tid

from .academic_affairs_archive_term_scope import cohort_term_scope
from .academic_affairs_program_activation_service import resolve_program_for_scope
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
    state = str(source.get("result") or ("PASS" if source.get("present") else "BLOCKED")).upper()
    if state not in {"PASS", "BLOCKED", "NOT_APPLICABLE", "UNKNOWN"}:
        state = "UNKNOWN"
    blocking = source.get("blockingCount")
    if blocking is None:
        blocking = 1 if state in {"BLOCKED", "UNKNOWN"} else 0
    blocking = max(1, int(blocking or 0)) if state in {"BLOCKED", "UNKNOWN"} else 0
    summary = str(source.get("summary") or source.get("remark") or "")
    return {
        **source,
        "present": state == "PASS",
        "result": state,
        "ruleCode": source.get("ruleCode") or f"{code}_SEMANTIC_GATE",
        "summary": summary,
        "remark": summary,
        "blockingCount": blocking,
        "route": source.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck"),
        "evidence": list(source.get("evidence") or []),
    }


def _archived_term_graduate_ids(db, term, student_ids):
    """仅恢复本期已正式毕业并归档的学生范围，不扩大到历史毕业主档。"""
    from sqlalchemy import select
    from app.models import (
        AaGraduationAuditBatch, AaGraduationAuditResult,
        GraduationDecisionFact, GraduationEvaluationRun,
    )
    from .academic_affairs_graduation_term_scope import batch_term_condition

    result, batch = AaGraduationAuditResult, AaGraduationAuditBatch
    decision, run = GraduationDecisionFact, GraduationEvaluationRun
    return set(db.scalars(select(result.student_id).join(
        batch, batch.id == result.batch_id,
    ).join(decision, decision.result_id == result.id).join(
        run, run.id == decision.evaluation_run_id,
    ).where(
        result.tenant_id == _tid(), result.is_deleted.is_(False), result.status == "ARCHIVED",
        result.student_id.in_(student_ids),
        result.conclusion.in_(["GRADUATED", "COMPLETED"]),
        batch.tenant_id == _tid(), batch.status == "ARCHIVED", batch_term_condition(term),
        decision.tenant_id == _tid(), decision.batch_id == batch.id,
        decision.student_id == result.student_id, decision.conclusion == result.conclusion,
        run.tenant_id == _tid(), run.batch_id == batch.id, run.result_id == result.id,
        run.student_id == result.student_id, run.overall == "SYSTEM_PASSED",
    )))


def evaluate_program(db, term=None, *, college_ids=None) -> dict:
    """指定学期范围内学生均能解析到方案，且涉及方案的BLOCKER为0。

    历史归档只核当时处于1..12培养学期范围的 cohort；合法未来届/已超学制届属于
    OUT_OF_SCOPE，不应阻断该历史学期。方案绑定按学期结束时点回放，避免归档后的
    新版本反向改写历史结论；年级格式异常仍 fail-closed。
    """
    from app.models import StudentProfile
    from .academic_affairs_status_service import is_enrolled

    query = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )
    if college_ids:
        query = query.filter(StudentProfile.college_id.in_(list(college_ids)))
    profiles = query.all()
    graduates = [row for row in profiles if getattr(row, "student_status", None) in {"GRADUATED", "COMPLETED"}]
    archived_ids = _archived_term_graduate_ids(db, term, [row.id for row in graduates]) if term is not None and graduates else set()
    enrolled = [row for row in profiles if is_enrolled(getattr(row, "student_status", None)) or row.id in archived_ids]

    students = []
    out_of_scope = 0
    invalid_scope = []
    for student in enrolled:
        if term is None:
            students.append(student)
            continue
        scope = cohort_term_scope(term.year_code, term.term_no, getattr(student, "grade", None))
        if scope["state"] == "OUT_OF_SCOPE":
            out_of_scope += 1
            continue
        if scope["state"] == "INVALID":
            invalid_scope.append({
                "type": "INVALID_COHORT_TERM_SCOPE",
                "studentId": str(student.id),
                "studentNo": getattr(student, "student_no", None),
                "grade": getattr(student, "grade", None),
                "termId": str(getattr(term, "id", "") or ""),
            })
            continue
        students.append(student)

    if not students:
        return rule_result(
            "PROGRAM", passed=False, rule_code="PROGRAM_NO_ENROLLED_STUDENT",
            summary="当前学期范围没有可核验的在读或本期已归档毕业学生，不能证明培养方案覆盖率",
            blocker_count=max(1, len(invalid_scope)),
            evidence=[*invalid_scope[:30], {"type": "OUT_OF_SCOPE_COHORTS", "students": out_of_scope}],
        )

    unresolved = []
    resolved = []
    replay_as_of = getattr(term, "end_date", None) if term is not None else None
    resolution_cache = {}
    for student in students:
        resolution_key = (
            int(getattr(student, "major_id", 0) or 0),
            str(getattr(student, "grade", None) or "").strip(),
            int(getattr(student, "class_id", 0) or 0),
        )
        resolution = resolution_cache.get(resolution_key)
        if resolution is None:
            resolution = resolve_student_program(
                db, student, tenant_id=_tid(), as_of=replay_as_of
            )
            resolution_cache[resolution_key] = resolution
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

    blockers = len(invalid_scope) + len(unresolved) + len(validation_blockers)
    coverage = round((len(resolved) / len(students)) * 100, 2) if students else 0
    evidence = [
        {
            "type": "PROGRAM_COVERAGE",
            "enrolledStudents": len(students),
            "archivedGraduates": sum(student.id in archived_ids for student in students),
            "resolvedStudents": len(resolved),
            "outOfScopeStudents": out_of_scope,
            "invalidScopeStudents": len(invalid_scope),
            "coveragePercent": coverage,
            "programIds": [str(value) for value in program_ids],
        },
        *invalid_scope[:30],
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
            f"本学期学生方案覆盖率100%，{len(program_ids)}个生效方案均无BLOCKER"
            if blockers == 0 and coverage == 100
            else f"方案覆盖率{coverage}%，范围异常{len(invalid_scope)}人，未解析学生{len(unresolved)}人，方案BLOCKER {len(validation_blockers)}项"
        ),
        evidence=evidence,
    )


def _expected_opening(db, term, *, college_ids=None, major_ids=None, cache=None):
    """按班级和学期结束时点解析唯一方案，再投影应开课程。"""
    from app.models import AaCourse, AaProgramCourse, SchoolClass

    cache = cache if cache is not None else {}
    classes_key = ("OPENING_CLASSES", _tid(), tuple(sorted(major_ids)) if major_ids is not None else None)
    if classes_key not in cache:
        query = db.query(SchoolClass).filter(
            SchoolClass.tenant_id == _tid(), SchoolClass.class_status == "NORMAL",
            SchoolClass.is_deleted.is_(False),
        )
        if major_ids is not None:
            query = query.filter(SchoolClass.major_id.in_(major_ids))
        cache[classes_key] = query.all()
    classes = cache[classes_key]
    # 应开需求来自所有学生班级；承担教学的学院由课程开课单位确定。
    # 按学生归属先删班级会丢失跨院授课需求，且 SchoolClass 本身没有 college_id。
    allowed_colleges = set(college_ids) if college_ids is not None else None
    expected = []
    structural = []
    replay_as_of = getattr(term, "end_date", None)
    course_cache = cache.setdefault(("OPENING_COURSES", _tid()), {})
    owner_cache = cache.setdefault(("OPENING_OWNERS", _tid()), {})
    for clazz in classes:
        grade = str(getattr(clazz, "grade", None) or "").strip()
        scope = cohort_term_scope(term.year_code, term.term_no, grade)
        if scope["state"] == "OUT_OF_SCOPE":
            continue
        if scope["state"] == "INVALID":
            if allowed_colleges is not None:
                continue  # 无法归属开课单位的基础治理异常只进入学校门禁。
            structural.append({
                "type": "TERM_UNRESOLVED", "reason": "INVALID_COHORT_TERM_SCOPE",
                "classId": str(clazz.id), "gradeYear": grade,
            })
            continue
        resolution_key = ("OPENING_PROGRAM", _tid(), int(clazz.id), replay_as_of)
        if resolution_key not in cache:
            cache[resolution_key] = resolve_program_for_scope(db, tenant_id=_tid(),
                major_id=getattr(clazz, "major_id", None), grade_year=grade,
                class_id=int(clazz.id), as_of=replay_as_of)
        resolution = cache[resolution_key]
        if resolution.status != "RESOLVED" or not resolution.program:
            if allowed_colleges is not None:
                continue
            structural.append({
                "type": "PROGRAM_UNRESOLVED",
                "reason": resolution.rule,
                "message": resolution.message,
                "classId": str(clazz.id),
                "gradeYear": grade,
            })
            continue
        program = resolution.program
        plan_term = int(scope["planTerm"])
        course_key = (int(program.id), plan_term)
        courses = course_cache.get(course_key)
        if courses is None:
            courses = db.query(AaProgramCourse).filter(
                AaProgramCourse.tenant_id == _tid(),
                AaProgramCourse.program_id == int(program.id),
                AaProgramCourse.open_term_no == plan_term,
                AaProgramCourse.is_deleted.is_(False),
            ).all()
            course_cache[course_key] = courses
        if allowed_colleges is not None:
            course_ids = {int(row.course_id) for row in courses if row.course_id and int(row.course_id) not in owner_cache}
            if course_ids:
                # 未找到的课程也缓存为空；同一请求不为每个学院重复查缺失数据。
                owner_cache.update({course_id: None for course_id in course_ids})
                owners = db.query(AaCourse).filter(
                    AaCourse.tenant_id == _tid(), AaCourse.id.in_(course_ids),
                    AaCourse.is_deleted.is_(False),
                ).all()
                owner_cache.update({int(row.id): row.owner_college_id for row in owners})
        for course in courses:
            if not course.course_id:
                if allowed_colleges is not None:
                    continue
                structural.append({
                    "type": "COURSE_UNRESOLVED", "programId": str(program.id),
                    "programCourseId": str(course.id), "classId": str(clazz.id),
                })
                continue
            if allowed_colleges is not None:
                owner = owner_cache.get(int(course.course_id))
                if owner is None:
                    continue
                if int(owner) not in allowed_colleges:
                    continue
            expected.append({
                "key": (int(course.course_id), int(clazz.id)),
                "programId": str(program.id),
                "programCourseId": str(course.id),
                "courseId": str(course.course_id),
                "classId": str(clazz.id),
            })
    return expected, structural


def _major_scope_subqueries(major_ids):
    from sqlalchemy import select
    from app.models import AaProgram, AaProgramCourse, SchoolClass
    classes = select(SchoolClass.id).where(SchoolClass.tenant_id == _tid(),
        SchoolClass.major_id.in_(major_ids), SchoolClass.is_deleted.is_(False))
    courses = select(AaProgramCourse.id).join(AaProgram,
        (AaProgram.id == AaProgramCourse.program_id) & (AaProgram.tenant_id == _tid())
        & AaProgram.is_deleted.is_(False)).where(AaProgramCourse.tenant_id == _tid(),
        AaProgramCourse.is_deleted.is_(False), AaProgram.major_id.in_(major_ids))
    return classes, courses


def _major_task_condition(major_ids):
    """行政班、独立成班来源及同批同课合班成员均可证明本专业需求。"""
    from sqlalchemy import or_, select
    from sqlalchemy.orm import aliased
    from app.models import AaTeachingTask
    classes, courses = _major_scope_subqueries(major_ids)
    def direct(model):
        return or_(model.class_id.in_(classes),
            model.class_id.is_(None) & model.source_program_course_id.in_(courses))
    member = aliased(AaTeachingTask)
    merged_member = select(member.id).where(member.tenant_id == _tid(), member.is_deleted.is_(False),
        member.status == "MERGED", member.merged_into_id == AaTeachingTask.id,
        member.batch_id == AaTeachingTask.batch_id, member.course_id == AaTeachingTask.course_id,
        direct(member)).exists()
    return or_(direct(AaTeachingTask), merged_member)


def _pending_teacher_count(tasks):
    return sum(not str(task.teacher_key or "").strip()
        or task.status in {"PENDING_ASSIGN", "ASSIGNED", "REJECTED_BY_TEACHER"} for task in tasks)


def evaluate_teaching_task(db, term_id, *, college_ids=None, major_ids=None, cache=None) -> dict:
    from sqlalchemy import select
    from app.models import AaCourse, AaTeachingClass, AaTeachingTask, AaTeachingTaskBatch, AaTerm

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
    if college_ids is not None:
        batch_query = batch_query.filter(AaTeachingTaskBatch.college_id.in_(list(college_ids)))
    if major_ids is not None:
        batch_query = batch_query.filter(AaTeachingTaskBatch.id.in_(select(AaTeachingTask.batch_id).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.status != "MERGED", _major_task_condition(major_ids))))
    batches = batch_query.all()
    batch_ids = [int(row.id) for row in batches]
    task_query = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(batch_ids or [0]),
        AaTeachingTask.status != "MERGED",
        AaTeachingTask.is_deleted.is_(False),
    )
    if major_ids is not None:
        task_query = task_query.filter(_major_task_condition(major_ids))
    tasks = task_query.all()

    expected, structural = _expected_opening(db, term, college_ids=college_ids, major_ids=major_ids, cache=cache)
    expected_counter = Counter(item["key"] for item in expected)
    actual_map = defaultdict(list)
    members = defaultdict(list)
    visible_classes, visible_sources = None, None
    from sqlalchemy.orm import aliased
    survivor = aliased(AaTeachingTask)
    merged = db.query(AaTeachingTask).join(survivor,
        (survivor.id == AaTeachingTask.merged_into_id) & (survivor.tenant_id == _tid())
        & survivor.is_deleted.is_(False) & (survivor.batch_id == AaTeachingTask.batch_id)
        & (survivor.course_id == AaTeachingTask.course_id)).filter(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.status == "MERGED", survivor.id.in_([task.id for task in tasks])).all()
    for member in merged:
        members[int(member.merged_into_id)].append(member)
    if major_ids is not None:
        classes, sources = _major_scope_subqueries(major_ids)
        visible_classes, visible_sources = set(db.scalars(classes)), set(db.scalars(sources))
    inspect_formal = tasks if major_ids is not None else [task for task in tasks
        if not task.class_id or members.get(int(task.id))]
    formal_ids = set()
    if inspect_formal:
        formal = db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == _tid(), AaTeachingClass.term_id == int(term_id),
            AaTeachingClass.teaching_task_id.in_([task.id for task in inspect_formal]),
            AaTeachingClass.status == "ACTIVE", AaTeachingClass.is_deleted.is_(False),
        ).all()
        formal_ids = {(int(row.teaching_task_id), int(row.course_id)) for row in formal}
    if major_ids is not None:
        structural += [{"type": "TEACHING_CLASS_UNRESOLVED", "taskId": str(task.id)}
                       for task in tasks if (int(task.id), int(task.course_id)) not in formal_ids]
    if (college_ids is not None or major_ids is not None) and tasks:
        courses = db.query(AaCourse).filter(AaCourse.tenant_id == _tid(),
            AaCourse.id.in_({task.course_id for task in tasks}), AaCourse.is_deleted.is_(False)).all()
        owners = {int(row.id): row.owner_college_id for row in courses}
        structural += [{"type": "OFFERING_UNIT_UNRESOLVED", "taskId": str(task.id)}
                       for task in tasks if not owners.get(int(task.course_id))]
    for task in tasks:
        for source in [task, *members.get(int(task.id), [])]:
            if major_ids is not None and (source.class_id not in visible_classes if source.class_id
                    else source.source_program_course_id not in visible_sources):
                continue  # 合班承接其他专业时，不能把外专业原班级混入本专业对账。
            if source.class_id:
                actual_map[(int(source.course_id), int(source.class_id))].append(task)
                continue
            # 非行政班课程必须有正式教学班和精确方案课程来源；不得补造行政班。
            valid = (int(task.id), int(task.course_id)) in formal_ids and source.formation_mode in {
                "SELECTABLE", "MERGED", "RETAKE", "LAYERED"}
            matches = [item for item in expected if item["courseId"] == str(source.course_id)
                       and item["programCourseId"] == str(source.source_program_course_id)] if valid else []
            if not matches:
                structural.append({"type": "TASK_PROVENANCE_UNRESOLVED", "taskId": str(task.id),
                    "reason": "正式教学班或方案课程来源不足，无法核验应开责任"})
                continue
            for item in matches:
                actual_map[item["key"]].append(task)

    missing = [item for item in expected if not actual_map.get(item["key"])]
    duplicate = [
        {"type": "DUPLICATE_TASK", "courseId": str(key[0]), "classId": str(key[1]),
         "taskIds": [str(row.id) for row in rows]}
        for key, rows in actual_map.items() if len(rows) > expected_counter.get(key, 0) and expected_counter.get(key, 0) > 0
        and any(row.class_id for row in rows)
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
        {"type": "TASK_RECONCILIATION", "expected": len(expected), "actual": len(tasks),
         "pendingTeacherCount": _pending_teacher_count(tasks)},
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
    if college_ids is not None:
        from .academic_affairs_archive_operational_policy import college_task_ids, college_schedule_batch_condition
        own_tasks = college_task_ids(db, college_ids, term_id)
        batch_query = batch_query.filter(college_schedule_batch_condition(db, college_ids, term_id))
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
    item_query = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(formal_ids or [0]),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    )
    if college_ids is not None:
        item_query = item_query.filter(AaScheduleItem.task_id.in_(own_tasks))
    items = item_query.all()

    task_batches = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term_id),
        AaTeachingTaskBatch.status.in_(["APPROVED", "ARCHIVED"]),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).all()
    task_batch_ids = [int(row.id) for row in task_batches]
    task_query = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids or [0]),
        AaTeachingTask.status == "READY",
        AaTeachingTask.no_auto_schedule.is_(False),
        AaTeachingTask.is_deleted.is_(False),
    )
    if college_ids is not None:
        task_query = task_query.filter(AaTeachingTask.id.in_(own_tasks))
    tasks = task_query.all()
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


def _missing_grade_task_ids(db, term_id, college_ids=None):
    """与学期责任流一致：本学期 READY 授课任务都应有同学期成绩任务。"""
    from sqlalchemy import func, select
    from app.models import AaCourse, AaGradeTask, AaTeachingTask, AaTeachingTaskBatch

    has_grade = select(AaGradeTask.id).where(
        AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False),
        AaGradeTask.term_id == int(term_id), AaGradeTask.teaching_task_id == AaTeachingTask.id,
    ).exists()
    missing = select(AaTeachingTask.id).join(AaTeachingTaskBatch,
        AaTeachingTaskBatch.id == AaTeachingTask.batch_id).join(AaCourse,
        AaCourse.id == AaTeachingTask.course_id).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.status == "READY",
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.is_deleted.is_(False),
        AaTeachingTaskBatch.term_id == int(term_id),
        AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False), ~has_grade,
    )
    if college_ids is not None:
        allowed = sorted({int(value) for value in college_ids})
        if not allowed:
            return 0, []
        missing = missing.where(func.coalesce(
            AaCourse.owner_college_id, AaTeachingTaskBatch.college_id).in_(allowed))
    missing = missing.subquery()
    count = int(db.scalar(select(func.count()).select_from(missing)) or 0)
    sample = [str(value) for value in db.scalars(
        select(missing.c.id).order_by(missing.c.id).limit(50)).all()]
    return count, sample


def evaluate_grade(db, term_code, previous_result: dict, *, college_ids=None, term_id=None) -> dict:
    from app.models import AaGradeRecheck, AaGradeRecord, AaGradeTask, AcademicGrade, WorkflowInstance

    task_query = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False),
    )
    if term_code:
        task_query = task_query.filter(AaGradeTask.term_code == term_code)
    if college_ids is not None:
        from sqlalchemy import select
        from .academic_affairs_archive_operational_policy import college_task_ids
        task_query = task_query.filter(AaGradeTask.teaching_task_id.in_(college_task_ids(db, college_ids)))
        own_grade_tasks = task_query.with_entities(AaGradeTask.id).subquery()
        own_grade_ids = select(AaGradeRecord.acad_grade_id).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.is_deleted.is_(False),
            AaGradeRecord.task_id.in_(select(own_grade_tasks.c.id)))
    tasks = task_query.all()
    unfinished = [row for row in tasks if str(row.status or "").upper() not in {"PUBLISHED", "ARCHIVED"}]
    missing_count, missing_ids = _missing_grade_task_ids(db, term_id, college_ids) if term_id else (0, [])

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
    if college_ids is not None:
        recheck_query = recheck_query.filter(AcademicGrade.id.in_(own_grade_ids))
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
    if college_ids is not None:
        change_query = change_query.filter(AaGradeTask.id.in_(select(own_grade_tasks.c.id)))
    active_changes = int(change_query.count() or 0)

    blockers = len(unfinished) + missing_count + active_rechecks + active_changes + (1 if not tasks and not missing_count else 0)
    base = normalize_legacy_result("GRADE", previous_result)
    evidence = [{
        "type": "GRADE_CLOSURE",
        "taskCount": len(tasks),
        "missingGradeTaskCount": missing_count,
        "missingGradeTaskIds": missing_ids,
        "unpublishedTaskIds": [str(row.id) for row in unfinished[:50]],
        "activeRechecks": active_rechecks,
        "activeChanges": active_changes,
        "baseSummary": base["summary"],
    }]
    rule_code = (
        "GRADE_TASK_NOT_CREATED" if missing_count else
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
            else f"成绩阻断{blockers}项：未建任务{missing_count}、未发布任务{len(unfinished)}、在途复查{active_rechecks}、在途更正{active_changes}"
        ),
        evidence=evidence,
    )


def evaluate_first_batch(db, term_id, term_code, previous: dict, *, college_ids=None) -> dict:
    from app.models import AaTerm

    results = {code: normalize_legacy_result(code, value) for code, value in (previous or {}).items()}
    term = None
    if term_id:
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
    results["PROGRAM"] = evaluate_program(db, term=term, college_ids=college_ids)
    results["TEACHING_TASK"] = evaluate_teaching_task(db, term_id, college_ids=college_ids)
    results["SCHEDULE"] = evaluate_schedule(
        db, term_id, results.get("SCHEDULE") or {}, college_ids=college_ids,
    )
    results["GRADE"] = evaluate_grade(db, term_code, results.get("GRADE") or {}, term_id=term_id)
    return results
