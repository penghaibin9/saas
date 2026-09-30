"""学院审核只读证据；在 canonical 审核事务中重算同一摘要，不建立第二状态机。"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from . import academic_affairs_grade_core_service as core
from . import academic_affairs_roster_consumer_service as roster_service


def _facts(row, names):
    return {name: getattr(row, name) for name in names.split()} if row else None


def _rows(db, model, *conditions):
    # Current reads are required after waiting for a writer under MySQL REPEATABLE READ.
    return db.scalars(select(model).where(
        model.tenant_id == core._tid(), model.is_deleted.is_(False), *conditions,
    ).order_by(model.id).with_for_update().execution_options(populate_existing=True)).all()


def require_scope(db, task, user):
    from . import academic_affairs_grade_task_read_service as task_read

    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role not in core._REVIEW_ROLES | {"COLLEGE_ADMIN"} and (user or {}).get("userType") != "PLATFORM_SUPER_ADMIN":
        raise no_permission("当前身份不能办理学院成绩审核")
    visible = db.execute(task_read._base_query().where(
        *task_read._scope_conditions(db, user, task_id=task.id),
    )).first()
    if not visible:
        raise AppException("NO_DATA_SCOPE", "成绩任务不在当前审核范围", http_status=403)


def build_evidence(db, task, user):
    """Caller owns the GradeTask lock. This function performs SELECTs only."""
    from app.models import (AaCourse, AaGradeRecord, AaTeachingClass,
                            AaTeachingClassMember, AaTeachingClassRosterVersion,
                            AaTerm, WorkflowInstance, WorkflowTask)
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy
    from app.models.academic_affairs_r10 import AaGradeComponentScore, AaGradeSchemeSnapshot
    from . import academic_affairs_dynamic_grade_service as dynamic
    from . import academic_affairs_effective_grade_policy_service as policy_service
    from .academic_affairs_effective_grade_policy_compat import select_chronological_policy

    require_scope(db, task, user)
    # GradeTask -> policy authority -> term/roster/score facts. Policy activation
    # and first-use base policy insertion take the same authority lock first.
    policy_service.lock_policy_authority(db)
    blockers = []

    def block(code, message):
        blockers.append({"code": code, "message": message})

    terms = _rows(db, AaTerm, AaTerm.id == (task.term_id or 0))
    if not terms or terms[0].status == "ARCHIVED":
        block("TERM_UNAVAILABLE", "学期缺失或已封存")
    courses = _rows(db, AaCourse, AaCourse.id == (task.course_id or 0))
    course = courses[0] if courses else None
    if not course or not course.course_code or not course.version:
        block("COURSE_IDENTITY_MISSING", "任务缺少正式课程版本")

    classes = _rows(db, AaTeachingClass, AaTeachingClass.teaching_task_id == (task.teaching_task_id or 0))
    teaching_class = classes[0] if len(classes) == 1 else None
    snapshots = roster_service._consumer_rows(db, "GRADE_TASK", int(task.id), lock=True)
    snapshot = roster_service._active_row(snapshots)
    frozen = roster_service._snapshot_dto(snapshot) if snapshot else None
    versions = _rows(db, AaTeachingClassRosterVersion,
                     AaTeachingClassRosterVersion.id == (teaching_class.current_roster_version_id if teaching_class else 0))
    version = versions[0] if versions else None
    members = _rows(db, AaTeachingClassMember,
                    AaTeachingClassMember.roster_version_id == (version.id if version else 0),
                    AaTeachingClassMember.status == "ACTIVE")
    member_ids = sorted({int(row.student_id) for row in members})
    current = bool(teaching_class and teaching_class.status == "ACTIVE" and version
                   and version.status == "LOCKED" and version.teaching_class_id == teaching_class.id
                   and version.roster_hash == roster_service.roster_hash(member_ids)
                   and version.member_count == len(member_ids))
    if current and snapshot:
        current = roster_service._matches(snapshot, int(task.teaching_task_id), {
            "teachingClassId": teaching_class.id, "rosterVersionId": version.id,
            "rosterVersionNo": version.version_no, "rosterHash": version.roster_hash,
            "memberCount": version.member_count, "studentIds": member_ids,
        })
    else:
        current = False
    # Reuse the canonical read-only projection check as well: a matching class
    # head alone cannot prove that its source selection batch is still ready.
    resolved = roster_service.teaching_class_service.resolve_teaching_task_roster(
        db, int(task.teaching_task_id),
    ) if task.teaching_task_id else {}
    current = current and bool(resolved.get("ready")) and (
        int(resolved.get("rosterVersionId") or 0) == int(version.id)
        and roster_service._ids(resolved.get("studentIds")) == member_ids
    )
    if not current:
        block("ROSTER_STALE", "提交冻结名单缺失、损坏或已不是当前正式名单，请退回重提")

    records = _rows(db, AaGradeRecord, AaGradeRecord.task_id == task.id)
    student_counts = Counter(int(row.student_id) for row in records)
    frozen_ids = set(frozen["studentIds"]) if frozen else None
    missing = len(frozen_ids - student_counts.keys()) if frozen_ids is not None else None
    outside = len(student_counts.keys() - frozen_ids) if frozen_ids is not None else None
    duplicates = sum(count - 1 for count in student_counts.values())
    if not frozen_ids or missing or outside or duplicates:
        block("RECORD_ROSTER_MISMATCH", "正式名单与成绩记录未收口（空名单、缺失、名单外或重复记录）")

    schemes = _rows(db, AaGradeSchemeSnapshot, AaGradeSchemeSnapshot.grade_task_id == task.id)
    scheme_row = schemes[0] if len(schemes) == 1 else None
    components = []
    try:
        components = dynamic.normalize_components(dynamic._components(scheme_row, task))
    except AppException as exc:
        block("SCHEME_INVALID", str(exc.message))
    if len(schemes) > 1 or (scheme_row and scheme_row.status != "LOCKED"):
        block("SCHEME_UNLOCKED", "动态成绩方案尚未锁定或存在重复快照")
    scores = _rows(db, AaGradeComponentScore, AaGradeComponentScore.grade_task_id == task.id)
    by_record = defaultdict(list)
    for score in scores:
        by_record[int(score.grade_record_id)].append(score)
    scheme = {
        "mode": "DYNAMIC" if scheme_row else "FIXED",
        "version": scheme_row.scheme_version if scheme_row else None,
        "status": scheme_row.status if scheme_row else "TASK_RATIOS",
        "components": components,
    }
    incomplete = 0
    exceptions = {flag: 0 for flag in sorted(dynamic._ALLOWED_FLAGS)}
    for record in records:
        flag = str(record.exception_flag or "NORMAL").upper()
        exceptions[flag] = exceptions.get(flag, 0) + 1
        if flag not in dynamic._ALLOWED_FLAGS:
            incomplete += 1
            continue
        if flag != "NORMAL":
            continue
        valid = bool(components) and record.total_score is not None
        if scheme_row:
            rows = by_record.get(int(record.id), [])
            by_code = {row.component_code: row for row in rows}
            valid = valid and len(rows) == len(components) and len(by_code) == len(components)
            for item in components:
                score = by_code.get(item["code"])
                valid = valid and bool(score and score.student_id == record.student_id
                    and score.scheme_version == scheme_row.scheme_version
                    and math.isfinite(score.score) and 0 <= score.score <= 100
                    and abs(score.weight - item["weight"]) < 0.0001
                    and abs(score.weighted_score - round(score.score * item["weight"] / 100, 4)) < 0.0001)
            total = round(round(sum(row.weighted_score for row in rows), 2)) if valid else None
        else:
            valid = valid and core._scores_complete(task, record.usual_score, record.midterm_score, record.final_score) and not by_record.get(int(record.id))
            valid = valid and all(value is None or 0 <= value <= 100 for value in
                                  (record.usual_score, record.midterm_score, record.final_score))
            total = core._compose_total(task, record.usual_score, record.midterm_score, record.final_score) if valid else None
        if not valid or total != record.total_score:
            incomplete += 1
    record_ids = {record.id for record in records}
    if any(row.grade_record_id not in record_ids for row in scores):
        block("COMPONENT_ORPHAN", "动态分项存在未关联正式成绩记录的事实")
    if incomplete:
        block("SCORES_INCOMPLETE", f"有 {incomplete} 条成绩分项、异常或合成结果需核对")

    # Current reads after the authority lock cannot reuse an earlier RR snapshot.
    # The selector is exactly the one used by formal effective-grade publication.
    policies = _rows(db, AaEffectiveGradePolicy, AaEffectiveGradePolicy.status == "ACTIVE")
    policy_term_ids = {int(row.effective_from_term_id) for row in policies if row.effective_from_term_id}
    policy_term_ids.add(int(task.term_id or 0))
    policy_terms = {int(row.id): row for row in _rows(db, AaTerm, AaTerm.id.in_(sorted(policy_term_ids)))}
    policy = None
    try:
        policy_row = select_chronological_policy(policies, policy_terms, task.term_id)
        policy = policy_service._policy_dto(policy_row)
    except AppException as error:
        block("POLICY_UNAVAILABLE", error.message)

    instances = _rows(db, WorkflowInstance, WorkflowInstance.id == (task.workflow_instance_id or 0))
    instance = instances[0] if instances else None
    workflow_tasks = _rows(db, WorkflowTask, WorkflowTask.instance_id == (instance.id if instance else 0),
                           WorkflowTask.node_code == "COLLEGE_REVIEW", WorkflowTask.status == "PENDING")
    workflow = {"currentNode": instance.current_node if instance else None,
                "assigneeId": str(workflow_tasks[0].assignee_id) if len(workflow_tasks) == 1 else None}
    if (not instance or instance.status != "RUNNING" or instance.current_node != "COLLEGE_REVIEW"
            or instance.source_biz_type != "AA_GRADE_TASK" or instance.source_biz_id != task.id
            or len(workflow_tasks) != 1):
        block("WORKFLOW_STALE", "当前学院审核流程节点缺失或已变化")
    if task.status != "SUBMITTED":
        block("TASK_STATE_CHANGED", "当前任务已不在待学院审核状态")

    evidence = {
        "gradeTaskId": str(task.id), "status": task.status,
        "roster": {**{key: value for key, value in (frozen or {}).items() if key != "studentIds"}, "current": current} if frozen else None,
        "counts": {"expected": len(frozen_ids) if frozen_ids is not None else None,
                   "entered": len(student_counts), "missing": missing, "outside": outside,
                   "incomplete": incomplete, "duplicates": duplicates},
        "exceptions": exceptions, "scheme": scheme, "policy": policy, "workflow": workflow,
        "blockers": blockers,
        "allowedActions": (["RETURN"] + ([] if blockers else ["APPROVE"])) if task.status == "SUBMITTED" else [],
    }
    facts = {
        "evidence": evidence,
        "task": _facts(task, "id tenant_id teaching_task_id term_id course_id class_id teacher_key credit usual_ratio midterm_ratio final_ratio pass_line submitted_at workflow_instance_id"),
        "course": _facts(course, "id course_code version credit"),
        "frozen": frozen,
        "currentRoster": {key: resolved.get(key) for key in ("ready", "source", "batchIds", "teachingClassId", "rosterVersionId", "rosterVersionNo")},
        "members": member_ids,
        "records": [_facts(row, "id student_id version_no usual_score midterm_score final_score total_score pass_status exception_flag") for row in records],
        "scores": [_facts(row, "id grade_record_id student_id component_code score weighted_score weight scheme_version") for row in scores],
        "workflowTasks": [_facts(row, "id assignee_id status node_code") for row in workflow_tasks],
    }
    evidence["evidenceHash"] = hashlib.sha256(json.dumps(
        facts, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    evidence["checkedAt"] = datetime.utcnow().isoformat()
    return evidence


def get_evidence(task_id, user):
    from . import academic_affairs_grade_service as grade
    with core.session() as db:
        task = grade._load_task(db, int(task_id), lock=True)
        return build_evidence(db, task, user)
