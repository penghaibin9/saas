"""岗位实习 · 实习变更申请（换岗/换单位/自主实习）。

对标工学云「中途变更实习单位」：学生发起 → 指导教师审核 → 落岗/更新冗余字段。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAgreement, InternshipAuditTrail, InternshipChangeRequest,
                        InternshipRecord, StudentProfile)
from app.modules.internship.services import internship_student_service as stu_svc
from app.services.db_service import _as_id, _iso, _tid, session

# 对标成熟实习变更：换岗 / 换单位 / 转自主 / 退岗（结束岗位）分类型，不混为一谈
TYPE_LABEL = {
    "CHANGE_POSITION": "换岗",
    "CHANGE_ENTERPRISE": "换实习单位",
    "SELF_ARRANGED": "转自主实习",
    "WITHDRAW_POST": "退岗",
}
STATUS_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}


def _op_name(user=None) -> str:
    if user:
        return user.get("realName") or "系统"
    from app.core.context import get_current_user_ctx
    return (get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, cid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=cid, target_type="CHANGE_REQ",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _scope(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _row(c, rec, stu):
    return {
        "id": str(c.id), "internId": str(c.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "changeType": c.change_type, "changeTypeLabel": TYPE_LABEL.get(c.change_type, c.change_type),
        "reason": c.reason,
        "targetEnterpriseName": c.target_enterprise_name or "",
        "targetPositionName": c.target_position_name or "",
        "currentEnterprise": rec.enterprise_name if rec else "",
        "currentPosition": rec.position_name if rec else "",
        "status": c.status, "statusLabel": STATUS_LABEL.get(c.status, c.status),
        "version": int(c.version or 0),
        "recordVersion": int(rec.version or 0) if rec else None,
        "recordVersionSnapshot": int(c.record_version_snapshot or 0),
        "createdAt": _iso(c.created_at) or "",
    }


def list_changes(page, page_size, status=None, keyword=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped_records = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipChangeRequest, InternshipRecord, StudentProfile).join(
            InternshipRecord,
            InternshipRecord.id == InternshipChangeRequest.internship_id,
        ).join(
            StudentProfile,
            StudentProfile.id == InternshipChangeRequest.student_id,
        ).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
            InternshipChangeRequest.internship_id.in_(select(scoped_records.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipChangeRequest.status == status)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipChangeRequest.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size)
            .limit(size)
        ).all()
        return [_row(change, record, student) for change, record, student in rows], total


def get_change(cid, user=None):
    with session() as db:
        c = db.get(InternshipChangeRequest, _as_id(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("变更申请不存在")
        rec = db.get(InternshipRecord, c.internship_id)
        stu = db.get(StudentProfile, c.student_id)
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("不在数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "CHANGE_REQ",
            InternshipAuditTrail.target_id == c.id).order_by(InternshipAuditTrail.id)).all()
        return {
            **_row(c, rec, stu),
            "reviewComment": c.review_comment or "",
            "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                            "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                           for t in trail],
        }


def list_my_changes(rec, stu):
    with session() as db:
        rows = db.scalars(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(), InternshipChangeRequest.internship_id == rec.id,
            InternshipChangeRequest.student_id == stu.id, InternshipChangeRequest.is_deleted.is_(False)
        ).order_by(InternshipChangeRequest.id.desc())).all()
        return [_row(c, rec, stu) for c in rows]


def student_apply(rec, stu, body) -> dict:
    b = body or {}
    ctype = (b.get("changeType") or "").upper()
    if ctype not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "changeType 无效")
    reason = (b.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")
    # 换岗必须带岗位库 ID，避免审核「假通过」不落岗
    if ctype == "CHANGE_POSITION" and not b.get("targetPositionId"):
        raise AppException("VALIDATION_ERROR", "换岗须填写目标岗位编号（targetPositionId）")
    with session() as db:
        pending = db.scalars(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(), InternshipChangeRequest.internship_id == rec.id,
            InternshipChangeRequest.status == "PENDING", InternshipChangeRequest.is_deleted.is_(False))).first()
        if pending:
            raise AppException("DATA_CONFLICT", "已有待审核的变更申请，请等待处理或撤回")
        c = InternshipChangeRequest(
            tenant_id=_tid(), internship_id=rec.id, student_id=stu.id, change_type=ctype, reason=reason,
            target_enterprise_id=int(b["targetEnterpriseId"]) if b.get("targetEnterpriseId") else None,
            target_position_id=int(b["targetPositionId"]) if b.get("targetPositionId") else None,
            target_enterprise_name=(b.get("targetEnterpriseName") or "").strip() or None,
            target_position_name=(b.get("targetPositionName") or "").strip() or None,
            record_version_snapshot=int(rec.version or 0),
            status="PENDING")
        db.add(c)
        db.flush()
        _trail(db, c.id, "APPLY", {"changeType": ctype})
        db.commit()
        return _row(c, rec, stu)


def withdraw_change(cid, rec, stu) -> dict:
    with session() as db:
        c = db.get(InternshipChangeRequest, _as_id(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("变更申请不存在")
        if c.internship_id != rec.id or c.student_id != stu.id:
            raise no_permission("只能撤回本人的变更申请")
        if c.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        c.status = "WITHDRAWN"
        _trail(db, c.id, "WITHDRAW", {})
        db.commit()
        return {"id": str(c.id), "status": "WITHDRAWN"}


def _void_prior_compliance(db, record: InternshipRecord, change: InternshipChangeRequest,
                           user=None) -> None:
    """A destination change invalidates prior consent and active agreements in the same transaction."""
    from app.modules.internship.services.internship_consent_service import supersede_for_major_change

    supersede_for_major_change(db, record.id)
    agreements = db.scalars(select(InternshipAgreement).where(
        InternshipAgreement.tenant_id == _tid(),
        InternshipAgreement.internship_id == record.id,
        InternshipAgreement.status.in_((
            "DRAFT", "PENDING_STUDENT", "PENDING_ENTERPRISE", "PENDING_SCHOOL", "EFFECTIVE")),
        InternshipAgreement.is_deleted.is_(False),
    ).with_for_update()).all()
    for agreement in agreements:
        before = agreement.status
        agreement.status = "VOIDED"
        agreement.reject_reason = f"实习变更单 {change.id} 已通过，原协议失效并须重新办理"
        agreement.version = int(agreement.version or 0) + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=agreement.id, target_type="AGREEMENT",
            action="VOID_BY_CHANGE", operator_name=_op_name(user),
            detail_json={"changeId": str(change.id), "beforeStatus": before},
            occurred_at=datetime.utcnow()))


def review_change(cid, action: str, comment: str = "", user=None, *, expected_version=None,
                  record_expected_version=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )

    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    review_comment = str(comment or "").strip()
    if action == "REJECT" and len(review_comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    change_version = extract_expected_version({"expectedVersion": expected_version})

    with session() as db:
        change = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == _as_id(cid),
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False)).with_for_update())
        if not change:
            raise not_found("变更申请不存在")
        if change.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可处理")
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == change.internship_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        if not record:
            raise not_found("实习主记录不存在")
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == change.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False)))
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, record, student):
            raise no_permission("不在数据范围内")

        snapshot = int(change.record_version_snapshot or 0)
        if action == "APPROVE":
            expected_record = snapshot if record_expected_version is None else extract_expected_version(
                {"expectedVersion": record_expected_version})
            if expected_record != snapshot:
                raise AppException("DATA_CONFLICT", "页面实习记录版本与申请快照不一致，请刷新")
            if int(record.version or 0) != snapshot:
                raise AppException(
                    "DATA_CONFLICT",
                    "学生实习主记录在申请后已变化，请退回申请并由学生基于最新数据重新提交",
                )
        before = {
            "recordVersion": int(record.version or 0),
            "positionId": str(record.position_id or ""),
            "enterpriseId": str(record.enterprise_id or ""),
            "destinationType": record.destination_type,
            "status": record.status,
        }
        if action == "APPROVE":
            change_type = change.change_type
            if change_type in ("CHANGE_POSITION", "CHANGE_ENTERPRISE"):
                if not change.target_position_id:
                    label = "换单位" if change_type == "CHANGE_ENTERPRISE" else "换岗"
                    raise AppException("DATA_CONFLICT", f"{label}申请缺少目标岗位编号，不可通过")
                stu_svc.assign_position_in_tx(
                    db, record, change.target_position_id, snapshot, user=user)
            elif change_type == "WITHDRAW_POST":
                next_status = "READY" if record.eligibility_status == "QUALIFIED" else "PREPARING"
                stu_svc.unassign_position_in_tx(
                    db, record, snapshot, change.reason or "退岗审核通过",
                    user=user, next_status=next_status)
            elif change_type == "SELF_ARRANGED":
                enterprise_name = str(change.target_enterprise_name or "").strip()
                position_name = str(change.target_position_name or "").strip()
                if len(enterprise_name) < 2 or len(position_name) < 2:
                    raise AppException("DATA_CONFLICT", "转自主实习必须填写完整的目标单位和岗位")
                if record.position_id:
                    stu_svc.unassign_position_in_tx(
                        db, record, snapshot, change.reason or "转自主实习",
                        user=user)
                else:
                    record.version = snapshot + 1
                record.enterprise_id = None
                record.position_id = None
                record.mentor_contact_id = None
                record.enterprise_name = enterprise_name
                record.position_name = position_name
                record.enterprise_mentor_name = None
                record.destination_type = "SELF_ARRANGED"
                stu_svc._trail(db, record.id, "SET_SELF_ARRANGED_BY_CHANGE", {
                    "changeId": str(change.id), "recordVersion": int(record.version or 0),
                })
            else:
                raise AppException("VALIDATION_ERROR", "未知实习变更类型")
            _void_prior_compliance(db, record, change, user=user)

        status = "APPROVED" if action == "APPROVE" else "REJECTED"
        new_version = versioned_update(
            db, InternshipChangeRequest, entity_id=change.id, tenant_id=_tid(),
            expected_version=change_version, expected_status="PENDING",
            values={
                "status": status,
                "review_comment": review_comment or None,
                "reviewed_by_name": _op_name(user),
                "reviewed_at": datetime.utcnow(),
            },
        )
        _trail(db, change.id, action, {
            "comment": review_comment,
            "recordBefore": before,
            "recordAfter": {
                "recordVersion": int(record.version or 0),
                "positionId": str(record.position_id or ""),
                "enterpriseId": str(record.enterprise_id or ""),
                "destinationType": record.destination_type,
                "status": record.status,
            } if action == "APPROVE" else before,
            "atomic": True,
        }, operator=_op_name(user))
        db.commit()
        return {
            "id": str(change.id), "status": status,
            "statusLabel": STATUS_LABEL.get(status), "version": new_version,
            "recordVersion": int(record.version or 0),
        }
