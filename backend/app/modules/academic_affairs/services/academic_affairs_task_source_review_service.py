"""范围内的任务来源核对；只读证据不等于来源承接确认。"""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from .academic_affairs_task_formation_policy import normalize_formation_mode

_MODE_LABELS = {"ADMIN_FIXED": "固定行政班", "SELECTABLE": "学生选课形成",
    "MERGED": "合班形成", "RETAKE": "重修形成", "LAYERED": "分层形成"}


def _check(code, label, passed, success, blocked):
    return {"code": code, "label": label, "status": "PASS" if passed else "BLOCKED",
        "message": success if passed else blocked}


def _mode(value):
    try:
        return normalize_formation_mode(value)
    except ValueError:
        return None


def _teacher_identity(db, key, stored_id):
    from .academic_affairs_teaching_class_teacher_service import _teacher
    try:
        teacher = _teacher(db, key or "")
    except AppException:
        return None
    # 空旧投影可以通过稳定教师键证明身份；非空矛盾编号不能被忽略。
    if stored_id is not None and int(stored_id) != int(teacher.id):
        return None
    return int(teacher.id)


def _projection(db, task, term):
    from app.models import (AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingClassTeacher)
    clazz = db.scalar(select(AaTeachingClass).where(AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id == task.id, AaTeachingClass.is_deleted.is_(False)))
    if not clazz:
        return {"class": None, "roster": None, "teacher": None, "initial": False, "count": None}
    current = db.scalar(select(AaTeachingClassRosterVersion).where(
        AaTeachingClassRosterVersion.tenant_id == _tid(),
        AaTeachingClassRosterVersion.teaching_class_id == clazz.id,
        AaTeachingClassRosterVersion.id == clazz.current_roster_version_id,
        AaTeachingClassRosterVersion.is_deleted.is_(False)))
    members = db.scalars(select(AaTeachingClassMember).where(
        AaTeachingClassMember.tenant_id == _tid(), AaTeachingClassMember.teaching_class_id == clazz.id,
        AaTeachingClassMember.roster_version_id == clazz.current_roster_version_id,
        AaTeachingClassMember.is_deleted.is_(False), AaTeachingClassMember.status == "ACTIVE",
    ).order_by(AaTeachingClassMember.id).limit(10001)).all()
    valid = bool(current and clazz.status == "ACTIVE" and clazz.roster_status == "LOCKED"
        and clazz.course_id == task.course_id and clazz.term_id == term.id
        and clazz.source_type == "TEACHING_TASK" and clazz.source_id == task.id
        and clazz.class_type == "ADMIN" and current.source_type == "ADMIN_CLASS"
        and current.source_id == task.class_id
        and current.status == "LOCKED" and current.version_no == clazz.current_roster_version_no
        and len(members) <= 10000 and len(members) == current.member_count
        and all(member.source_type == "ADMIN_CLASS" and member.source_id == task.class_id for member in members))
    roster = frozenset(int(member.student_id) for member in members) if valid else None
    if roster is not None and len(roster) != len(members):
        roster = None
    if valid and roster is not None:
        from .academic_affairs_teaching_class_service import resolve_teaching_task_roster
        from .academic_affairs_teaching_class_core_service import _roster_hash
        # 比较编号不能证明名单可用于实际教学；沿同一只读权威核验有效学生主档。
        authoritative = resolve_teaching_task_roster(db, task.id)
        valid = bool(authoritative.get("ready")
            and authoritative.get("teachingClassId") == str(clazz.id)
            and authoritative.get("rosterVersionId") == str(current.id)
            and frozenset(int(pk) for pk in authoritative.get("studentIds", [])) == roster
            and current.roster_hash == _roster_hash(roster))
    if not valid:
        roster = None
    version_count = db.scalar(select(func.count()).select_from(AaTeachingClassRosterVersion).where(
        AaTeachingClassRosterVersion.tenant_id == _tid(), AaTeachingClassRosterVersion.teaching_class_id == clazz.id))
    initial = bool(valid and version_count == 1 and clazz.class_type == "ADMIN"
        and clazz.source_type == "TEACHING_TASK" and clazz.source_id == task.id
        and current.version_no == 1 and current.source_type == "ADMIN_CLASS"
        and current.source_id == task.class_id)
    from app.models import AffairsAuditTrail
    adjusted = db.scalar(select(AffairsAuditTrail.id).where(AffairsAuditTrail.tenant_id == _tid(),
        AffairsAuditTrail.biz_type == "AA_TEACHING_CLASS_TEACHER", AffairsAuditTrail.biz_id == clazz.id,
        AffairsAuditTrail.action.in_(("TEACHER_RELATION_CREATE", "TEACHER_RELATION_UPDATE", "TEACHER_RELATION_DEACTIVATE")),
    ).limit(1)) is not None
    initial = initial and not adjusted
    relations = db.scalars(select(AaTeachingClassTeacher).where(
        AaTeachingClassTeacher.tenant_id == _tid(), AaTeachingClassTeacher.teaching_class_id == clazz.id,
        AaTeachingClassTeacher.status == "ACTIVE", AaTeachingClassTeacher.is_deleted.is_(False),
    ).order_by(AaTeachingClassTeacher.id).limit(101)).all()
    signature = []
    task_teacher = _teacher_identity(db, task.teacher_key, task.teacher_id)
    valid_teachers = bool(task_teacher and relations and len(relations) <= 100)
    from .academic_affairs_teaching_class_teacher_service import _validate_topology
    try:
        _validate_topology(task, term, relations)
    except AppException:
        valid_teachers = False
    primary = 0
    for relation in relations:
        identity = _teacher_identity(db, relation.teacher_key, relation.teacher_id)
        start = task.start_week if relation.start_week is None else relation.start_week
        end = task.end_week if relation.end_week is None else relation.end_week
        if (not identity or start is None or end is None or task.start_week is None
                or task.end_week is None or not task.start_week <= start <= end <= task.end_week):
            valid_teachers = False
        if relation.role_type == "PRIMARY":
            primary += 1
            valid_teachers = valid_teachers and identity == task_teacher
        signature.append((identity, relation.role_type, start, end))
    valid_teachers = valid_teachers and primary == 1
    return {"class": clazz, "roster": roster, "teacher": tuple(sorted(signature)) if valid_teachers else None,
        "initial": initial, "count": len(members) if valid else None}


