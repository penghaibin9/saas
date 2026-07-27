"""学工材料补交版本、安全批次和宿舍异常风险投影。

本服务只开放低风险批量动作 ``MATERIAL_REMIND``。任何审批、生效、发放、处分、
风险关闭等高风险动作均不在批量白名单内，必须继续逐条办理。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, no_permission, not_found
from app.core.permissions import has_permission
from app.services.db_service import _iso, _tid, session

_INSTALLED = False

_MATERIAL_STATUS_LABELS = {
    "MISSING": "待补交",
    "PENDING_REVIEW": "待审核",
    "ACCEPTED": "已验收",
    "RETURNED": "已退回补交",
    "WAIVED": "已免交",
}
_SUBMISSION_STATUS_LABELS = {
    "SUBMITTED": "已提交待审核",
    "ACCEPTED": "已验收",
    "RETURNED": "已退回",
    "SUPERSEDED": "历史版本",
}
_BATCH_STATUS_LABELS = {
    "PENDING": "待执行",
    "RUNNING": "执行中",
    "PARTIAL_SUCCESS": "部分成功",
    "SUCCESS": "全部成功",
    "FAILED": "全部失败",
    "CANCELLED": "已取消",
}

_BIZ_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "LEAVE": ("studentAffairs.leave.approve",),
    "AID": ("studentAffairs.aid.approve", "studentAffairs.aid.counselorReview"),
    "FUNDING": ("studentAffairs.funding.approve",),
    "DISCIPLINE": ("studentAffairs.discipline.approve",),
    "DISCIPLINE_APPEAL": ("studentAffairs.discipline.appeal.review",),
    "DORM_TRANSFER": ("studentAffairs.dorm.transfer.approve",),
    "CREDIT_APPEAL": ("studentAffairs.activity.confirm",),
    "SECOND_CLASS_APPEAL": ("studentAffairs.activity.confirm",),
}
_ACTION_KEYS = {
    "LEAVE": "AFFAIRS_LEAVE",
    "AID": "AFFAIRS_AID",
    "FUNDING": "AFFAIRS_FUNDING",
    "DISCIPLINE": "AFFAIRS_DISCIPLINE",
    "DISCIPLINE_APPEAL": "AFFAIRS_DISCIPLINE",
    "DORM_TRANSFER": "AFFAIRS_DORM",
    "CREDIT_APPEAL": "AFFAIRS_ACTIVITY",
    "SECOND_CLASS_APPEAL": "AFFAIRS_ACTIVITY",
}


def _biz(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_")


def _numeric_user_id(user: dict | None) -> int:
    raw = str((user or {}).get("userId") or "").strip()
    for prefix in ("db-", "u_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    if raw.isdigit():
        return int(raw)
    try:
        from app.services.message_identity import resolve_message_user_id
        return int(resolve_message_user_id(user or {}) or 0)
    except Exception:
        return 0


def _user_key(user: dict | None) -> str:
    uid = _numeric_user_id(user)
    return str(uid) if uid else str((user or {}).get("userId") or "unknown")[:64]


def _require_supported_biz(biz_type: str) -> str:
    bt = _biz(biz_type)
    if bt not in _BIZ_PERMISSIONS:
        raise AppException("VALIDATION_ERROR", f"暂不支持该材料业务类型：{bt or '-'}")
    return bt


def _require_biz_permission(user: dict, biz_type: str) -> None:
    bt = _require_supported_biz(biz_type)
    if not any(has_permission(user or {}, code) for code in _BIZ_PERMISSIONS[bt]):
        raise no_permission("当前身份无权维护该业务的补交材料")


def _require_student_scope(db, student_id: int, user: dict) -> None:
    from app.core.affairs_security import build_affairs_context
    build_affairs_context(user or {}, db).require_student(db, int(student_id))


def _resolve_biz_student(db, biz_type: str, biz_id: int) -> int:
    """从业务真表解析学生，禁止信任前端直接传 studentId。"""
    from app.models import (
        AffairsCreditAppeal,
        AidApply,
        CsLeave,
        CsServiceStudent,
        DisciplineAppeal,
        DisciplineCase,
        DormTransfer,
        FundingApplication,
    )

    bt = _require_supported_biz(biz_type)
    row = None
    student_id = None
    if bt == "LEAVE":
        row = db.get(CsLeave, int(biz_id))
        if row:
            student_id = row.student_id
            if not student_id and row.cs_student_id:
                cs = db.get(CsServiceStudent, int(row.cs_student_id))
                student_id = cs.student_id if cs and not cs.is_deleted else None
    elif bt == "AID":
        row = db.get(AidApply, int(biz_id)); student_id = row.student_id if row else None
    elif bt == "FUNDING":
        row = db.get(FundingApplication, int(biz_id)); student_id = row.student_id if row else None
    elif bt == "DISCIPLINE":
        row = db.get(DisciplineCase, int(biz_id)); student_id = row.student_id if row else None
    elif bt == "DISCIPLINE_APPEAL":
        row = db.get(DisciplineAppeal, int(biz_id)); student_id = row.student_id if row else None
    elif bt == "DORM_TRANSFER":
        row = db.get(DormTransfer, int(biz_id)); student_id = row.student_id if row else None
    elif bt in {"CREDIT_APPEAL", "SECOND_CLASS_APPEAL"}:
        row = db.get(AffairsCreditAppeal, int(biz_id)); student_id = row.student_id if row else None

    if not row or getattr(row, "is_deleted", False) or row.tenant_id != _tid():
        raise not_found("业务申请不存在")
    if not student_id:
        raise AppException("DATA_CONFLICT", "该历史业务记录尚未关联统一学生主档，不能登记材料缺项")
    return int(student_id)


def _audit(db, biz_id: int, action: str, detail: str = "") -> None:
    from app.models import AffairsAuditTrail
    user = get_current_user_ctx() or {}
    db.add(AffairsAuditTrail(
        tenant_id=_tid(), biz_type="MATERIAL_REQUIREMENT", biz_id=int(biz_id),
        action=action, operator=user.get("realName") or _user_key(user),
        role_name=user.get("currentRoleCode") or "", detail=(detail or "")[:1000],
        occurred_at=datetime.utcnow(),
    ))


def _register_message_templates() -> None:
    from app.services import message_event_outbox_service as outbox
    templates = {
        "MATERIAL.REQUIRED": ("RETURNED_NOTICE", "材料待补交", "IMPORTANT"),
        "MATERIAL.REMINDED": ("DEADLINE_REMINDER", "材料补交提醒", "IMPORTANT"),
        "MATERIAL.ACCEPTED": ("WORKFLOW_RESULT", "材料已验收", "NORMAL"),
        "MATERIAL.RETURNED": ("RETURNED_NOTICE", "补交材料被退回", "IMPORTANT"),
        "MATERIAL.WAIVED": ("STATUS_CHANGED", "材料已免交", "NORMAL"),
    }
    for code, (message_type, title, priority) in templates.items():
        outbox._EVENT_TEMPLATES.setdefault(code, {
            "source_module": "student-affairs",
            "category": "REMINDER" if "REMIND" in code else "BUSINESS",
            "priority": priority,
            "message_type": message_type,
            "title": title,
            "require_ack": False,
        })


def _emit_student_notice(db, requirement, event_code: str, title: str, content: str, *, extra: str = "") -> None:
    from app.services.message_event_outbox_service import emit_receiver_notice
    bt = _biz(requirement.biz_type)
    emit_receiver_notice(
        db,
        event_code=event_code,
        source_module="student-affairs",
        source_biz_type=bt,
        source_biz_id=int(requirement.biz_id),
        receiver_id=int(requirement.student_id),
        title=title,
        content=content,
        receiver_as="student",
        action_key=_ACTION_KEYS.get(bt, "AFFAIRS_APPLICATIONS"),
        action_params={
            "bizType": bt,
            "recordId": str(requirement.biz_id),
            "materialRequirementId": str(requirement.id),
        },
        dedup_extra=f"material:{requirement.id}:{event_code}:{extra}",
    )


def _drain_messages() -> None:
    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="affairs-material-inline")


def _todo_upsert(db, requirement) -> None:
    from app.models import UnifiedTodo
    owner = int(requirement.review_owner_id or 0)
    if owner <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "材料审核责任人未配置")
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type == "MATERIAL_REQUIREMENT",
        UnifiedTodo.source_biz_id == int(requirement.id),
        UnifiedTodo.todo_type == "MATERIAL_REVIEW",
        UnifiedTodo.assignee_id == owner,
        UnifiedTodo.is_deleted.is_(False),
    )).first()
    title = f"补交材料待审核：{requirement.item_name}"
    if row:
        row.status = "PENDING"
        row.title = title
        row.student_id = int(requirement.student_id)
        row.due_at = requirement.due_at
        row.version = int(row.version or 0) + 1
    else:
        db.add(UnifiedTodo(
            tenant_id=_tid(), source_module="student-affairs",
            source_biz_type="MATERIAL_REQUIREMENT", source_biz_id=int(requirement.id),
            todo_type="MATERIAL_REVIEW", assignee_id=owner,
            student_id=int(requirement.student_id), title=title,
            status="PENDING", due_at=requirement.due_at,
        ))


def _todo_done(db, requirement_id: int) -> None:
    from app.models import UnifiedTodo
    rows = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type == "MATERIAL_REQUIREMENT",
        UnifiedTodo.source_biz_id == int(requirement_id),
        UnifiedTodo.todo_type == "MATERIAL_REVIEW",
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    )).all()
    for row in rows:
        row.status = "DONE"
        row.version = int(row.version or 0) + 1


def _submission_rows(db, requirement_ids: Iterable[int]) -> dict[int, list[Any]]:
    from app.models.affairs_operations import AffairsMaterialSubmission
    ids = {int(x) for x in requirement_ids}
    result: dict[int, list[Any]] = {x: [] for x in ids}
    if not ids:
        return result
    rows = db.scalars(select(AffairsMaterialSubmission).where(
        AffairsMaterialSubmission.tenant_id == _tid(),
        AffairsMaterialSubmission.requirement_id.in_(ids),
        AffairsMaterialSubmission.is_deleted.is_(False),
    ).order_by(AffairsMaterialSubmission.requirement_id, AffairsMaterialSubmission.version_no.desc())).all()
    for row in rows:
        result.setdefault(int(row.requirement_id), []).append(row)
    return result


def _submission_dict(row, current_id: int | None = None) -> dict:
    return {
        "submissionId": str(row.id),
        "versionNo": int(row.version_no or 0),
        "fileId": str(row.file_id),
        "fileName": row.file_name or "补交材料",
        "status": row.status,
        "statusLabel": _SUBMISSION_STATUS_LABELS.get(row.status, row.status),
        "submittedAt": _iso(row.submitted_at or row.created_at),
        "reviewedAt": _iso(row.reviewed_at),
        "reviewNote": row.review_note or "",
        "current": int(current_id or 0) == int(row.id),
        "downloadable": not bool(row.is_deleted),
        "supersedesId": str(row.supersedes_id or ""),
    }


def _requirement_dict(row, submissions: list[Any], *, student_view: bool, owner_name: str = "") -> dict:
    current = next((x for x in submissions if int(x.id) == int(row.current_submission_id or 0)), None)
    now = datetime.utcnow()
    overdue = bool(row.due_at and row.due_at < now and row.status in {"MISSING", "RETURNED"})
    actions: list[str] = []
    if student_view and row.status in {"MISSING", "RETURNED"}:
        actions.append("SUBMIT_MATERIAL")
    if not student_view and row.status == "PENDING_REVIEW":
        actions.extend(["ACCEPT_MATERIAL", "RETURN_MATERIAL"])
    if not student_view and row.status in {"MISSING", "RETURNED", "PENDING_REVIEW"}:
        actions.append("WAIVE_MATERIAL")
    versions = [_submission_dict(x, row.current_submission_id) for x in submissions]
    return {
        "requirementId": str(row.id),
        "studentId": str(row.student_id),
        "bizType": row.biz_type,
        "bizId": str(row.biz_id),
        "itemCode": row.item_code,
        "itemName": row.item_name,
        "requirementReason": row.requirement_reason or "",
        "status": row.status,
        "statusLabel": _MATERIAL_STATUS_LABELS.get(row.status, row.status),
        "returnRound": int(row.return_round or 1),
        "dueAt": _iso(row.due_at),
        "overdue": overdue,
        "reviewOwnerId": str(row.review_owner_id or ""),
        "reviewOwner": owner_name or "",
        "currentSubmissionId": str(row.current_submission_id or ""),
        "currentSubmission": _submission_dict(current, row.current_submission_id) if current else None,
        "versions": versions,
        "versionCount": len(versions),
        "version": int(row.version or 0),
        "allowedActions": actions,
        "exceptionProjection": {
            "type": "MATERIAL_MISSING",
            "responsibleUserId": str(row.review_owner_id or ""),
            "responsibleUser": owner_name or "",
            "dueAt": _iso(row.due_at),
            "overdue": overdue,
            "status": row.status,
            "canEscalate": overdue and row.status in {"MISSING", "RETURNED"},
        },
    }


def create_material_requirement(user: dict, payload: dict) -> dict:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement

    bt = _require_supported_biz(payload.get("bizType"))
    _require_biz_permission(user, bt)
    biz_id = int(payload.get("bizId") or 0)
    if biz_id <= 0:
        raise AppException("VALIDATION_ERROR", "业务记录ID无效")
    item_code = str(payload.get("itemCode") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,99}", item_code):
        raise AppException("VALIDATION_ERROR", "材料项编码需为1-100位大写字母、数字、下划线或短横线")
    item_name = str(payload.get("itemName") or "").strip()
    if not 2 <= len(item_name) <= 200:
        raise AppException("VALIDATION_ERROR", "材料项名称需2-200字")
    reason = str(payload.get("requirementReason") or "").strip()
    if reason and not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "缺项说明需5-500字")
    owner = _numeric_user_id(user)
    if owner <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "当前教师账号未绑定可用用户ID")

    created = False
    with session() as db:
        student_id = _resolve_biz_student(db, bt, biz_id)
        _require_student_scope(db, student_id, user)
        row = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.biz_type == bt,
            AffairsMaterialRequirement.biz_id == biz_id,
            AffairsMaterialRequirement.item_code == item_code,
            AffairsMaterialRequirement.is_deleted.is_(False),
        ).with_for_update()).first()
        if row:
            if row.status in {"MISSING", "RETURNED", "PENDING_REVIEW"}:
                raise AppException("DATA_CONFLICT", "该材料缺项仍在处理中，请勿重复登记")
            row.status = "MISSING"
            row.return_round = int(row.return_round or 0) + 1
            row.requirement_reason = reason or row.requirement_reason
            row.item_name = item_name
            row.due_at = payload.get("dueAt")
            row.review_owner_id = owner
            row.accepted_at = None
            row.version = int(row.version or 0) + 1
            action = "REOPEN_REQUIREMENT"
        else:
            row = AffairsMaterialRequirement(
                tenant_id=_tid(), student_id=student_id, biz_type=bt, biz_id=biz_id,
                item_code=item_code, item_name=item_name,
                requirement_reason=reason or None, status="MISSING", return_round=1,
                due_at=payload.get("dueAt"), review_owner_id=owner,
                created_by=owner, updated_by=owner,
            )
            db.add(row); db.flush(); created = True
            action = "CREATE_REQUIREMENT"
        _audit(db, row.id, action, f"{bt}:{biz_id}:{item_code}:{item_name}")
        _emit_student_notice(
            db, row, "MATERIAL.REQUIRED", "材料待补交",
            f"{item_name}需要补交，请在学工申请中查看要求并上传材料。",
            extra=str(row.return_round),
        )
        db.commit(); db.refresh(row)
        owner_row = db.get(User, owner)
        result = _requirement_dict(row, [], student_view=False,
                                   owner_name=(owner_row.real_name if owner_row else ""))
        result["created"] = created
    _drain_messages()
    return result


def list_teacher_requirements(user: dict, *, status: str | None = None, page: int = 1,
                              page_size: int = 50) -> tuple[list[dict], int]:
    from app.models import StudentProfile, User
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.services.affairs_dashboard_service import _allowed_class_ids

    page, page_size = max(1, int(page)), min(100, max(1, int(page_size)))
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id == AffairsMaterialRequirement.student_id,
            StudentProfile.is_deleted.is_(False),
        ]
        if status:
            conds.append(AffairsMaterialRequirement.status == str(status).upper())
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        total = int(db.scalar(select(func.count()).select_from(AffairsMaterialRequirement).join(
            StudentProfile, StudentProfile.id == AffairsMaterialRequirement.student_id
        ).where(*conds)) or 0)
        rows = db.scalars(select(AffairsMaterialRequirement).join(
            StudentProfile, StudentProfile.id == AffairsMaterialRequirement.student_id
        ).where(*conds).order_by(AffairsMaterialRequirement.id.desc())
            .offset((page - 1) * page_size).limit(page_size)).all()
        visible = [row for row in rows if any(has_permission(user, code) for code in _BIZ_PERMISSIONS.get(row.biz_type, ()))]
        submissions = _submission_rows(db, [x.id for x in visible])
        owner_ids = {int(x.review_owner_id) for x in visible if x.review_owner_id}
        owners = {int(x.id): x.real_name for x in db.scalars(select(User).where(
            User.tenant_id == _tid(), User.id.in_(owner_ids or {-1}), User.is_deleted.is_(False)
        )).all()}
        return [
            _requirement_dict(row, submissions.get(int(row.id), []), student_view=False,
                              owner_name=owners.get(int(row.review_owner_id or 0), ""))
            for row in visible
        ], total


def list_my_requirements(user: dict, *, biz_type: str | None = None, biz_id: int | None = None) -> list[dict]:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        conds = [
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.student_id == int(student.id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        ]
        if biz_type:
            conds.append(AffairsMaterialRequirement.biz_type == _biz(biz_type))
        if biz_id:
            conds.append(AffairsMaterialRequirement.biz_id == int(biz_id))
        rows = db.scalars(select(AffairsMaterialRequirement).where(*conds)
                          .order_by(AffairsMaterialRequirement.id.desc())).all()
        submissions = _submission_rows(db, [x.id for x in rows])
        owner_ids = {int(x.review_owner_id) for x in rows if x.review_owner_id}
        owners = {int(x.id): x.real_name for x in db.scalars(select(User).where(
            User.tenant_id == _tid(), User.id.in_(owner_ids or {-1}), User.is_deleted.is_(False)
        )).all()}
        return [
            _requirement_dict(row, submissions.get(int(row.id), []), student_view=True,
                              owner_name=owners.get(int(row.review_owner_id or 0), ""))
            for row in rows
        ]


def submit_material(user: dict, requirement_id: int, *, file_id: int, note: str = "",
                    expected_version: int | None) -> dict:
    from app.models import AffairsAttachment, FileObject
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    actor_id = _numeric_user_id(user)
    if actor_id <= 0:
        raise AppException("UNAUTHORIZED", "学生账号未建立稳定用户绑定")
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        req = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.id == int(requirement_id),
            AffairsMaterialRequirement.student_id == int(student.id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        ).with_for_update()).first()
        if not req:
            raise not_found("材料缺项不存在或不属于本人")
        if req.status not in {"MISSING", "RETURNED"}:
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前材料状态不可补交，请刷新")
        check_version(req.version, expected_version)
        file = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False), FileObject.status.in_(("AVAILABLE", "STORED")),
        ).with_for_update()).first()
        if not file:
            raise not_found("上传文件不存在或不可用")
        if int(file.owner_user_id or file.created_by or 0) != actor_id:
            raise no_permission("只能提交本人上传的文件")
        latest = db.scalars(select(AffairsMaterialSubmission).where(
            AffairsMaterialSubmission.tenant_id == _tid(),
            AffairsMaterialSubmission.requirement_id == int(req.id),
            AffairsMaterialSubmission.is_deleted.is_(False),
        ).order_by(AffairsMaterialSubmission.version_no.desc()).with_for_update()).first()
        if latest and latest.status not in {"ACCEPTED", "SUPERSEDED"}:
            latest.status = "SUPERSEDED"
            latest.version = int(latest.version or 0) + 1
        attachment = AffairsAttachment(
            tenant_id=_tid(), biz_type="MATERIAL_SUPPLEMENT", biz_id=int(req.id),
            file_id=int(file.id), file_name=file.file_name,
            note=(note or f"补交项：{req.item_name}")[:500], created_by=actor_id,
        )
        db.add(attachment); db.flush()
        version_no = int(latest.version_no if latest else 0) + 1
        submission = AffairsMaterialSubmission(
            tenant_id=_tid(), requirement_id=int(req.id), student_id=int(student.id),
            version_no=version_no, affairs_attachment_id=int(attachment.id), file_id=int(file.id),
            file_name=file.file_name, status="SUBMITTED", submitted_by=str(actor_id),
            submitted_at=datetime.utcnow(), supersedes_id=int(latest.id) if latest else None,
            created_by=actor_id, updated_by=actor_id,
        )
        db.add(submission); db.flush()
        file.biz_type = "MATERIAL_REQUIREMENT"
        file.biz_id = str(req.id)
        file.visibility = "STUDENT_SELF"
        req.current_submission_id = int(submission.id)
        req.status = "PENDING_REVIEW"
        req.version = int(req.version or 0) + 1
        req.updated_by = actor_id
        _todo_upsert(db, req)
        _audit(db, req.id, "SUBMIT_MATERIAL", f"version={version_no};file={file.id}")
        db.commit(); db.refresh(req); db.refresh(submission)
        versions = _submission_rows(db, [req.id]).get(int(req.id), [])
        result = _requirement_dict(req, versions, student_view=True)
    return result


def review_material(user: dict, requirement_id: int, *, action: str, reason: str = "",
                    expected_version: int | None) -> dict:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.core.affairs_security import build_affairs_context

    act = str(action or "").strip().upper()
    if act not in {"ACCEPT", "RETURN", "WAIVE"}:
        raise AppException("VALIDATION_ERROR", "材料审核动作仅支持 ACCEPT/RETURN/WAIVE")
    text = str(reason or "").strip()
    if act == "RETURN" and not 5 <= len(text) <= 500:
        raise AppException("VALIDATION_ERROR", "退回原因需5-500字")
    actor = _numeric_user_id(user)
    with session() as db:
        req = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.id == int(requirement_id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        ).with_for_update()).first()
        if not req:
            raise not_found("材料缺项不存在")
        _require_biz_permission(user, req.biz_type)
        _require_student_scope(db, req.student_id, user)
        ctx = build_affairs_context(user or {}, db)
        if ctx.scope_type != "TENANT_ALL" and int(req.review_owner_id or 0) != actor:
            raise no_permission("仅材料审核责任人或学校级学工管理员可处理")
        check_version(req.version, expected_version)
        current = db.get(AffairsMaterialSubmission, int(req.current_submission_id)) if req.current_submission_id else None
        if act in {"ACCEPT", "RETURN"}:
            if req.status != "PENDING_REVIEW" or not current or current.status != "SUBMITTED":
                raise AppException("APPROVAL_VERSION_CONFLICT", "当前没有可审核的最新补交版本")
        now = datetime.utcnow()
        if act == "ACCEPT":
            current.status = "ACCEPTED"; current.reviewed_by = str(actor); current.reviewed_at = now
            current.review_note = text or "材料验收通过"; current.version = int(current.version or 0) + 1
            req.status = "ACCEPTED"; req.accepted_at = now
            event, title, content = "MATERIAL.ACCEPTED", "材料已验收", f"{req.item_name}已验收通过。"
        elif act == "RETURN":
            current.status = "RETURNED"; current.reviewed_by = str(actor); current.reviewed_at = now
            current.review_note = text; current.version = int(current.version or 0) + 1
            req.status = "RETURNED"
            event, title, content = "MATERIAL.RETURNED", "补交材料被退回", f"{req.item_name}需重新补交：{text}"
        else:
            if req.status not in {"MISSING", "RETURNED", "PENDING_REVIEW"}:
                raise AppException("APPROVAL_VERSION_CONFLICT", "当前材料状态不可免交")
            if current and current.status == "SUBMITTED":
                current.status = "SUPERSEDED"; current.reviewed_by = str(actor); current.reviewed_at = now
                current.review_note = text or "学校免交"; current.version = int(current.version or 0) + 1
            req.status = "WAIVED"; req.accepted_at = now
            event, title, content = "MATERIAL.WAIVED", "材料已免交", f"{req.item_name}已由学校确认免交。"
        req.version = int(req.version or 0) + 1
        req.updated_by = actor or None
        _todo_done(db, req.id)
        _audit(db, req.id, f"MATERIAL_{act}", text)
        _emit_student_notice(db, req, event, title, content, extra=str(req.version))
        db.commit(); db.refresh(req)
        versions = _submission_rows(db, [req.id]).get(int(req.id), [])
        owner = db.get(User, int(req.review_owner_id)) if req.review_owner_id else None
        result = _requirement_dict(req, versions, student_view=False,
                                   owner_name=(owner.real_name if owner else ""))
    _drain_messages()
    return result


def _material_contract(original):
    """把正式缺项/版本表投影进现有学生“我的申请”材料合同。"""
    def materials(db, *, biz_types: Iterable[str], biz_id: int, status: str) -> dict:
        from app.models.affairs_operations import AffairsMaterialRequirement
        from app.services.mobile_student_service import resolve_student

        base = original(db, biz_types=biz_types, biz_id=biz_id, status=status)
        user = get_current_user_ctx() or {}
        try:
            student = resolve_student(db, user)
        except Exception:
            student = None
        variants = {_biz(x) for x in biz_types if x}
        rows = []
        if student and variants:
            rows = db.scalars(select(AffairsMaterialRequirement).where(
                AffairsMaterialRequirement.tenant_id == _tid(),
                AffairsMaterialRequirement.student_id == int(student.id),
                AffairsMaterialRequirement.biz_type.in_(variants),
                AffairsMaterialRequirement.biz_id == int(biz_id),
                AffairsMaterialRequirement.is_deleted.is_(False),
            ).order_by(AffairsMaterialRequirement.id)).all()
        submissions = _submission_rows(db, [x.id for x in rows])
        missing = [
            _requirement_dict(row, submissions.get(int(row.id), []), student_view=True)
            for row in rows
        ]
        base["missingItems"] = missing
        base["missingItemsKnown"] = True
        states = {x.status for x in rows}
        if "PENDING_REVIEW" in states:
            base["supplementStatus"] = "PENDING_REVIEW"
        elif states.intersection({"MISSING", "RETURNED"}):
            base["supplementStatus"] = "PENDING_STUDENT_SUPPLEMENT"
        elif rows and states.issubset({"ACCEPTED", "WAIVED"}):
            base["supplementStatus"] = "COMPLETE"
        return base
    return materials


def _merge_material_contract(original):
    def merge(*contracts: dict) -> dict:
        base = original(*contracts)
        missing: list[dict] = []
        for contract in contracts:
            missing.extend(contract.get("missingItems") or [])
        base["missingItems"] = missing
        base["missingItemsKnown"] = all(c.get("missingItemsKnown", False) for c in contracts) if contracts else True
        statuses = {c.get("supplementStatus") for c in contracts}
        for candidate in ("PENDING_REVIEW", "PENDING_STUDENT_SUPPLEMENT", "PENDING_STUDENT_EDIT", "COMPLETE"):
            if candidate in statuses:
                base["supplementStatus"] = candidate
                break
        return base
    return merge


def _batch_job_dict(db, job, include_items: bool = True) -> dict:
    from app.models.affairs_operations import AffairsBatchJobItem
    items = []
    if include_items:
        rows = db.scalars(select(AffairsBatchJobItem).where(
            AffairsBatchJobItem.tenant_id == _tid(),
            AffairsBatchJobItem.batch_job_id == int(job.id),
            AffairsBatchJobItem.is_deleted.is_(False),
        ).order_by(AffairsBatchJobItem.id)).all()
        items = [{
            "itemId": str(row.id), "itemKey": row.item_key, "bizType": row.biz_type,
            "bizId": str(row.biz_id), "action": row.action, "status": row.status,
            "attemptCount": int(row.attempt_count or 0), "errorCode": row.error_code or "",
            "errorMessage": row.error_message or "", "result": row.result_json or {},
            "expectedVersion": row.expected_version, "startedAt": _iso(row.started_at),
            "completedAt": _iso(row.completed_at),
        } for row in rows]
    can_retry = int(job.failure_count or 0) > 0 and job.status in {"FAILED", "PARTIAL_SUCCESS"}
    return {
        "batchJobId": str(job.id), "batchNo": job.batch_no, "jobType": job.job_type,
        "status": job.status, "statusLabel": _BATCH_STATUS_LABELS.get(job.status, job.status),
        "idempotencyKey": job.idempotency_key, "requestedBy": job.requested_by,
        "retryOfId": str(job.retry_of_id or ""), "totalCount": int(job.total_count or 0),
        "successCount": int(job.success_count or 0), "failureCount": int(job.failure_count or 0),
        "pendingCount": int(job.pending_count or 0), "startedAt": _iso(job.started_at),
        "completedAt": _iso(job.completed_at), "lastError": job.last_error or "",
        "allowedActions": ["RETRY_FAILED"] if can_retry else [], "items": items,
        "exceptionProjection": {
            "type": "BATCH_PARTIAL_FAILURE", "hasException": int(job.failure_count or 0) > 0,
            "responsibleUser": job.requested_by, "failureCount": int(job.failure_count or 0),
            "canRetry": can_retry, "status": job.status,
        },
    }


def _refresh_batch_summary(job_id: int) -> dict:
    from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem
    with session() as db:
        job = db.scalars(select(AffairsBatchJob).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.id == int(job_id),
            AffairsBatchJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if not job:
            raise not_found("批次不存在")
        rows = db.scalars(select(AffairsBatchJobItem.status).where(
            AffairsBatchJobItem.tenant_id == _tid(),
            AffairsBatchJobItem.batch_job_id == int(job.id),
            AffairsBatchJobItem.is_deleted.is_(False),
        )).all()
        success_count = sum(1 for x in rows if x == "SUCCESS")
        failure_count = sum(1 for x in rows if x == "FAILED")
        pending_count = sum(1 for x in rows if x in {"PENDING", "RUNNING"})
        job.total_count = len(rows); job.success_count = success_count
        job.failure_count = failure_count; job.pending_count = pending_count
        if pending_count:
            job.status = "RUNNING"
        elif success_count and failure_count:
            job.status = "PARTIAL_SUCCESS"
        elif success_count:
            job.status = "SUCCESS"
        else:
            job.status = "FAILED"
        job.completed_at = None if pending_count else datetime.utcnow()
        job.last_error = f"{failure_count}条失败" if failure_count else None
        job.version = int(job.version or 0) + 1
        _audit(db, job.id, "BATCH_COMPLETE", f"success={success_count};failed={failure_count}")
        db.commit(); db.refresh(job)
        return _batch_job_dict(db, job)


def _execute_batch_item(item_id: int, user: dict) -> None:
    from app.models.affairs_operations import AffairsBatchJobItem, AffairsMaterialRequirement
    try:
        with session() as db:
            item = db.scalars(select(AffairsBatchJobItem).where(
                AffairsBatchJobItem.tenant_id == _tid(), AffairsBatchJobItem.id == int(item_id),
                AffairsBatchJobItem.is_deleted.is_(False),
            ).with_for_update()).first()
            if not item or item.status not in {"PENDING", "FAILED"}:
                return
            item.status = "RUNNING"; item.attempt_count = int(item.attempt_count or 0) + 1
            item.started_at = datetime.utcnow(); item.error_code = None; item.error_message = None
            db.flush()
            if item.action != "REMIND" or item.biz_type != "MATERIAL_REQUIREMENT":
                raise AppException("NO_PERMISSION", "该动作不在低风险批量白名单")
            req = db.scalars(select(AffairsMaterialRequirement).where(
                AffairsMaterialRequirement.tenant_id == _tid(),
                AffairsMaterialRequirement.id == int(item.biz_id),
                AffairsMaterialRequirement.is_deleted.is_(False),
            ).with_for_update()).first()
            if not req:
                raise not_found("材料缺项不存在")
            _require_biz_permission(user, req.biz_type)
            _require_student_scope(db, req.student_id, user)
            if item.expected_version is not None:
                check_version(req.version, item.expected_version)
            if req.status not in {"MISSING", "RETURNED"}:
                raise AppException("APPROVAL_VERSION_CONFLICT", "该材料当前无需提醒补交")
            _emit_student_notice(
                db, req, "MATERIAL.REMINDED", "材料补交提醒",
                f"请尽快补交：{req.item_name}。",
                extra=f"batch-item:{item.id}:attempt:{item.attempt_count}",
            )
            item.status = "SUCCESS"; item.completed_at = datetime.utcnow()
            item.result_json = {"requirementId": str(req.id), "reminded": True}
            item.version = int(item.version or 0) + 1
            db.commit()
    except AppException as exc:
        with session() as db:
            row = db.get(AffairsBatchJobItem, int(item_id))
            if row and row.tenant_id == _tid() and not row.is_deleted:
                row.status = "FAILED"; row.error_code = exc.code; row.error_message = exc.message[:1000]
                row.completed_at = datetime.utcnow(); row.version = int(row.version or 0) + 1
                db.commit()
    except Exception as exc:  # noqa: BLE001
        with session() as db:
            row = db.get(AffairsBatchJobItem, int(item_id))
            if row and row.tenant_id == _tid() and not row.is_deleted:
                row.status = "FAILED"; row.error_code = "SERVER_ERROR"
                row.error_message = str(exc)[:1000]; row.completed_at = datetime.utcnow()
                row.version = int(row.version or 0) + 1; db.commit()


def run_batch_job(job_id: int, user: dict, *, failed_only: bool = False) -> dict:
    from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem
    with session() as db:
        job = db.scalars(select(AffairsBatchJob).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.id == int(job_id),
            AffairsBatchJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if not job:
            raise not_found("批次不存在")
        if job.job_type != "MATERIAL_REMIND":
            raise AppException("NO_PERMISSION", "该批次类型不在低风险白名单")
        if job.requested_by != _user_key(user):
            from app.core.affairs_security import build_affairs_context
            if build_affairs_context(user or {}, db).scope_type != "TENANT_ALL":
                raise no_permission("只能重试本人创建的批次")
        statuses = {"FAILED"} if failed_only else {"PENDING", "FAILED"}
        item_ids = list(db.scalars(select(AffairsBatchJobItem.id).where(
            AffairsBatchJobItem.tenant_id == _tid(),
            AffairsBatchJobItem.batch_job_id == int(job.id),
            AffairsBatchJobItem.status.in_(statuses),
            AffairsBatchJobItem.is_deleted.is_(False),
        ).order_by(AffairsBatchJobItem.id)).all())
        job.status = "RUNNING"; job.started_at = job.started_at or datetime.utcnow()
        job.completed_at = None; job.version = int(job.version or 0) + 1
        _audit(db, job.id, "BATCH_RETRY" if failed_only else "BATCH_RUN", f"items={len(item_ids)}")
        db.commit()
    for item_id in item_ids:
        _execute_batch_item(int(item_id), user)
    result = _refresh_batch_summary(job_id)
    _drain_messages()
    return result


def create_batch_job(user: dict, payload: dict) -> dict:
    from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem

    job_type = str(payload.get("jobType") or "").strip().upper()
    if job_type != "MATERIAL_REMIND":
        raise AppException("NO_PERMISSION", "仅开放低风险批量材料提醒，审批/发放/处分等必须逐条处理")
    key = str(payload.get("idempotencyKey") or "").strip()
    if not 8 <= len(key) <= 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", key):
        raise AppException("VALIDATION_ERROR", "幂等键需8-128位字母、数字或 ._:-")
    raw_items = payload.get("items") or []
    if not 1 <= len(raw_items) <= 200:
        raise AppException("VALIDATION_ERROR", "每个批次需1-200条记录")
    requirement_ids = [int(x.get("requirementId") or 0) for x in raw_items]
    if any(x <= 0 for x in requirement_ids) or len(set(requirement_ids)) != len(requirement_ids):
        raise AppException("VALIDATION_ERROR", "批次记录ID无效或重复")
    requester = _user_key(user)
    with session() as db:
        existed = db.scalars(select(AffairsBatchJob).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.job_type == job_type,
            AffairsBatchJob.idempotency_key == key, AffairsBatchJob.is_deleted.is_(False),
        )).first()
        if existed:
            return _batch_job_dict(db, existed)
        job = AffairsBatchJob(
            tenant_id=_tid(), batch_no=f"AFB-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}",
            job_type=job_type, idempotency_key=key, status="PENDING", requested_by=requester,
            request_json={"requirementIds": requirement_ids}, total_count=len(raw_items),
            pending_count=len(raw_items), created_by=_numeric_user_id(user) or None,
        )
        db.add(job); db.flush()
        for raw, requirement_id in zip(raw_items, requirement_ids):
            db.add(AffairsBatchJobItem(
                tenant_id=_tid(), batch_job_id=int(job.id), item_key=f"material:{requirement_id}",
                todo_type="MATERIAL_REVIEW", biz_type="MATERIAL_REQUIREMENT", biz_id=requirement_id,
                action="REMIND", expected_version=raw.get("version"), payload_json={}, status="PENDING",
                created_by=_numeric_user_id(user) or None,
            ))
        _audit(db, job.id, "BATCH_CREATE", f"type={job_type};items={len(raw_items)}")
        try:
            db.commit(); db.refresh(job)
        except IntegrityError as exc:
            db.rollback()
            existed = db.scalars(select(AffairsBatchJob).where(
                AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.job_type == job_type,
                AffairsBatchJob.idempotency_key == key, AffairsBatchJob.is_deleted.is_(False),
            )).first()
            if existed:
                return _batch_job_dict(db, existed)
            raise AppException("IDEMPOTENCY_CONFLICT", "批次幂等键冲突，请刷新") from exc
    return run_batch_job(int(job.id), user)


def list_batch_jobs(user: dict, *, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    from app.models.affairs_operations import AffairsBatchJob
    page, page_size = max(1, int(page)), min(100, max(1, int(page_size)))
    with session() as db:
        from app.core.affairs_security import build_affairs_context
        ctx = build_affairs_context(user or {}, db)
        conds = [AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.is_deleted.is_(False)]
        if ctx.scope_type != "TENANT_ALL":
            conds.append(AffairsBatchJob.requested_by == _user_key(user))
        total = int(db.scalar(select(func.count()).select_from(AffairsBatchJob).where(*conds)) or 0)
        rows = db.scalars(select(AffairsBatchJob).where(*conds).order_by(AffairsBatchJob.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return [_batch_job_dict(db, row, include_items=False) for row in rows], total


def get_batch_job(user: dict, job_id: int) -> dict:
    from app.models.affairs_operations import AffairsBatchJob
    with session() as db:
        job = db.scalars(select(AffairsBatchJob).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.id == int(job_id),
            AffairsBatchJob.is_deleted.is_(False),
        )).first()
        if not job:
            raise not_found("批次不存在")
        from app.core.affairs_security import build_affairs_context
        if job.requested_by != _user_key(user) and build_affairs_context(user or {}, db).scope_type != "TENANT_ALL":
            raise no_permission("无权查看该批次")
        return _batch_job_dict(db, job)


def _risk_allowed_actions(db, risk, user: dict) -> list[str]:
    from app.core.affairs_security import build_affairs_context
    from app.services import affairs_risk_service as risk_service
    ctx = build_affairs_context(user or {}, db)
    uid = _numeric_user_id(user)
    role = str((user or {}).get("currentRoleCode") or "").upper()
    actions = []
    for action, rule in risk_service.RISK_TRANSITIONS.items():
        if risk.status not in rule["from"] or not has_permission(user, rule["permission"]):
            continue
        rel = rule.get("relationship")
        if rel == "OWNER_OR_ADMIN" and ctx.scope_type != "TENANT_ALL" and int(risk.owner_id or 0) != uid:
            continue
        if rel == "SUPERIOR" and ctx.scope_type != "TENANT_ALL" and role not in {
            "COLLEGE_ADMIN", "COLLEGE_SA", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SCHOOL_ADMIN"
        }:
            continue
        actions.append(action)
    return actions


def _install_dorm_risk_projection() -> None:
    from app.services import affairs_dorm_service as dorm
    from app.services import affairs_risk_service as risk_service
    from app.services.affairs_sla import risk_due_at, risk_is_overdue

    original_list = dorm.list_exceptions
    original_handle = dorm.handle_exception

    def project(items: list[dict], user: dict) -> list[dict]:
        from app.models import AffairsRiskRecord, User
        ids = {int(x["exceptionId"]) for x in items if str(x.get("exceptionId") or "").isdigit()}
        if not ids:
            return items
        with session() as db:
            risks = db.scalars(select(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.source == "DORM",
                AffairsRiskRecord.source_ref_id.in_(ids), AffairsRiskRecord.is_deleted.is_(False),
            ).order_by(AffairsRiskRecord.id.desc())).all()
            risk_map = {}
            for risk in risks:
                risk_map.setdefault(int(risk.source_ref_id), risk)
            owner_ids = {int(x.owner_id) for x in risks if x.owner_id}
            owners = {int(x.id): x.real_name for x in db.scalars(select(User).where(
                User.tenant_id == _tid(), User.id.in_(owner_ids or {-1}), User.is_deleted.is_(False)
            )).all()}
            for item in items:
                rid = int(item["exceptionId"]) if str(item.get("exceptionId") or "").isdigit() else 0
                risk = risk_map.get(rid)
                if not risk:
                    item["riskProjection"] = {"linked": False, "source": "DORM", "sourceRefId": str(rid)}
                    item["relatedRiskId"] = ""
                    continue
                due = risk_due_at(risk)
                projection = {
                    "linked": True, "riskId": str(risk.id), "source": risk.source,
                    "sourceRefId": str(risk.source_ref_id or ""), "riskLevel": risk.risk_level,
                    "status": risk.status, "statusLabel": risk_service.L_RISK.get(risk.status, risk.status),
                    "ownerId": str(risk.owner_id or ""),
                    "ownerName": owners.get(int(risk.owner_id or 0), ""),
                    "dueAt": _iso(due), "overdue": risk_is_overdue(risk),
                    "allowedActions": _risk_allowed_actions(db, risk, user),
                    "version": int(risk.version or 0),
                    "actionKey": "AFFAIRS_RISK",
                    "actionParams": {"riskId": str(risk.id), "recordId": str(risk.id)},
                }
                item["riskProjection"] = projection
                item["relatedRiskId"] = str(risk.id)
                item["riskStatus"] = risk.status
                item["riskOwner"] = projection["ownerName"]
                item["riskDueAt"] = projection["dueAt"]
                item["riskOverdue"] = projection["overdue"]
        return items

    def list_exceptions(user, status=None, page=1, page_size=50, student_id=None):
        items, total = original_list(user, status=status, page=page, page_size=page_size, student_id=student_id)
        return project(items, user), total

    def handle_exception(exception_id, user, note="", expected_version=None):
        result = original_handle(exception_id, user, note=note, expected_version=expected_version)
        projected = project([{"exceptionId": str(exception_id)}], user)[0]
        result["riskProjection"] = projected.get("riskProjection")
        result["relatedRiskId"] = projected.get("relatedRiskId") or ""
        return result

    dorm.list_exceptions = list_exceptions
    dorm.handle_exception = handle_exception


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _register_message_templates()
    from app.services import affairs_student_contract_service as contract
    contract._materials = _material_contract(contract._materials)
    contract._merge_materials = _merge_material_contract(contract._merge_materials)
    _install_dorm_risk_projection()
    _INSTALLED = True
