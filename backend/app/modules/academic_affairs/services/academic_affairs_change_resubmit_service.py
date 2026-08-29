"""AA-003 returned status-change resubmission command.

A RETURN decision must not force a student to create a second status-change case.  This
command reopens the original row and original workflow instance in one transaction:
row lock -> student ownership -> frozen term -> current student fact -> target validation ->
new first-node task -> todo/audit -> commit.  The original change id, workflow history and
idempotency key remain stable; concurrent double-submit can only reopen the row once.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid, session
from app.services.mobile_student_service import _require_student, resolve_student

from . import academic_affairs_change_safety_guard as safety
from . import academic_affairs_change_service as change


def _value(body, key, default=None):
    if isinstance(body, dict):
        return body.get(key, default)
    return getattr(body, key, default)


def _has(body, key) -> bool:
    if isinstance(body, dict):
        return key in body
    return hasattr(body, key)


def _student_my(db, user):
    student = resolve_student(db, _require_student(user))
    if not student:
        raise no_permission("尚未建立你的学生档案")
    return student


def _require_version(row, body) -> None:
    expected = _value(body, "expectedVersion")
    if expected in (None, ""):
        return
    try:
        wanted = int(expected)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from exc
    current = int(row.version or 0)
    if wanted != current:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "该异动已发生变化，请刷新后再重交",
            details={"expectedVersion": wanted, "currentVersion": current},
            http_status=409,
        )


def _validate_current_fact(db, row, student) -> None:
    current = str(student.student_status or "").upper()
    origin = str(row.from_status or "").upper()
    if current != origin:
        raise AppException(
            "STATUS_CHANGE_STALE_STUDENT_FACT",
            "退回期间学生学籍状态已变化，禁止继续重交旧申请",
            details={"expectedStatus": origin, "currentStatus": current},
            http_status=409,
        )
    if current in {"MERGED", "RECYCLED", "WITHDRAWN", "GRADUATED"}:
        raise AppException("DATA_CONFLICT", f"学生已处于终态 {current}，不可重交异动", http_status=409)

    ct = str(row.change_type or "").upper()
    if ct == "RESUME":
        if current not in {"SUSPENDED", "PRESERVED"}:
            raise AppException("DATA_CONFLICT", "仅休学中或保留学籍中的学生可重交复学申请", http_status=409)
        from app.models import AaStatusChange

        prior = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.student_id == int(student.id),
            AaStatusChange.change_type.in_(("SUSPEND", "PRESERVE")),
            AaStatusChange.status == "EFFECTIVE",
            AaStatusChange.is_deleted.is_(False),
        ).order_by(AaStatusChange.id.desc())).first()
        if prior and prior.expire_date and prior.expire_date < datetime.utcnow():
            raise AppException("DATA_CONFLICT", "休学已超过最长年限，应作退学处理，不可复学", http_status=409)
    elif ct in {"SUSPEND", "PRESERVE", "WITHDRAW", "RETAIN", "TRANSFER_MAJOR", "TRANSFER_CLASS"}:
        if not change.is_enrolled(current):
            raise AppException("DATA_CONFLICT", "仅在籍学生可重交该异动", http_status=409)


def _validate_targets(db, row, student, body) -> None:
    requested_type = str(_value(body, "changeType") or "").strip().upper()
    if requested_type and requested_type != str(row.change_type or "").upper():
        raise AppException("VALIDATION_ERROR", "退回重交不可改变异动类型；如需改类型请撤销后重新申请")

    ct = str(row.change_type or "").upper()
    if ct == "TRANSFER_MAJOR":
        from app.models import Major, SchoolClass

        raw_mid = _value(body, "toMajorId") if _has(body, "toMajorId") else row.to_major_id
        if not raw_mid:
            raise AppException("VALIDATION_ERROR", "转专业需指定目标专业")
        major = db.get(Major, int(raw_mid))
        if not major or major.tenant_id != _tid() or major.is_deleted:
            raise not_found("目标专业不存在")
        if student.major_id and int(major.id) == int(student.major_id):
            raise AppException("DATA_CONFLICT", "目标专业与当前专业相同", http_status=409)

        row.to_major_id = int(major.id)
        row.to_college_id = int(major.college_id) if major.college_id else None

        raw_cid = _value(body, "toClassId") if _has(body, "toClassId") else row.to_class_id
        if raw_cid in (None, ""):
            row.to_class_id = None
        else:
            target = db.get(SchoolClass, int(raw_cid))
            if not target or target.tenant_id != _tid() or target.is_deleted:
                raise not_found("目标班级不存在")
            if int(target.major_id or 0) != int(major.id):
                raise AppException("VALIDATION_ERROR", "目标班级不属于所选专业")
            if str(target.class_status or "").upper() != "NORMAL" or str(target.status or "").upper() != "ACTIVE":
                raise AppException("DATA_CONFLICT", "目标班级非在读状态，不可转入", http_status=409)
            row.to_class_id = int(target.id)
        return

    if ct == "TRANSFER_CLASS":
        from app.models import SchoolClass

        raw_cid = _value(body, "toClassId") if _has(body, "toClassId") else row.to_class_id
        if not raw_cid:
            raise AppException("VALIDATION_ERROR", "转班需指定目标班级")
        target = db.get(SchoolClass, int(raw_cid))
        if not target or target.tenant_id != _tid() or target.is_deleted:
            raise not_found("目标班级不存在")
        if str(target.class_status or "").upper() != "NORMAL" or str(target.status or "").upper() != "ACTIVE":
            raise AppException("DATA_CONFLICT", "目标班级非在读状态，不可转入", http_status=409)
        if int(target.major_id or 0) != int(student.major_id or 0):
            raise AppException("VALIDATION_ERROR", "转班仅限同专业换班，跨专业请使用转专业申请")
        if student.class_id and int(target.id) == int(student.class_id):
            raise AppException("DATA_CONFLICT", "学生已在目标班级", http_status=409)
        row.to_college_id = int(student.college_id) if student.college_id else None
        row.to_major_id = int(student.major_id) if student.major_id else None
        row.to_class_id = int(target.id)


def resubmit_my(user, change_id, body=None) -> dict:
    """Reopen one RETURNED case in place; never creates a second AaStatusChange row."""
    body = body or {}
    try:
        cid = int(change_id)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "changeId 非法") from exc

    from app.models import AaStatusChange, WorkflowInstance, WorkflowTask

    with session() as db:
        row = db.scalars(select(AaStatusChange).where(
            AaStatusChange.id == cid,
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("异动单不存在")

        student = _student_my(db, user)
        if int(row.student_id) != int(student.id):
            raise no_permission("该异动不属于当前学生本人")
        if str(row.status or "").upper() != "RETURNED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已退回的异动可重交", http_status=409)

        _require_version(row, body)
        safety._term_for_change(db, row.term_code)
        _validate_current_fact(db, row, student)

        other_active = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.student_id == int(student.id),
            AaStatusChange.id != int(row.id),
            AaStatusChange.status.in_(list(change._ACTIVE)),
            AaStatusChange.is_deleted.is_(False),
        ).with_for_update()).first()
        if other_active:
            raise AppException("DATA_CONFLICT", "该生已有其它在途学籍异动，不可重交", http_status=409)

        reason = str(_value(body, "reason", row.reason or "") or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "异动事由至少 5 个字")
        _validate_targets(db, row, student, body)

        nodes = change.CHANGE_FLOW.get(str(row.change_type or "").upper(), (None, []))[1]
        if not nodes:
            raise AppException("WORKFLOW_NODE_INVALID", "异动类型未配置审批节点", http_status=409)
        first = nodes[0]

        if not row.workflow_instance_id:
            raise AppException("WORKFLOW_INSTANCE_MISSING", "退回异动缺少原工作流实例，禁止另开新流程", http_status=409)
        inst = db.get(WorkflowInstance, int(row.workflow_instance_id))
        if (
            not inst
            or inst.tenant_id != _tid()
            or inst.is_deleted
            or str(inst.source_module or "") != "academic-affairs"
            or str(inst.source_biz_type or "") != "AA_STATUS_CHANGE"
            or int(inst.source_biz_id or 0) != int(row.id)
        ):
            raise AppException("WORKFLOW_INSTANCE_MISSING", "原工作流实例不存在或归属异常", http_status=409)

        token = safety._CHANGE_CONTEXT.set(safety._change_snapshot(row))
        try:
            assignee = int(change._assignee_for(db, first, row.student_id) or 0)
        finally:
            safety._CHANGE_CONTEXT.reset(token)
        if assignee <= 0:
            raise AppException("WORKFLOW_ASSIGNEE_UNRESOLVED", "首审节点没有唯一真实受理人", http_status=409)

        new_task = WorkflowTask(
            tenant_id=_tid(),
            instance_id=int(inst.id),
            node_code=first,
            assignee_id=assignee,
            status="PENDING",
        )
        db.add(new_task)
        db.flush()

        row.reason = reason
        row.status = "SUBMITTED"
        row.current_node = first
        row.current_task_id = int(new_task.id)
        row.version = int(row.version or 0) + 1
        row.decision_version = int(row.decision_version or 0) + 1
        row.expected_student_version = int(student.version or 0)

        inst.status = "RUNNING"
        inst.current_node = first

        change._todo_upsert(
            db,
            row.id,
            assignee,
            row.student_id,
            f"{change.L_CT.get(row.change_type, row.change_type)}待审（学生退回后重交）",
        )
        change._audit(db, row.id, "RESUBMIT", f"node={first};sameChangeId=1")
        db.commit()
        db.refresh(row)
        return change._row(row, student)