def _lineage(db, first, second):
    """只接受同一系列内明确的前版本链；不依赖名称或数字大小猜承接方向。"""
    from app.models import AaProgram
    if (not first or not second or not first.series_key or first.series_key != second.series_key
            or first.major_id != second.major_id or first.grade_year != second.grade_year):
        return None
    ancestors = []
    for program in (first, second):
        seen = {int(program.id)}
        row = program
        for _ in range(32):
            previous_id = row.prev_version_id
            if not previous_id:
                break
            if int(previous_id) in seen:
                return None
            seen.add(int(previous_id))
            row = db.scalar(select(AaProgram).where(AaProgram.tenant_id == _tid(),
                AaProgram.id == previous_id, AaProgram.is_deleted.is_(False)))
            if (not row or row.series_key != first.series_key or row.major_id != first.major_id
                    or row.grade_year != first.grade_year):
                return None
        else:
            return None
        ancestors.append(seen)
    if first.id != second.id:
        if first.id in ancestors[1]:
            return int(second.id)
        if second.id in ancestors[0]:
            return int(first.id)
    return None


def _consumption(db, task_id, projection):
    from app.models import (AaAttendanceSession, AaEvaluationResult, AaEvaluationTask,
        AaExamCourse, AaGradeTask, AaRosterConsumerSnapshot, AaScheduleChange, AaScheduleItem,
        AaRetakeApply, AaSelectionCourse, AaTextbookSelection)
    references = (
        (AaScheduleItem, "task_id", "课表"), (AaSelectionCourse, "teaching_task_id", "选课供给"),
        (AaGradeTask, "teaching_task_id", "成绩"), (AaScheduleChange, "task_id", "调停补课"),
        (AaExamCourse, "teaching_task_id", "考试"), (AaTextbookSelection, "task_id", "教材"),
        (AaEvaluationTask, "teaching_task_id", "评教任务"), (AaEvaluationResult, "teaching_task_id", "评教结果"),
        (AaAttendanceSession, "teaching_task_id", "课堂考勤"),
        (AaRetakeApply, "teaching_task_ref", "重修编班"),
    )
    labels = []
    for model, column, label in references:
        # 历史引用也证明曾被消费；不把逻辑删除当成可自动承接的空白。
        if db.scalar(select(model.id).where(model.tenant_id == _tid(),
                getattr(model, column) == task_id).limit(1)) is not None:
            labels.append(label)
    clazz = projection["class"]
    if clazz and db.scalar(select(AaRosterConsumerSnapshot.id).where(
            AaRosterConsumerSnapshot.tenant_id == _tid(),
            AaRosterConsumerSnapshot.teaching_class_id == clazz.id).limit(1)) is not None:
        labels.append("正式名单消费")
    return labels


