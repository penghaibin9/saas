"""学生本人困难认定/奖助申请的原子事务入口。

解决旧链路“业务申请先提交，确认留痕后提交”的双事务问题：确认记录、申请、
家庭经济、工作流、待办和业务审计必须同事务成功或同事务回滚。
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session
from app.student_portal.services import common_service as common


def _self_student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    _require_student(user)
    student = resolve_student(db, user)
    if not student:
        raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
    return student


def _payload_sha256(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _optional_non_negative_decimal(value, field_name: str):
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AppException("VALIDATION_ERROR", f"{field_name}格式非法") from exc
    if result < 0:
        raise AppException("VALIDATION_ERROR", f"{field_name}不能小于0")
    if result.as_tuple().exponent < -2:
        raise AppException("VALIDATION_ERROR", f"{field_name}最多保留2位小数")
    return result


def _bounded_list(value, field_name: str, limit: int) -> list:
    rows = value or []
    if not isinstance(rows, list):
        raise AppException("VALIDATION_ERROR", f"{field_name}格式非法")
    if len(rows) > limit:
        raise AppException("VALIDATION_ERROR", f"{field_name}最多填写{limit}项")
    return rows


def aid_apply(user: dict, body: dict) -> dict:
    from app.models import AidApply, AidBatch, AidFamilyEconomy
    from app.services import affairs_aid_service as aid

    body = body or {}
    batch_id = str(body.get("batchId") or "").strip()
    level = str(body.get("applyLevel") or "").strip()
    statement = str(body.get("statement") or "").strip()
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "认定批次（batchId）必填")
    if level not in aid.LEVELS:
        raise AppException("VALIDATION_ERROR", "申请等级非法")
    if not 10 <= len(statement) <= 500:
        raise AppException("VALIDATION_ERROR", "困难情况说明需 10-500 字")
    if not bool(body.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先阅读并勾选确认承诺书")

    member_count = body.get("memberCount")
    if member_count not in (None, ""):
        try:
            member_count = int(member_count)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "家庭成员数格式非法") from exc
        if member_count < 1 or member_count > 30:
            raise AppException("VALIDATION_ERROR", "家庭成员数应为1-30人")
    annual_income = _optional_non_negative_decimal(body.get("annualIncome"), "家庭年收入")
    debt = _optional_non_negative_decimal(body.get("debt"), "家庭债务")
    family_members = _bounded_list(body.get("familyMembers"), "家庭成员", 30)
    special_tags = _bounded_list(body.get("specialTags"), "特殊情况标签", 30)

    with session() as db:
        student = _self_student(db, user)
        batch = db.get(AidBatch, aid._req_int(batch_id, "批次"))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("认定批次不存在")
        if batch.status != "OPEN":
            raise AppException("DATA_CONFLICT", "批次未开放或已截止")
        duplicate = db.scalars(select(AidApply).where(
            AidApply.tenant_id == _tid(),
            AidApply.batch_id == batch.id,
            AidApply.student_id == student.id,
            AidApply.is_deleted.is_(False),
        )).first()
        if duplicate and duplicate.status not in aid._TERMINAL:
            raise AppException("DATA_CONFLICT", "你在本批次已有在途申请，不可重复提交")

        first = aid.AID_NODES[0]
        application = AidApply(
            tenant_id=_tid(), batch_id=batch.id, student_id=student.id,
            apply_level=level, statement=statement, status=first,
        )
        db.add(application)
        db.flush()
        family = AidFamilyEconomy(
            tenant_id=_tid(), apply_id=application.id, student_id=student.id,
            member_count=member_count,
            income_encrypted=aid.encrypt_field(str(annual_income) if annual_income is not None else None),
            debt_encrypted=aid.encrypt_field(str(debt) if debt is not None else None),
            family_members_json=json.dumps(family_members, ensure_ascii=False),
            special_flags_json=json.dumps(special_tags, ensure_ascii=False),
        )
        db.add(family)
        assignee = aid._assignee_for(db, first, student.id)
        workflow = aid._open_wf(
            db, application.id, student.id,
            f"{student.real_name} 困难认定", first, assignee,
        )
        application.workflow_instance_id = workflow.id
        aid._todo_upsert(
            db, application.id, assignee, student.id,
            f"困难认定待评议：{student.real_name}",
        )
        payload_hash = _payload_sha256({
            "bizType": "DIFFICULTY_COMMIT",
            "studentId": int(student.id),
            "batchId": int(batch.id),
            "applyLevel": level,
            "statement": statement,
            "memberCount": member_count,
            "annualIncome": str(annual_income) if annual_income is not None else None,
            "debt": str(debt) if debt is not None else None,
            "familyMembers": family_members,
            "specialTags": special_tags,
        })
        confirmation = common.create_sign_record_in_session(db, user, {
            "bizType": "DIFFICULTY_COMMIT",
            "bizId": str(application.id),
            "content": (
                f"困难认定本人确认 student={student.id} batch={batch.id} "
                f"payloadSha256={payload_hash}"
            ),
            "confirm": True,
        }, student)
        aid._audit(db, application.id, "APPLY", f"level={level};confirmation={confirmation['signId']}")
        db.commit()
        aid._drain_message_outbox()
        db.refresh(application)
        db.refresh(family)
        result = aid._apply_row(application, student, family)
        result["confirmation"] = confirmation
        result["payloadSha256"] = payload_hash
        return result


def funding_apply(user: dict, body: dict) -> dict:
    from app.models import FundingApplication, FundingBatch
    from app.services import affairs_funding_service as funding

    body = body or {}
    batch_id = str(body.get("batchId") or "").strip()
    statement = str(body.get("statement") or "").strip()
    amount = _optional_non_negative_decimal(body.get("amount"), "申请金额")
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "资助批次（batchId）必填")
    if not 5 <= len(statement) <= 1000:
        raise AppException("VALIDATION_ERROR", "申请理由需5-1000字")
    if not bool(body.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先阅读并勾选确认承诺书")

    with session() as db:
        student = _self_student(db, user)
        batch = db.get(FundingBatch, funding._req_int(batch_id, "批次"))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("资助批次不存在")
        if batch.status != "OPEN":
            raise AppException("DATA_CONFLICT", "批次未开放或已截止")
        duplicate = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(),
            FundingApplication.batch_id == batch.id,
            FundingApplication.student_id == student.id,
            FundingApplication.is_deleted.is_(False),
        )).first()
        if duplicate and duplicate.status not in funding._TERMINAL:
            raise AppException("DATA_CONFLICT", "你在本批次已有在途申请，不可重复提交")

        snapshot = (
            funding._check_grant(db, student.id)
            if batch.project_type == "GRANT"
            else funding._check_scholarship(db, student.id)
        )
        if not snapshot["ok"]:
            raise AppException("DATA_CONFLICT", funding._reject_reason(snapshot))
        first = funding.FUND_NODES[0]
        application = FundingApplication(
            tenant_id=_tid(), batch_id=batch.id, student_id=student.id,
            apply_source="SELF", project_type=batch.project_type,
            amount=amount, statement=statement,
            check_snapshot_json=json.dumps(snapshot, ensure_ascii=False), status=first,
        )
        db.add(application)
        db.flush()
        assignee = funding._assignee_for(db, first, student.id)
        workflow = funding._open_wf(
            db, application.id, batch.project_type, student.id,
            f"{student.real_name} {batch.project_type}", first, assignee,
        )
        application.workflow_instance_id = workflow.id
        funding._todo_upsert(
            db, application.id, assignee, student.id,
            f"资助申请待审：{student.real_name}",
        )
        payload_hash = _payload_sha256({
            "bizType": "FUNDING_COMMIT",
            "studentId": int(student.id),
            "batchId": int(batch.id),
            "projectType": batch.project_type,
            "amount": str(amount) if amount is not None else None,
            "statement": statement,
            "checkSnapshot": snapshot,
        })
        confirmation = common.create_sign_record_in_session(db, user, {
            "bizType": "FUNDING_COMMIT",
            "bizId": str(application.id),
            "content": (
                f"资助申请本人确认 student={student.id} batch={batch.id} "
                f"projectType={batch.project_type} payloadSha256={payload_hash}"
            ),
            "confirm": True,
        }, student)
        funding._audit(
            db, application.id, "APPLY",
            f"{batch.project_type};confirmation={confirmation['signId']}",
        )
        db.commit()
        funding._drain_message_outbox()
        db.refresh(application)
        result = funding._app_row(application, user, student)
        result["confirmation"] = confirmation
        result["payloadSha256"] = payload_hash
        return result


def install() -> None:
    """学生门户与小程序共用同一原子申请实现。"""
    from app.student_portal.services import affairs_service as portal
    portal.aid_apply = aid_apply
    portal.funding_apply = funding_apply
