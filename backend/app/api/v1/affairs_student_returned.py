"""学生本人困难认定、奖助申请退回修改与重新提交。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.optimistic_lock import atomic_claim_version
from app.core.response import success
from app.core.security import get_current_user
from app.services.db_service import _tid, session

router = APIRouter(tags=["学工中心·退回重提"])


def _student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    _require_student(user)
    row = resolve_student(db, user)
    if not row:
        raise no_permission("未找到你的学生档案")
    return row


def _aid(db, apply_id: int, user):
    from app.models import AidApply
    student = _student(db, user)
    row = db.get(AidApply, int(apply_id))
    if not row or row.is_deleted or row.tenant_id != _tid() or int(row.student_id) != int(student.id):
        raise not_found("困难认定申请不存在或不属于本人")
    return row, student


def _funding(db, app_id: int, user):
    from app.models import FundingApplication
    student = _student(db, user)
    row = db.get(FundingApplication, int(app_id))
    if not row or row.is_deleted or row.tenant_id != _tid() or int(row.student_id) != int(student.id):
        raise not_found("资助申请不存在或不属于本人")
    return row, student


def _aid_payload(aid, row, student, family) -> dict:
    """学生本人编辑页可查看自己录入的家庭经济字段；不复用仅供工作人员的 reveal 权限。"""
    result = aid._apply_row(row, student, family)
    result.update({
        "memberCount": family.member_count if family else None,
        "annualIncome": aid.decrypt_field(family.income_encrypted) if family else None,
        "debt": aid.decrypt_field(family.debt_encrypted) if family else None,
        "familyMembers": json.loads(family.family_members_json or "[]") if family else [],
        "specialTags": json.loads(family.special_flags_json or "[]") if family else [],
    })
    return result


def _funding_payload(funding, row, user, student) -> dict:
    result = funding._app_row(row, user, student)
    result["statement"] = row.statement or ""
    return result


@router.get("/mobile/affairs/aid/{apply_id}/editable", summary="本人读取退回困难认定申请")
def aid_editable(apply_id: int = Path(...), user=Depends(get_current_user)):
    from app.services import affairs_aid_service as aid
    with session() as db:
        row, student = _aid(db, apply_id, user)
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "只有被退回的困难认定申请可以修改")
        family = aid._family_of(db, row.id)
        result = _aid_payload(aid, row, student, family)
        result["allowedActions"] = ["EDIT_RETURNED", "RESUBMIT"]
        return success(result)


@router.put("/mobile/affairs/aid/{apply_id}/returned", summary="本人修改退回困难认定申请")
def aid_update_returned(
    apply_id: int = Path(...), body: dict = Body(...), user=Depends(get_current_user),
):
    from app.services import affairs_aid_service as aid
    with session() as db:
        row, student = _aid(db, apply_id, user)
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "只有被退回的困难认定申请可以修改")
        atomic_claim_version(db, row, body.get("version"))
        level = str(body.get("applyLevel") or row.apply_level or "")
        statement = str(body.get("statement") if body.get("statement") is not None else row.statement or "").strip()
        if level not in aid.LEVELS:
            raise AppException("VALIDATION_ERROR", "申请等级非法")
        if not 10 <= len(statement) <= 500:
            raise AppException("VALIDATION_ERROR", "困难情况说明需10-500字")
        row.apply_level, row.statement = level, statement
        family = aid._family_of(db, row.id)
        if family:
            if "memberCount" in body:
                family.member_count = body.get("memberCount")
            if "annualIncome" in body:
                family.income_encrypted = aid.encrypt_field(body.get("annualIncome"))
            if "debt" in body:
                family.debt_encrypted = aid.encrypt_field(body.get("debt"))
            if "familyMembers" in body:
                family.family_members_json = json.dumps(body.get("familyMembers") or [], ensure_ascii=False)
            if "specialTags" in body:
                family.special_flags_json = json.dumps(body.get("specialTags") or [], ensure_ascii=False)
            family.version = int(family.version or 0) + 1
        row.version = int(row.version or 0) + 1
        aid._audit(db, row.id, "STUDENT_EDIT_RETURNED", f"level={level}")
        db.commit()
        db.refresh(row)
        result = _aid_payload(aid, row, student, family)
        result["allowedActions"] = ["RESUBMIT"]
        return success(result, message="修改已保存")


@router.post("/mobile/affairs/aid/{apply_id}/resubmit", summary="本人重新提交困难认定")
def aid_resubmit(
    apply_id: int = Path(...), body: dict = Body(...), user=Depends(get_current_user),
):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import affairs_aid_service as aid
    with session() as db:
        row, student = _aid(db, apply_id, user)
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "只有被退回的申请可以重新提交")
        atomic_claim_version(db, row, body.get("version"))
        first = aid.AID_NODES[0]
        assignee = aid._assignee_for(db, first, row.student_id)
        workflow = db.get(WorkflowInstance, int(row.workflow_instance_id)) if row.workflow_instance_id else None
        if not workflow:
            workflow = aid._open_wf(db, row.id, row.student_id, f"{student.real_name} 困难认定", first, assignee)
            row.workflow_instance_id = workflow.id
        else:
            workflow.status, workflow.current_node = "RUNNING", first
            db.add(WorkflowTask(
                tenant_id=_tid(), instance_id=workflow.id, node_code=first,
                assignee_id=assignee, status="PENDING",
            ))
        row.status, row.return_reason, row.version = first, None, int(row.version or 0) + 1
        aid._todo_upsert(db, row.id, assignee, row.student_id, f"困难认定重新提交待评议：{student.real_name}")
        aid._audit(db, row.id, "STUDENT_RESUBMIT")
        db.commit()
        aid._drain_message_outbox()
        db.refresh(row)
        return success(aid._apply_row(row, student, aid._family_of(db, row.id)), message="已重新提交")


@router.get("/mobile/affairs/funding/{app_id}/editable", summary="本人读取退回资助申请")
def funding_editable(app_id: int = Path(...), user=Depends(get_current_user)):
    from app.services import affairs_funding_service as funding
    with session() as db:
        row, student = _funding(db, app_id, user)
        if row.status != "RETURNED":
            raise AppException("DATA_CONFLICT", "只有被退回的资助申请可以修改")
        result = _funding_payload(funding, row, user, student)
        result["allowedActions"] = ["EDIT_RETURNED", "RESUBMIT"]
        return success(result)


@router.put("/mobile/affairs/funding/{app_id}/returned", summary="本人修改退回资助申请")
def funding_update_returned(
    app_id: int = Path(...), body: dict = Body(...), user=Depends(get_current_user),
):
    from app.services import affairs_funding_service as funding
    with session() as db:
        row, student = _funding(db, app_id, user)
        if row.status != "RETURNED":
            raise AppException("DATA_CONFLICT", "只有被退回的资助申请可以修改")
        atomic_claim_version(db, row, body.get("version"))
        if "statement" in body:
            row.statement = str(body.get("statement") or "").strip()
        if "amount" in body:
            row.amount = body.get("amount")
        row.version = int(row.version or 0) + 1
        funding._audit(db, row.id, "STUDENT_EDIT_RETURNED")
        db.commit()
        db.refresh(row)
        result = _funding_payload(funding, row, user, student)
        result["allowedActions"] = ["RESUBMIT"]
        return success(result, message="修改已保存")


@router.post("/mobile/affairs/funding/{app_id}/resubmit", summary="本人重新提交资助申请")
def funding_resubmit(
    app_id: int = Path(...), body: dict = Body(...), user=Depends(get_current_user),
):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import affairs_funding_service as funding
    with session() as db:
        row, student = _funding(db, app_id, user)
        if row.status != "RETURNED":
            raise AppException("DATA_CONFLICT", "只有被退回的资助申请可以重新提交")
        atomic_claim_version(db, row, body.get("version"))
        snapshot = (
            funding._check_grant(db, row.student_id)
            if row.project_type == "GRANT"
            else funding._check_scholarship(db, row.student_id)
        )
        if not snapshot["ok"]:
            raise AppException("DATA_CONFLICT", funding._reject_reason(snapshot))
        first = funding.FUND_NODES[0]
        assignee = funding._assignee_for(db, first, row.student_id)
        workflow = db.get(WorkflowInstance, int(row.workflow_instance_id)) if row.workflow_instance_id else None
        if not workflow:
            workflow = funding._open_wf(
                db, row.id, row.project_type, row.student_id,
                f"{student.real_name} {row.project_type}", first, assignee,
            )
            row.workflow_instance_id = workflow.id
        else:
            workflow.status, workflow.current_node = "RUNNING", first
            db.add(WorkflowTask(
                tenant_id=_tid(), instance_id=workflow.id, node_code=first,
                assignee_id=assignee, status="PENDING",
            ))
        row.status, row.return_reason = first, None
        row.check_snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        row.version = int(row.version or 0) + 1
        funding._todo_upsert(db, row.id, assignee, row.student_id, f"资助申请重新提交待审：{student.real_name}")
        funding._audit(db, row.id, "STUDENT_RESUBMIT")
        db.commit()
        funding._drain_message_outbox()
        db.refresh(row)
        return success(funding._app_row(row, user, student), message="已重新提交")
