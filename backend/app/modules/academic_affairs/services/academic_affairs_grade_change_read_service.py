"""AA-194: scoped, paged correction requests and exact application evidence.

This module projects existing correction/workflow/grade facts. Only the canonical
correction command writes decisions; a read-back is never a command receipt.
"""
from __future__ import annotations

from sqlalchemy import and_, false, func, or_, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.models import (
    AaGradeRecord, AaGradeTask, AaTeachingTask, AaTerm, AcademicGrade,
    StudentProfile, User, WorkflowInstance, WorkflowTask,
)
from app.models.academic_affairs_effective_grade import AaGradeChangeRequest, AaGradeCorrection
from app.models.academic_affairs_r10 import AaGradeComponentScore, AaGradeSchemeSnapshot
from app.services.db_service import _tid, session

from . import academic_affairs_grade_core_service as core
from . import academic_affairs_grade_correction_command as command
from . import academic_affairs_grade_task_read_service as task_read
from . import academic_affairs_grade_change_component_service as components
from . import academic_affairs_grade_change_authority_service as authority

APPLY = "academicAffairs.gradeChange.apply"
REVIEW = "academicAffairs.gradeChange.review"


def _visible(model):
    return (model.tenant_id == _tid(), model.is_deleted.is_(False))


def _id(value):
    return str(value) if value else None


def _iso(value):
    return value.isoformat() if value else None


def _access(db, user):
    apply = has_permission(user, APPLY)
    review = has_permission(user, REVIEW)
    if not (apply or review):
        raise no_permission("无成绩更正申请或审核权限")
    return command._current_user_id(db), build_affairs_context(user, db), apply, review


def _scope(db, user, access):
    _, ctx, apply, review = access
    branches = []
    if review:
        allowed = ctx.allowed_class_ids(db)
        branches.append(True if allowed is None else AaGradeTask.class_id.in_(sorted(allowed)))
    if apply:
        # Reuse the installed relation-first task reader, including effective
        # teacher windows. A historical GradeTask.teacher_key is not authority.
        ids = select(AaGradeTask.id).outerjoin(AaTeachingTask, and_(
            AaTeachingTask.id == AaGradeTask.teaching_task_id,
            *_visible(AaTeachingTask),
        )).where(*task_read._scope_conditions(db, user))
        # Scope-admin writers additionally use the actual data scope, not role
        # text alone. Teacher task scope remains the canonical relation scope.
        role = str((user or {}).get("currentRoleCode") or "").upper()
        if role in core._REVIEW_ROLES or role == "COLLEGE_ADMIN":
            allowed = ctx.allowed_class_ids(db)
            if allowed is not None:
                ids = ids.where(AaGradeTask.class_id.in_(sorted(allowed)))
        branches.append(AaGradeTask.id.in_(ids.correlate(None)))
    return or_(*branches) if branches else false()


def _query(db, user, access):
    return select(AaGradeChangeRequest, AaGradeTask, AaGradeRecord, WorkflowInstance, WorkflowTask).join(
        AaGradeTask, and_(AaGradeTask.id == AaGradeChangeRequest.grade_task_id, *_visible(AaGradeTask)),
    ).join(AaGradeRecord, and_(
        AaGradeRecord.id == AaGradeChangeRequest.grade_record_id,
        AaGradeRecord.task_id == AaGradeTask.id,
        AaGradeRecord.student_id == AaGradeChangeRequest.student_id, *_visible(AaGradeRecord),
    )).outerjoin(WorkflowInstance, and_(
        WorkflowInstance.id == AaGradeChangeRequest.workflow_instance_id,
        WorkflowInstance.source_module == "academic-affairs",
        WorkflowInstance.source_biz_type == "AA_GRADE_CHANGE",
        WorkflowInstance.source_biz_id == AaGradeRecord.id,
        WorkflowInstance.workflow_code == core._WF_CHANGE, *_visible(WorkflowInstance),
    )).outerjoin(WorkflowTask, and_(
        WorkflowTask.id == AaGradeChangeRequest.current_task_id,
        WorkflowTask.instance_id == WorkflowInstance.id, *_visible(WorkflowTask),
    )).where(*_visible(AaGradeChangeRequest), _scope(db, user, access))