def get_source_review(task_id, other_task_id, user, *, db=None):
    from app.models import AaProgram, AaProgramCourse, AaTeachingTaskBatch, AaTerm, SchoolClass
    from .academic_affairs_task_service import _ensure_task_visible
    from .academic_affairs_task_formation_provenance_service import resolve_task_formation_snapshot
    from .academic_affairs_archive_service import guard_term_writable

    if int(task_id) == int(other_task_id):
        raise AppException("VALIDATION_ERROR", "请选择两条不同的教学任务进行核对")
    with (session() if db is None else nullcontext(db)) as db:
        # 先对双方独立裁决原有范围，再读取来源、名单与教师；拒绝不能泄露另一院事实。
        tasks = [_ensure_task_visible(db, int(pk), user)[0] for pk in (task_id, other_task_id)]
        batches = [db.scalar(select(AaTeachingTaskBatch).where(AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.id == task.batch_id, AaTeachingTaskBatch.is_deleted.is_(False))) for task in tasks]
        if any(batch is None for batch in batches):
            raise not_found("教学任务来源批次不存在")
        term = db.scalar(select(AaTerm).where(AaTerm.tenant_id == _tid(),
            AaTerm.id == batches[0].term_id, AaTerm.is_deleted.is_(False)))
        if not term:
            raise not_found("学期不存在")
        checks = []
        def add(code, label, passed, success, blocked):
            checks.append(_check(code, label, passed, success, blocked))
        same = (batches[0].term_id == batches[1].term_id and tasks[0].course_id == tasks[1].course_id
            and tasks[0].class_id is not None and tasks[0].class_id == tasks[1].class_id)
        add("OBJECT", "学期、课程与行政班", same, "两条任务属于同一学期、课程和行政班。", "学期、课程或行政班不同，不能按重复来源承接。")
        add("RESPONSIBILITY_SCOPE", "原任务与后继任务责任学院", batches[0].college_id == batches[1].college_id,
            "两条任务的责任学院一致。", "责任学院不同，不能通过来源承接转移学院办理范围。")
        writable = True
        try:
            guard_term_writable(db, term.id)
        except AppException:
            writable = False
        add("STATE", "当前办理阶段", writable and all(task.status == "READY" and not task.is_merged
            and not task.merged_into_id for task in tasks) and all(batch.status == "APPROVED" for batch in batches),
            "学期可办理，两条任务均已完成学校终审。", "学期已封存，或任务尚未终审、已经合班，不能按已批准来源承接。")
        sources = [db.scalar(select(AaProgramCourse).where(AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.id == task.source_program_course_id, AaProgramCourse.is_deleted.is_(False))) for task in tasks]
        programs = [db.scalar(select(AaProgram).where(AaProgram.tenant_id == _tid(),
            AaProgram.id == source.program_id, AaProgram.is_deleted.is_(False))) if source else None for source in sources]
        successor_program_id = _lineage(db, *programs)
        add("LINEAGE", "培养方案前后版本", bool(successor_program_id),
            "存在同一方案系列的明确前后版本关系。", "缺少有效的方案前后版本关系，不能根据编号或名称选择原任务。")
        from .academic_affairs_program_activation_service import resolve_program_for_scope
        school_class = db.scalar(select(SchoolClass).where(SchoolClass.tenant_id == _tid(),
            SchoolClass.id == tasks[0].class_id, SchoolClass.is_deleted.is_(False)))
        binding = resolve_program_for_scope(db, tenant_id=_tid(), major_id=school_class.major_id,
            grade_year=school_class.grade, class_id=school_class.id) if school_class else None
        add("BINDING", "当前班级适用方案", bool(binding and binding.status == "RESOLVED"
            and binding.program.id == successor_program_id), "当前班级唯一适用方案为明确的后继版本。",
            "当前班级适用方案缺失、冲突或不是后继版本，须先核实方案绑定。")
        proven = [resolve_task_formation_snapshot(db, task.id, tenant_id=_tid()) for task in tasks]
        modes = [item["formationMode"] for item in proven]
        add("FORMATION", "课程形成方式与原始来源", all(item["status"] == "PROVEN" for item in proven)
            and modes[0] == modes[1], "原始来源均已证明，课程形成方式一致。",
            "形成方式来源尚未证明或不一致；空值不能认定为相同，须先由责任人员核实来源依据。")
        credit_match = bool(all(source is not None and source.course_id == task.course_id
            and source.credit_snapshot is not None and source.open_term_no is not None
            for source, task in zip(sources, tasks)))
        credit_match = credit_match and sources[0].credit_snapshot == sources[1].credit_snapshot and sources[0].open_term_no == sources[1].open_term_no
        add("CREDIT", "方案学分与开课序号", credit_match, "两份来源的学分和开课序号一致。", "来源学分、开课序号缺失或不一致，不能自动变更课程要求。")
        fields = ("weekly_hours", "total_hours", "start_week", "end_week")
        valid_hours = all(all(getattr(task, field) is not None and getattr(task, field) > 0 for field in fields)
            and task.start_week <= task.end_week <= int(term.teaching_weeks or 0) for task in tasks)
        add("HOURS", "计划学时与起止周", valid_hours and all(getattr(tasks[0], field) == getattr(tasks[1], field) for field in fields),
            "总学时、周学时和起止周一致。", "计划学时或起止周缺失、不合法或不一致，不能自动改写教学计划。")
        scheduling_fields = ("no_auto_schedule", "required_room_type", "expected_students")
        add("SCHEDULING_REQUIREMENTS", "排课参与与资源要求",
            all(getattr(tasks[0], field) == getattr(tasks[1], field) for field in scheduling_fields),
            "是否参与排课、教室类型和预计人数一致。", "排课参与或资源要求不同，须核实原计划，不能自动选择一份要求。")
        projections = [_projection(db, task, term) for task in tasks]
        add("TEACHER", "教师身份与正式任课关系", projections[0]["teacher"] is not None
            and projections[0]["teacher"] == projections[1]["teacher"],
            "稳定教师标识解析为同一有效教师，正式任课角色与周窗一致；缺失旧编号未被补写。",
            "教师账号、任务快照或正式任课关系尚未证明一致，不能自动换教师。")
        add("ROSTER", "正式教学班与当前名单", projections[0]["roster"] is not None
            and projections[0]["roster"] == projections[1]["roster"],
            "两份锁定名单的学生集合一致；未返回学生个人明细。", "教学班或锁定名单缺失、不完整、过大或学生集合不同，不能自动调整名单。")
        successor_index = next((index for index, program in enumerate(programs)
            if program and program.id == successor_program_id), None)
        untouched = successor_index is not None and projections[successor_index]["initial"]
        add("SUCCESSOR_PROJECTION", "后继任务初始投影", untouched,
            "后继教学班保留初始行政班名单投影，未发现正式任课调整审计。",
            "无法证明后继任务只保留未调整的初始自动投影；任课人工调整历史也不能被当前值掩盖。")
        consumed = _consumption(db, tasks[successor_index].id, projections[successor_index]) if successor_index is not None else []
        add("SUCCESSOR_CONSUMPTION", "后继任务正式业务引用", successor_index is not None and not consumed,
            "已检查的课表、选课、成绩、考勤、考务及正式名单消费未发现后继引用。",
            "后继任务已有正式业务引用：" + "、".join(consumed) if consumed else "来源方向未证明，无法判定哪条任务可被承接。")
        from .academic_affairs_task_execution_authority import load_execution_handoffs
        handoffs = load_execution_handoffs(db, [task.id for task in tasks])
        add("EXECUTION_HANDOFF", "独立执行关系", not handoffs,
            "两条任务尚未建立来源承接关系。", "任务已有承接关系，不能再次选择为新的独立承接原任务。")
        from app.models import AaTeachingTaskSourceHandoff
        successor_is_anchor = successor_index is not None and db.scalar(select(AaTeachingTaskSourceHandoff.id).where(
            AaTeachingTaskSourceHandoff.tenant_id == _tid(),
            AaTeachingTaskSourceHandoff.execution_task_id == tasks[successor_index].id).limit(1)) is not None
        add("SUCCESSOR_EXECUTION", "后继是否已承担其他来源执行", not successor_is_anchor,
            "后继任务未承担其他来源的教学执行。", "后继任务已是其他来源的执行原任务，不能改变已有执行链。")
        output = []
        for task, source, program, projection, proof in zip(tasks, sources, programs, projections, proven):
            output.append({"taskId": str(task.id), "batchId": str(task.batch_id), "courseName": task.course_name or "待核对课程",
                "teachingClassName": task.teaching_class_name or "待核对教学班", "sourceProgramId": str(program.id) if program else "",
                "sourceProgramName": program.program_name if program else "来源方案未证明",
                "sourceProgramVersion": program.version if program else None,
                "sourceRelationLabel": ("后继方案版本" if program.id == successor_program_id else "原方案版本")
                    if program and successor_program_id else "版本关系待核对",
                "sourceProgramCourseId": str(source.id) if source else "",
                "formationProofLabel": ("历史依据已正式确认" if proof.get("proofId") else "原方案课程明确记录")
                    if proof["status"] == "PROVEN" else "来源尚未证明",
                "formationModeLabel": _MODE_LABELS.get(proof["formationMode"], "来源未证明")
                    if proof["status"] == "PROVEN"
                    else "任务：" + _MODE_LABELS.get(_mode(task.formation_mode), "来源未证明")
                        + "；方案来源：" + _MODE_LABELS.get(_mode(source.formation_mode) if source else None, "来源未证明"),
                "credit": str(source.credit_snapshot) if source and source.credit_snapshot is not None else None,
                "openTermNo": source.open_term_no if source else None, "weeklyHours": task.weekly_hours,
                "totalHours": task.total_hours, "startWeek": task.start_week, "endWeek": task.end_week,
                "teacherName": task.teacher_name or "待核对教师", "teacherIdentityProven": projection["teacher"] is not None,
                "rosterCount": projection["count"]})
        blocked = any(check["status"] != "PASS" for check in checks)
        # 展示保留打开顺序；签核依据固定为原执行→后继，反向入口不产生假冲突。
        fingerprint_order = ([1 - successor_index, successor_index] if successor_index is not None
            else sorted(range(len(tasks)), key=lambda index: tasks[index].id))
        fingerprint = hashlib.sha256(json.dumps({
            "term": [term.id, term.status, term.teaching_weeks],
            "tasks": [output[index] for index in fingerprint_order], "checks": checks,
            "versions": [tasks[index].version for index in fingerprint_order],
            "schedulingRequirements": [[getattr(tasks[index], field) for field in scheduling_fields] for index in fingerprint_order],
            "programs": [[program.id, program.version, program.prev_version_id, program.status]
                if (program := programs[index]) else None for index in fingerprint_order],
            "rosters": [sorted(projections[index]["roster"]) if projections[index]["roster"] is not None else None
                for index in fingerprint_order],
            "teachers": [projections[index]["teacher"] for index in fingerprint_order],
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
        execution_id = str(tasks[1 - successor_index].id) if successor_index is not None else None
        successor_id = str(tasks[successor_index].id) if successor_index is not None else None
        confirmed = handoffs.get(int(successor_id)) if successor_id else None
        if confirmed and str(confirmed.execution_task_id) != execution_id:
            confirmed = None
        from .academic_affairs_task_source_handoff_service import _receipt, _responsible
        responsible = False
        try:
            _responsible(db, user)
            responsible = True
        except AppException as exc:
            if exc.http_status not in (401, 403):
                raise
        allowed = not blocked and responsible and confirmed is None
        action_reason = ("已确认由原任务承接，可回读原任务继续排课。" if confirmed else
            "请先核实所有阻断项，再由校教务责任人员确认。" if blocked else
            "由校教务责任人员填写依据说明后确认。" if responsible else
            "核对已完成，请交有效校教务责任人员确认承接。")
        return {"termId": str(term.id), "taskIds": [str(task.id) for task in tasks], "tasks": output, "checks": checks,
            "sourceFingerprint": fingerprint,
            "executionTaskId": execution_id, "successorTaskId": successor_id,
            "handoffAction": {"allowed": allowed, "reason": action_reason,
                "executionTaskId": execution_id, "successorTaskId": successor_id,
                "expectedSourceFingerprint": fingerprint},
            "confirmedHandoff": _receipt(confirmed) if confirmed else None,
            "status": "BLOCKED" if blocked else "CHECKED", "reviewOnly": True,
            "summary": _receipt(confirmed)["summary"] if confirmed else
                "来源核对存在待补依据，暂不能确认承接。" if blocked else "核对项一致；本次仅核对，尚未办理来源承接。",
            "nextStep": {"label": "回原教学任务继续排课与办理" if confirmed else
                "先核实阻断项的来源依据" if blocked else "交校教务核定来源承接",
                "description": "承接已确认，后继任务保留来源记录；正式课表、任课及历史沿原任务继续。" if confirmed else
                    "核对结果不会合并或改写任务；重复来源仍须完成正式承接后才能继续排课与发布。"}}
