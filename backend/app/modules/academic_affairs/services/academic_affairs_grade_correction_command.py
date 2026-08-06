"""包 1：正式成绩更正统一命令。

关闭三条根因：

- **C05 正式成绩原地覆盖**：发起更正时不再改 ``AaGradeRecord`` 的分项，改成把"想改成什么"
  写进 ``AaGradeChangeRequest``。审批期间成绩单、毕业审核、学生自己看到的仍是当前生效成绩。
  终审通过才追加一条新的 ``AcademicGrade``，原行转 ``SUPERSEDED``——与成绩复查走同一套
  追加式版本链，连续两次更正形成 A→B→C 可追溯。
- **C06 更正与工作流跨两个事务**：终审此前先 commit 正式成绩与消息，再另开会话完成工作流；
  中间失败就留下"成绩已改、流程还在审"的分裂状态。现在锁记录 → 锁当前 ACTIVE 成绩 →
  锁更正命令 → 原子认领 WorkflowTask → 生成新版本 → 冻结策略 → 完成工作流 → 审计 →
  outbox，一次 commit。
- **NEW-P1-02 assignee_id=0**：学院与教务节点都解析真实受理人，解析不到就拒绝发起，
  不再生成没人负责、谁都能抢办的待审任务。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_, select

from app.core.affairs_security import build_affairs_context
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_grade_core_service as _core

_COLLEGE_NODE = "COLLEGE_REVIEW"
_ACADEMIC_NODE = "ACADEMIC_REVIEW"
_REVIEW_PERM = "academicAffairs.gradeChange.review"


def _conflict(message, **details):
    return AppException("DATA_CONFLICT", message, details=details or None, http_status=409)


def _version_conflict(message, **details):
    return AppException("APPROVAL_VERSION_CONFLICT", message, details=details or None, http_status=409)


# ═══════════ 受理人解析（NEW-P1-02） ═══════════

def _permission_holder_ids(db, permission_code: str) -> list[int]:
    """持有该权限的启用账号。"""
    from app.models import Permission, Role, RolePermission, User, UserRole

    conditions = [
        User.tenant_id == _tid(), User.status == "ACTIVE", User.is_deleted.is_(False),
        UserRole.tenant_id == _tid(), UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
        Role.tenant_id == _tid(), Role.status == "ACTIVE", Role.is_deleted.is_(False),
        RolePermission.tenant_id == _tid(), RolePermission.status == "ACTIVE",
        RolePermission.is_deleted.is_(False),
        Permission.permission_code == permission_code,
    ]
    stmt = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(*conditions)
        .distinct()
        .order_by(User.id)
    )
    return [int(value) for value in db.scalars(stmt).all()]


def _college_bound_user_ids(db) -> set[int]:
    """绑在某个具体学院上的账号（教学秘书或学院在岗岗位）。

    教务处终审属于校级职责，必须排除这些院级账号：否则学院教务既审初审又审终审，
    职责分离形同虚设，候选人也会因不唯一直接把整条更正链卡死。
    """
    from app.models import College, StaffAssignment

    bound = {
        int(value) for (value,) in db.query(College.secretary_id).filter(
            College.tenant_id == _tid(),
            College.is_deleted.is_(False),
            College.secretary_id.is_not(None),
        ).all()
    }
    now = datetime.utcnow()
    bound |= {
        int(value) for value in db.scalars(select(StaffAssignment.user_id).where(
            StaffAssignment.tenant_id == _tid(),
            StaffAssignment.org_type == "COLLEGE",
            StaffAssignment.status == "ACTIVE",
            StaffAssignment.is_deleted.is_(False),
            StaffAssignment.effective_at <= now,
            or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now),
        )).all()
    }
    return bound


def _task_college_id(db, task) -> int | None:
    """成绩任务 → 开课/行政班学院。教学班优先，退回行政班的专业归属学院。"""
    from app.models import Major, SchoolClass

    class_id = getattr(task, "class_id", None)
    if not class_id:
        return None
    school_class = db.get(SchoolClass, int(class_id))
    if not school_class or school_class.tenant_id != _tid() or school_class.is_deleted:
        return None
    if not school_class.major_id:
        return None
    major = db.get(Major, int(school_class.major_id))
    if not major or major.tenant_id != _tid() or major.is_deleted:
        return None
    return int(major.college_id) if major.college_id else None


def _active_user(db, user_id):
    from app.models import User

    if not user_id:
        return None
    row = db.get(User, int(user_id))
    if not row or row.tenant_id != _tid() or row.is_deleted or row.status != "ACTIVE":
        return None
    return row


def _unique_assignee(candidates, node) -> int:
    unique = sorted({int(value) for value in candidates if int(value) > 0})
    if len(unique) != 1:
        raise _conflict(
            "成绩更正审批节点没有唯一真实受理人，禁止生成无人或人人可抢的待审任务",
            node=node, candidateUserIds=[str(value) for value in unique],
        )
    return unique[0]


def resolve_change_assignee(db, node: str, task) -> int:
    """学院节点按开课学院的教学秘书/在岗负责人；教务终审收敛到校级岗位账号。解析不到即 409。

    两个节点共用 ``gradeChange.review`` 一个权限码（现有权限模型如此），所以终审必须再按
    校级账号身份收窄，否则学院教务也会被算成候选人，既破坏职责分离，也会因"候选人不唯一"
    把整条更正链卡死。
    """
    candidates = _permission_holder_ids(db, _REVIEW_PERM)
    if node != _COLLEGE_NODE:
        college_bound = _college_bound_user_ids(db)
        return _unique_assignee([uid for uid in candidates if uid not in college_bound], node)

    from app.models import College, StaffAssignment

    college_id = _task_college_id(db, task)
    if not college_id:
        raise _conflict("成绩任务未绑定开课学院，无法解析学院初审受理人", node=node)
    college = db.get(College, int(college_id))
    if not college or college.tenant_id != _tid() or college.is_deleted:
        raise _conflict("成绩更正的开课学院不存在或已停用", node=node)

    if college.secretary_id and int(college.secretary_id) in candidates:
        if _active_user(db, int(college.secretary_id)):
            return int(college.secretary_id)

    now = datetime.utcnow()
    assigned = db.scalars(select(StaffAssignment.user_id).where(
        StaffAssignment.tenant_id == _tid(),
        StaffAssignment.org_type == "COLLEGE",
        StaffAssignment.org_node_id == int(college_id),
        StaffAssignment.assignment_type.in_(("SECRETARY", "LEADER")),
        StaffAssignment.status == "ACTIVE",
        StaffAssignment.is_deleted.is_(False),
        StaffAssignment.effective_at <= now,
        or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now),
    ).order_by(StaffAssignment.is_primary.desc(), StaffAssignment.user_id)).all()
    allowed = [int(uid) for uid in assigned if int(uid) in candidates and _active_user(db, int(uid))]
    return _unique_assignee(allowed, node)


def _current_user_id(db) -> int:
    """审批人稳定数值 userId；演示登录的 ``u_<loginName>`` 回 t_user 解析，查不到即拒绝。"""
    from app.models import User

    current = get_current_user_ctx() or {}
    raw = current.get("userId")
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = 0
    if parsed > 0:
        return parsed
    login_name = str(current.get("loginName") or "").strip()
    text = str(raw or "").strip()
    if not login_name and text.startswith("u_"):
        login_name = text[2:]
    if login_name:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(), User.login_name == login_name,
            User.status == "ACTIVE", User.is_deleted.is_(False),
        )).first()
        if row:
            return int(row.id)
    raise no_permission("当前登录身份未绑定有效系统账号，禁止审批成绩更正")


# ═══════════ 发起更正：只写命令，不动正式成绩（C05） ═══════════

def _load_record(db, task_id, record_id, *, lock=False):
    from app.models import AaGradeRecord, AaGradeTask

    task = db.get(AaGradeTask, int(task_id))
    if not task or task.is_deleted or task.tenant_id != _tid():
        raise not_found("成绩录入任务不存在")
    query = db.query(AaGradeRecord).filter(
        AaGradeRecord.id == int(record_id),
        AaGradeRecord.tenant_id == _tid(),
        AaGradeRecord.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    record = query.first()
    if not record or int(record.task_id) != int(task.id):
        raise not_found("成绩明细不存在")
    return task, record


def _proposed_scores(task, record, body):
    """请求未传的分项沿用当前正式值；总评与及格结论由服务端按任务占比重算。"""
    usual = getattr(body, "newUsualScore", None)
    midterm = getattr(body, "newMidtermScore", None)
    final = getattr(body, "newFinalScore", None)
    usual = record.usual_score if usual is None else int(usual)
    midterm = record.midterm_score if midterm is None else int(midterm)
    final = record.final_score if final is None else int(final)
    for label, value in (("平时", usual), ("期中", midterm), ("期末", final)):
        if value is not None and not (0 <= int(value) <= 100):
            raise AppException("VALIDATION_ERROR", f"{label}成绩须为 0-100 整数")
    total = None
    if _core._scores_complete(task, usual, midterm, final):
        total = _core._compose_total(task, usual, midterm, final)
    pass_status = None
    if total is not None:
        pass_status = "PASSED" if total >= int(task.pass_line or 60) else "FAILED"
    return usual, midterm, final, total, pass_status


def change_request(task_id, record_id, user, body) -> dict:
    """教师发起成绩更正：写命令 + 开工作流，正式成绩保持不变。"""
    from app.models import AaGradeTask, WorkflowInstance, WorkflowTask
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    from app.services.runtime_preset_install_service import ensure_workflow_enabled

    with session() as db:
        task, record = _load_record(db, task_id, record_id, lock=True)
        _core._check_course_scope(task, user)
        if task.status == "ARCHIVED":
            raise _conflict("已归档学期，成绩更正需线下特批（本轮暂未开放线上入口）")
        if task.status != "PUBLISHED":
            raise _conflict("仅已发布成绩可申请更正")
        guard_term_writable(db, task.term_id)

        reason = (getattr(body, "reason", "") or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "更正原因必填且不少于5字")

        running = db.query(AaGradeChangeRequest).filter(
            AaGradeChangeRequest.tenant_id == _tid(),
            AaGradeChangeRequest.grade_record_id == record.id,
            AaGradeChangeRequest.status == "PENDING",
            AaGradeChangeRequest.is_deleted.is_(False),
        ).with_for_update().first()
        if running:
            raise _conflict("该成绩已有在途更正申请，不可重复发起", changeRequestId=str(running.id))

        usual, midterm, final, total, pass_status = _proposed_scores(task, record, body)
        if (usual, midterm, final) == (record.usual_score, record.midterm_score, record.final_score):
            raise AppException("VALIDATION_ERROR", "更正申请没有任何分项变化")

        assignee = resolve_change_assignee(db, _COLLEGE_NODE, task)

        request = AaGradeChangeRequest(
            tenant_id=_tid(), grade_task_id=task.id, grade_record_id=record.id,
            student_id=record.student_id, source="CHANGE_REQUEST",
            proposed_usual_score=usual, proposed_midterm_score=midterm,
            proposed_final_score=final, proposed_total_score=total,
            proposed_pass_status=pass_status,
            before_usual_score=record.usual_score, before_midterm_score=record.midterm_score,
            before_final_score=record.final_score, before_total_score=record.total_score,
            current_grade_id=record.acad_grade_id,
            expected_grade_version=int(record.version_no or 1),
            reason=reason, status="PENDING",
        )
        db.add(request)
        db.flush()

        ensure_workflow_enabled(db, _tid(), _core._WF_CHANGE)
        _name, _role, uid = _core._op()
        instance = WorkflowInstance(
            tenant_id=_tid(), workflow_code=_core._WF_CHANGE, source_module="academic-affairs",
            source_biz_type="AA_GRADE_CHANGE", source_biz_id=record.id,
            applicant_id=int(uid) if str(uid).isdigit() else 0,
            title=f"{task.course_name or ''} 成绩更正", status="RUNNING", current_node=_COLLEGE_NODE,
        )
        db.add(instance)
        db.flush()
        wtask = WorkflowTask(tenant_id=_tid(), instance_id=instance.id, node_code=_COLLEGE_NODE,
                             assignee_id=assignee, status="PENDING")
        db.add(wtask)
        db.flush()
        request.workflow_instance_id = instance.id
        request.current_task_id = wtask.id
        _core._audit(db, "AA_GRADE_RECORD", record.id, "CHANGE_APPLY",
                     f"requestId={request.id};assignee={assignee};{reason}")
        db.commit()
        return {
            "recordId": str(record.id), "changeRequestId": str(request.id),
            "workflowInstanceId": str(instance.id), "assigneeId": str(assignee),
            "status": "CHANGE_REVIEW",
            "proposedTotalScore": total, "currentTotalScore": record.total_score,
        }


# ═══════════ 审批：认领 + 决定 + 正式事实，一次事务（C06） ═══════════

def _load_pending_request(db, record_id):
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    request = db.query(AaGradeChangeRequest).filter(
        AaGradeChangeRequest.tenant_id == _tid(),
        AaGradeChangeRequest.grade_record_id == int(record_id),
        AaGradeChangeRequest.status == "PENDING",
        AaGradeChangeRequest.is_deleted.is_(False),
    ).with_for_update().first()
    if not request:
        raise _version_conflict("该成绩没有在途更正申请")
    return request


def _claim_task(db, request, node):
    from app.models import WorkflowInstance, WorkflowTask

    instance = db.get(WorkflowInstance, int(request.workflow_instance_id or 0))
    if not instance or instance.tenant_id != _tid() or instance.is_deleted:
        raise _conflict("成绩更正缺少工作流实例")
    if instance.current_node != node:
        raise _version_conflict("当前更正申请不在此审核节点",
                                currentNode=str(instance.current_node or ""))
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.instance_id == instance.id,
        WorkflowTask.node_code == node,
        WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False),
    ).with_for_update()).first()
    if not task:
        raise _version_conflict("当前审批任务不存在或已被处理")
    assignee = int(task.assignee_id or 0)
    if assignee <= 0:
        raise _conflict("该审批任务没有真实受理人，请由教务处重新指派")
    if assignee != _current_user_id(db):
        raise no_permission("当前审批任务已明确分配给其他受理人")
    return instance, task


def _reject(db, request, instance, task, reason):
    request.status = "REJECTED"
    request.decided_by = (get_current_user_ctx() or {}).get("realName") or ""
    request.decided_at = datetime.utcnow()
    request.current_task_id = None
    task.status, task.action_reason, task.acted_at = "REJECTED", reason, datetime.utcnow()
    instance.status = "REJECTED"
    _core._audit(db, "AA_GRADE_RECORD", request.grade_record_id, "CHANGE_REJECT", reason)


def change_college_review(record_id, user, action, reason="") -> dict:
    """学院初审：通过→推进到教务终审并解析真实受理人；驳回→正式成绩本来就没动过。"""
    from app.models import AaGradeTask, WorkflowTask

    act = (action or "").upper()
    with session() as db:
        request = _load_pending_request(db, record_id)
        task = db.get(AaGradeTask, int(request.grade_task_id))
        if task:
            _core._check_college_scope(db, task, user)
        instance, wtask = _claim_task(db, request, _COLLEGE_NODE)

        if act == "REJECT":
            cleaned = (reason or "").strip()
            if len(cleaned) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            _reject(db, request, instance, wtask, cleaned)
            db.commit()
            return {"recordId": str(record_id), "status": "PUBLISHED"}
        if act != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")

        wtask.status, wtask.acted_at = "APPROVED", datetime.utcnow()
        assignee = resolve_change_assignee(db, _ACADEMIC_NODE, task)
        instance.current_node = _ACADEMIC_NODE
        next_task = WorkflowTask(tenant_id=_tid(), instance_id=instance.id,
                                 node_code=_ACADEMIC_NODE, assignee_id=assignee, status="PENDING")
        db.add(next_task)
        db.flush()
        request.current_task_id = next_task.id
        _core._audit(db, "AA_GRADE_RECORD", request.grade_record_id, "CHANGE_STEP",
                     f"->{_ACADEMIC_NODE};assignee={assignee}")
        db.commit()
        return {"recordId": str(record_id), "status": "CHANGE_REVIEW",
                "assigneeId": str(assignee)}


def change_academic_review(record_id, user, action, reason="") -> dict:
    """教务终审：通过则以追加式版本生成新正式成绩，全链单事务。"""
    from app.models import AaGradeRecord, AaGradeTask, AcademicGrade, AcademicStudent
    from app.models.academic_affairs_effective_grade import AaGradeCorrection
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        freeze_effective_grade_policy,
        policy_payload,
        resolve_active_policy,
    )
    from app.modules.academic_affairs.services.academic_affairs_grade_service import _refresh_aggregates
    from app.services.message_event_outbox_service import emit_receiver_notice

    act = (action or "").upper()
    _core._require_review_role(user)
    with session() as db:
        request = _load_pending_request(db, record_id)
        instance, wtask = _claim_task(db, request, _ACADEMIC_NODE)

        if act == "REJECT":
            cleaned = (reason or "").strip()
            if len(cleaned) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            _reject(db, request, instance, wtask, cleaned)
            db.commit()
            return {"recordId": str(record_id), "status": "PUBLISHED"}
        if act != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")

        record = db.query(AaGradeRecord).filter(
            AaGradeRecord.id == int(request.grade_record_id),
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("成绩明细不存在")
        if int(record.version_no or 1) != int(request.expected_grade_version or 1):
            raise _version_conflict(
                "该成绩在本次更正在途期间已被其他入口改写，请重新发起更正",
                expectedVersion=int(request.expected_grade_version or 1),
                currentVersion=int(record.version_no or 1),
            )
        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(request.grade_task_id),
            AaGradeTask.tenant_id == _tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not task:
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)

        original = None
        if record.acad_grade_id:
            original = db.query(AcademicGrade).filter(
                AcademicGrade.id == int(record.acad_grade_id),
                AcademicGrade.tenant_id == _tid(),
                AcademicGrade.is_deleted.is_(False),
            ).with_for_update().first()
        if not original or original.record_status != "ACTIVE":
            raise _conflict("正式成绩不存在或已失效，无法在其之上追加更正版本")

        policy = resolve_active_policy(db, task.term_id, required=True)
        pass_line = int(task.pass_line or 60)
        score = request.proposed_total_score
        pass_status = request.proposed_pass_status or (
            "PASSED" if score is not None and score >= pass_line else "FAILED"
        )

        excluded = {
            "id", "created_at", "created_by", "updated_at", "updated_by",
            "is_deleted", "version", "score", "pass_status", "record_status",
            "void_reason", "source", "source_biz_type", "source_biz_id",
        }
        payload = {
            attr.key: getattr(original, attr.key)
            for attr in AcademicGrade.__mapper__.column_attrs
            if attr.key not in excluded
        }
        # 必须先让原行退位再插新行：uk_acad_grade_active_record 只允许同一成绩明细存在
        # 一条 ACTIVE 版本，顺序反了会在 flush 时自己撞自己的唯一键。
        original.record_status = "SUPERSEDED"
        original.void_reason = "成绩更正，已由后继版本接管"
        db.flush()

        corrected = AcademicGrade(
            **payload,
            score=score,
            pass_status=pass_status,
            record_status="ACTIVE",
            void_reason=None,
            source="CHANGE",
            source_biz_type="GRADE_CHANGE_REQUEST",
            source_biz_id=request.id,
        )
        corrected.effective_policy_code = str(policy.policy_code)
        corrected.effective_policy_version = int(policy.policy_version or 1)
        corrected.effective_attempt_strategy = str(policy.attempt_strategy or "").upper()
        corrected.pass_line_snapshot = pass_line
        db.add(corrected)
        db.flush()
        original.void_reason = f"成绩更正，后继成绩ID={corrected.id}"

        record.usual_score = request.proposed_usual_score
        record.midterm_score = request.proposed_midterm_score
        record.final_score = request.proposed_final_score
        record.total_score = score
        record.pass_status = pass_status
        record.prev_usual_score = request.before_usual_score
        record.prev_midterm_score = request.before_midterm_score
        record.prev_final_score = request.before_final_score
        record.prev_total_score = request.before_total_score
        record.acad_grade_id = corrected.id
        record.source = "CHANGE"
        record.change_reason = request.reason
        record.change_at = datetime.utcnow()
        _name, _role, uid = _core._op()
        record.change_by = int(uid) if str(uid).isdigit() else None
        record.version_no = int(record.version_no or 1) + 1

        db.add(AaGradeCorrection(
            tenant_id=_tid(),
            source_type="CHANGE_REQUEST",
            source_ref_id=request.id,
            recheck_id=None,
            original_grade_id=original.id,
            corrected_grade_id=corrected.id,
            before_score=request.before_total_score,
            after_score=score,
            pass_line=pass_line,
            rule_snapshot_json=json.dumps({
                "passLine": pass_line,
                "policy": policy_payload(corrected),
                "gradeTaskId": str(task.id),
                "termId": str(task.term_id or ""),
                "changeRequestId": str(request.id),
            }, ensure_ascii=False, sort_keys=True),
            reason=request.reason,
            operator=_name or str(uid),
            effective_at=datetime.utcnow(),
            status="ACTIVE",
        ))
        freeze_effective_grade_policy(
            db, corrected, event_type="CHANGE",
            source_biz_type="GRADE_CHANGE_REQUEST", source_biz_id=request.id,
        )

        academic_student = (
            db.get(AcademicStudent, int(corrected.acad_student_id))
            if corrected.acad_student_id else None
        )
        if academic_student:
            _refresh_aggregates(db, academic_student)

        wtask.status, wtask.acted_at = "APPROVED", datetime.utcnow()
        instance.status = "APPROVED"
        request.status = "APPROVED"
        request.decided_by = _name or str(uid)
        request.decided_at = datetime.utcnow()
        request.current_task_id = None

        emit_receiver_notice(
            db,
            event_code="GRADE.CORRECTED",
            source_module="academic-affairs",
            source_biz_type="aa_grade_record",
            source_biz_id=record.id,
            receiver_id=int(record.student_id),
            title="成绩已更正",
            content=f"{task.course_name or ''} 成绩已更正为 {score}",
            receiver_as="student",
        )
        _core._audit(
            db, "AA_GRADE_RECORD", record.id, "CHANGE_APPROVE",
            f"requestId={request.id};{request.before_total_score}→{score};newGradeId={corrected.id}",
        )
        db.commit()

    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="aa-grade-change-inline")
    warning_scan_ok = True
    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_warnings
        scan_warnings(user)
    except Exception:  # noqa: BLE001
        import logging
        warning_scan_ok = False
        logging.getLogger(__name__).exception("grade change approve -> scan_warnings failed")
    return {
        "recordId": str(record_id), "status": "PUBLISHED", "final": True,
        "correctedGradeId": str(corrected.id), "totalScore": score,
        "passStatus": pass_status, "warningScanOk": warning_scan_ok,
    }


change_request._grade_correction_command = True
change_college_review._grade_correction_command = True
change_academic_review._grade_correction_command = True


def install() -> None:
    """幂等安装：成绩域公开 Service 与 core 的更正入口统一指向本命令。"""
    from . import academic_affairs_grade_service as _public

    for module in (_core, _public):
        for name, func in (
            ("change_request", change_request),
            ("change_college_review", change_college_review),
            ("change_academic_review", change_academic_review),
        ):
            if not getattr(getattr(module, name, None), "_grade_correction_command", False):
                setattr(module, name, func)