def _by_id(db, model, ids):
    return {int(row.id): row for row in db.scalars(select(model).where(
        model.id.in_(sorted({int(value) for value in ids if value})), *_visible(model),
    )).all()} if any(ids) else {}


def _scores(record, prefix=""):
    return {key: getattr(record, prefix + attr) for key, attr in (
        ("usualScore", "usual_score"), ("midtermScore", "midterm_score"),
        ("finalScore", "final_score"), ("totalScore", "total_score"),
    )}


def _ratios(task):
    return {"usualRatio": task.usual_ratio, "midtermRatio": task.midterm_ratio, "finalRatio": task.final_ratio}


def _hydrate(db, rows, user, access):
    """Fetch evidence in bounded batches for the current SQL page, not per row."""
    if not rows:
        return []
    uid, ctx, _, review = access
    students = _by_id(db, StudentProfile, [r.student_id for r, *_ in rows])
    users = _by_id(db, User, [value for _, _, _, inst, wt in rows for value in (
        inst.applicant_id if inst else None, wt.assignee_id if wt else None,
    )])
    terms = _by_id(db, AaTerm, [task.term_id for _, task, *_ in rows])
    grades = _by_id(db, AcademicGrade, [record.acad_grade_id for _, _, record, *_ in rows])
    task_ids = {task.id for _, task, *_ in rows}
    dynamic_ids = set()
    for model in (AaGradeSchemeSnapshot, AaGradeComponentScore):
        dynamic_ids.update(db.scalars(select(model.grade_task_id).where(
            model.grade_task_id.in_(task_ids), *_visible(model),
        ).distinct()).all())
    corrections = {int(c.source_ref_id): c for c in db.scalars(select(AaGradeCorrection).where(
        AaGradeCorrection.source_type == "CHANGE_REQUEST",
        AaGradeCorrection.source_ref_id.in_([r.id for r, *_ in rows]), *_visible(AaGradeCorrection),
    )).all()}
    allowed_classes = ctx.allowed_class_ids(db) if review else set()
    result = []
    for request, task, record, inst, wt in rows:
        student = students.get(request.student_id)
        applicant = users.get(inst.applicant_id) if inst else None
        assignee = users.get(wt.assignee_id) if wt else None
        grade = grades.get(record.acad_grade_id)
        term = terms.get(task.term_id)
        dynamic = task.id in dynamic_ids or bool(request.score_snapshot_json)
        component_view = components.projection(db, task, record, request) if dynamic else {}
        fresh = bool(grade and grade.record_status == "ACTIVE"
                     and record.acad_grade_id == request.current_grade_id
                     and int(record.version_no or 1) == request.expected_grade_version
                     and _scores(record) == _scores(request, "before_"))
        if dynamic and component_view["componentProblems"]:
            fresh = False
        chain = bool(inst and inst.status == "RUNNING" and wt and wt.status == "PENDING"
                     and inst.current_node == wt.node_code
                     and wt.node_code in (command._COLLEGE_NODE, command._ACADEMIC_NODE))
        scoped_review = review and (allowed_classes is None or task.class_id in allowed_classes)
        academic_role = (str((user or {}).get("currentRoleCode") or "").upper() in core._REVIEW_ROLES
                         or (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN")
        can_act = bool(request.status == "PENDING" and chain and scoped_review
                       and assignee and assignee.status == "ACTIVE" and wt.assignee_id == uid
                       and (wt.node_code != command._ACADEMIC_NODE or (ctx.scope_type == "TENANT_ALL" and academic_role)))
        blockers = []
        if request.status == "PENDING":
            if not chain:
                blockers.append("当前审批任务或业务工作流关系不完整，禁止办理")
            elif not can_act:
                blockers.append("当前账号不是具有本申请范围权限的实际受理人")
            if not fresh:
                blockers.append("申请时的正式成绩已变化或失效，不能通过；请驳回后重新发起")
            if dynamic:
                blockers.extend(component_view["componentProblems"])
            if task.status != "PUBLISHED" or (task.term_id and (not term or term.status == "ARCHIVED")):
                blockers.append("成绩任务未发布或学期已归档/失效，禁止通过")
            if str(record.exception_flag or "NORMAL").upper() != "NORMAL":
                blockers.append("异常成绩缺少更正依据合同，禁止按普通分数通过")
            if request.proposed_total_score is None:
                blockers.append("拟更正分项不完整，不能生成正式成绩")
            if not dynamic:
                proposed = (request.proposed_usual_score, request.proposed_midterm_score, request.proposed_final_score)
                if (not core._scores_complete(task, *proposed)
                        or request.proposed_total_score != core._compose_total(task, *proposed)):
                    blockers.append("拟更正分项不完整或当前计分比例已变化")
                expected_pass = "PASSED" if request.proposed_total_score is not None and request.proposed_total_score >= int(task.pass_line or 60) else "FAILED"
                if request.proposed_pass_status != expected_pass:
                    blockers.append("申请后的及格线或拟更正结论已变化")
        correction = corrections.get(request.id)
        result.append({
            "changeRequestId": str(request.id), "requestVersion": int(request.version or 0),
            "gradeTaskId": str(task.id), "gradeRecordId": str(record.id),
            "studentId": str(request.student_id), "studentNo": student.student_no if student else None,
            "studentName": student.real_name if student else None,
            "courseName": task.course_name, "termId": _id(task.term_id), "termCode": task.term_code,
            "source": request.source, "requestStatus": request.status, "reason": request.reason,
            "createdAt": _iso(request.created_at), "decidedBy": request.decided_by,
            "decidedAt": _iso(request.decided_at), "currentGradeId": _id(request.current_grade_id),
            "expectedGradeVersion": request.expected_grade_version, "currentRecordVersion": int(record.version_no or 1),
            "sourceFresh": fresh, "workflowInstanceId": _id(request.workflow_instance_id),
            "currentNode": inst.current_node if inst else None,
            "currentTaskId": _id(request.current_task_id), "currentTaskVersion": int(wt.version or 0) if wt else None,
            "assigneeId": _id(wt.assignee_id) if wt else None, "assigneeName": assignee.real_name if assignee else None,
            "applicantId": _id(inst.applicant_id) if inst else None, "applicantName": applicant.real_name if applicant else None,
            "allowedActions": (["REJECT"] if blockers else ["APPROVE", "REJECT"]) if can_act else [],
            "blockers": blockers, "schemeMode": "DYNAMIC" if dynamic else "FIXED", **component_view,
            "fixedScores": {"before": _scores(request, "before_"), "proposed": _scores(request, "proposed_"), "current": _scores(record)},
            "ratios": _ratios(task), "correctedGradeId": _id(correction.corrected_grade_id) if correction else None,
            "effectiveAt": _iso(correction.effective_at) if correction else None,
        })
    return result


def list_requests(user, *, queue="MINE", status=None, task_id=None, record_id=None, page=1, page_size=20):
    if queue not in {"MINE", "PENDING", "ALL"} or (status and status not in {"PENDING", "APPROVED", "REJECTED"}):
        raise AppException("VALIDATION_ERROR", "无效的成绩更正队列或状态")
    if page < 1 or not 1 <= page_size <= 200:
        raise AppException("VALIDATION_ERROR", "成绩更正分页范围无效")
    with session() as db:
        access = _access(db, user)
        query = _query(db, user, access)
        if queue == "MINE":
            query = query.where(WorkflowInstance.applicant_id == access[0])
        elif queue == "PENDING":
            if not access[3]:
                raise no_permission("无成绩更正审核权限")
            query = query.where(AaGradeChangeRequest.status == "PENDING", WorkflowInstance.status == "RUNNING",
                                WorkflowTask.status == "PENDING", WorkflowTask.assignee_id == access[0],
                                WorkflowTask.node_code == WorkflowInstance.current_node,
                                WorkflowTask.node_code.in_((command._COLLEGE_NODE, command._ACADEMIC_NODE)))
        if status:
            query = query.where(AaGradeChangeRequest.status == status)
        if task_id is not None:
            query = query.where(AaGradeChangeRequest.grade_task_id == task_id)
        if record_id is not None:
            query = query.where(AaGradeChangeRequest.grade_record_id == record_id)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.execute(query.order_by(AaGradeChangeRequest.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return _hydrate(db, rows, user, access), total


def get_detail(user, request_id):
    with session() as db:
        access = _access(db, user)
        row = db.execute(_query(db, user, access).where(AaGradeChangeRequest.id == request_id)).first()
        if row is None:
            raise not_found("成绩更正申请不存在或不在当前范围")
        dto = _hydrate(db, [row], user, access)[0]
        from . import academic_affairs_grade_change_material_service as materials
        dto.update(materials.details(db, row[0]))
        if row[0].status == "PENDING":
            dto.update(authority.projection(db, row[1], row[2], row[0]))
            if dto["authorityProblems"]:
                dto["blockers"].extend(dto["authorityProblems"])
                dto["sourceFresh"] = False
                dto["allowedActions"] = [action for action in dto["allowedActions"] if action != "APPROVE"]
        if dto["evidenceProblems"]:
            dto["blockers"].extend(dto["evidenceProblems"])
            dto["allowedActions"] = [action for action in dto["allowedActions"] if action != "APPROVE"]
        inst = row[3]
        history = db.scalars(select(WorkflowTask).where(
            WorkflowTask.instance_id == inst.id, *_visible(WorkflowTask),
        ).order_by(WorkflowTask.id)).all() if inst else []
        users = _by_id(db, User, [t.assignee_id for t in history])
        dto["workflowHistory"] = [{
            "taskId": str(t.id), "node": t.node_code, "status": t.status,
            "assigneeId": _id(t.assignee_id), "assigneeName": users[t.assignee_id].real_name if t.assignee_id in users else None,
            "reason": t.action_reason, "actedAt": _iso(t.acted_at), "createdAt": _iso(t.created_at),
        } for t in history]
        return dto


def get_source(user, task_id, record_id):
    from . import academic_affairs_grade_execution_service as execution

    if not has_permission(user, APPLY):
        raise no_permission("无成绩更正申请权限")
    with session() as db:
        task, record = command._load_record(db, task_id, record_id)
        access = _access(db, user)
        if not db.scalar(select(AaGradeTask.id).where(AaGradeTask.id == task.id, _scope(db, user, access))):
            raise no_permission("原成绩不在当前业务范围")
        execution._require_live_teacher(db, task, user)
        # Source reads do not acquire business write locks or create evidence.
        dynamic = command._has_dynamic(db, task.id)
        component_view = components.projection(db, task, record) if dynamic else {}
        authority_view = authority.projection(db, task, record)
        blockers = command._fixed_source_blockers(db, task, record, allow_dynamic=True)
        blockers.extend(authority_view["authorityProblems"])
        blockers.extend(component_view.get("componentProblems", []))
        pending_id = db.scalar(select(AaGradeChangeRequest.id).where(
            AaGradeChangeRequest.grade_record_id == record.id, AaGradeChangeRequest.status == "PENDING",
            *_visible(AaGradeChangeRequest),
        ).limit(1))
        if pending_id:
            blockers.append("该成绩已有在途更正申请，请在申请队列核对后办理")
        student = _by_id(db, StudentProfile, [record.student_id]).get(record.student_id)
        return {
            "gradeTaskId": str(task.id), "gradeRecordId": str(record.id), "studentId": str(record.student_id),
            "studentNo": student.student_no if student else None, "studentName": student.real_name if student else None,
            "courseName": task.course_name, "termId": _id(task.term_id), "termCode": task.term_code,
            "taskStatus": task.status, "recordVersion": int(record.version_no or 1),
            "currentGradeId": _id(record.acad_grade_id), "schemeMode": "DYNAMIC" if dynamic else "FIXED", **component_view,
            **_scores(record), **_ratios(task), **authority_view, "canApply": not blockers, "blockers": blockers,
        }
