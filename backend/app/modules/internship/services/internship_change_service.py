"""岗位实习 · 实习变更申请（换岗/换单位/自主实习）。

对标工学云「中途变更实习单位」：学生发起 → 指导教师审核 → 落岗/更新冗余字段。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipChangeRequest, InternshipRecord, StudentProfile
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
        "createdAt": _iso(c.created_at) or "",
    }


def list_changes(page, page_size, status=None, keyword=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import batch_record_ids
    with session() as db:
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
            InternshipChangeRequest.internship_id.in_(record_ids),
        )
        if status:
            q = q.where(InternshipChangeRequest.status == status)
        rows = db.scalars(q.order_by(InternshipChangeRequest.id.desc())).all()
        scope, in_scope = _scope(user)
        items = []
        for c in rows:
            rec = db.get(InternshipRecord, c.internship_id)
            stu = db.get(StudentProfile, c.student_id)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(c, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


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


def _exc_reason(exc: BaseException) -> str:
    if isinstance(exc, AppException):
        return (exc.message or "")[:500]
    return (str(exc) or type(exc).__name__)[:500]


def _rollback_approved_change(cid, user=None, reason: str = "") -> None:
    """落岗/副作用失败补偿：变更申请回到待审，避免「已通过但未落实」。"""
    with session() as db:
        c = db.get(InternshipChangeRequest, _as_id(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            return
        if c.status != "APPROVED":
            return
        c.status = "PENDING"
        c.review_comment = None
        c.reviewed_by_name = None
        c.reviewed_at = None
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "APPROVE_ROLLBACK", {"reason": reason or "落岗失败"})
        db.commit()


def review_change(cid, action: str, comment: str = "", user=None, *, expected_version=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    ver = extract_expected_version({"expectedVersion": expected_version})
    with session() as db:
        c = db.get(InternshipChangeRequest, _as_id(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("变更申请不存在")
        if c.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可处理")
        rec = db.get(InternshipRecord, c.internship_id)
        stu = db.get(StudentProfile, c.student_id)
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("不在数据范围内")
        ctype = c.change_type
        teid = c.target_enterprise_id
        tpid = c.target_position_id
        ten = c.target_enterprise_name
        tpn = c.target_position_name
        reason = c.reason
        # 过审前校验：避免先标 APPROVED 再因缺目标岗失败
        if action == "APPROVE" and ctype == "CHANGE_POSITION" and not tpid:
            raise AppException("DATA_CONFLICT", "换岗申请缺少目标岗位编号，不可通过")
        status = "APPROVED" if action == "APPROVE" else "REJECTED"
        review_comment = (comment or "").strip()
        new_ver = versioned_update(
            db, InternshipChangeRequest, entity_id=c.id, tenant_id=_tid(),
            expected_version=ver, expected_status="PENDING",
            values={
                "status": status,
                "review_comment": review_comment,
                "reviewed_by_name": _op_name(user),
                "reviewed_at": datetime.utcnow(),
            },
        )
        _trail(db, c.id, action, {"comment": review_comment})
        out_id = str(c.id)
        rid = str(rec.id)
        db.commit()
    if action == "APPROVE":
        try:
            if ctype == "WITHDRAW_POST":
                # 退岗：释放岗位占用（成熟产品独立类型，对应 unassign）
                stu_svc.unassign_position(rid, reason or "退岗审核通过", user=user)
            elif ctype == "CHANGE_POSITION":
                stu_svc.assign_position(rid, str(tpid), user=user)
            elif ctype in ("CHANGE_ENTERPRISE", "SELF_ARRANGED"):
                if ctype == "SELF_ARRANGED":
                    stu_svc.set_destination(rid, "SELF_ARRANGED", reason, user=user)
                with session() as db:
                    r = db.get(InternshipRecord, _as_id(rid))
                    if r:
                        if ten:
                            r.enterprise_name = ten
                        if tpn:
                            r.position_name = tpn
                        if teid:
                            r.enterprise_id = teid
                        if tpid:
                            r.position_id = tpid
                        db.commit()
        except Exception as exc:
            if ctype == "SELF_ARRANGED":
                try:
                    stu_svc.set_destination(rid, "NONE", "变更审核落岗失败回滚", user=user)
                except Exception:  # noqa: BLE001 — 尽力补偿
                    pass
            _rollback_approved_change(out_id, user=user, reason=_exc_reason(exc))
            raise
    return {"id": out_id, "status": status, "statusLabel": STATUS_LABEL.get(status), "version": new_ver}
