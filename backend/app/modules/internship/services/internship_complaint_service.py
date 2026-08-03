"""企业投诉受理（07 整改方案 §5.3）。

受理业务（非普通风险待办）：核实后可转风险单(risk_id)，也可仅咨询/撤回/判定不成立。
状态机 RECEIVED→ACCEPTED→INVESTIGATING→RESOLVED/REJECTED→CLOSED；旁路 WITHDRAWN。
投诉人联系方式敏感(密文)，需 internship.complaint.sensitive 才可见明文（领导 *.view 不含该码=脱敏）。
转风险后保留双向链接(risk_id)，原投诉不可被风险单覆盖。审计 InternshipAuditTrail(target_type=COMPLAINT)。
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.field_crypto import decrypt_sensitive, encrypt_sensitive, hash_sensitive
from app.models import (InternshipAuditTrail, InternshipComplaint, InternshipRecord, RiskRecord,
                        StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"RECEIVED": "已登记", "ACCEPTED": "已受理", "INVESTIGATING": "调查中",
                "RESOLVED": "已办结", "REJECTED": "不成立", "WITHDRAWN": "已撤回", "CLOSED": "已关闭"}
_logger = logging.getLogger("app.internship.complaint")

_TRANSITIONS = {
    "ACCEPT": (("RECEIVED",), "ACCEPTED"),
    "INVESTIGATE": (("ACCEPTED",), "INVESTIGATING"),
    "RESOLVE": (("INVESTIGATING",), "RESOLVED"),
    "REJECT": (("RECEIVED", "ACCEPTED", "INVESTIGATING"), "REJECTED"),
    "WITHDRAW": (("RECEIVED", "ACCEPTED"), "WITHDRAWN"),
    "CLOSE": (("RESOLVED", "REJECTED"), "CLOSED"),
}


def _op_name(user=None):
    return (user or get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, cid, action, detail=None, user=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=cid, target_type="COMPLAINT", action=action,
        operator_name=_op_name(user), detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _get(db, cid):
    c = db.get(InternshipComplaint, _as_id(cid))
    if not c or c.is_deleted or c.tenant_id != _tid():
        raise not_found("投诉不存在或不在当前数据范围内")
    return c


def _mask(value: str) -> str:
    v = (value or "").strip()
    if len(v) <= 4:
        return "***" if v else ""
    return v[:3] + "****" + v[-2:]


def _row(c, user=None, student_name: str = ""):
    from app.core.permissions import has_permission

    can_sensitive = has_permission(user or {}, "internship.complaint.sensitive")
    contact = ""
    contact_corrupted = False
    if c.complainant_contact_encrypted:
        try:
            contact = decrypt_sensitive(
                c.complainant_contact_encrypted,
                "internship_complaint_contact",
                allow_legacy_plaintext=True,
            ) or ""
        except Exception:  # noqa: BLE001 - 列表展示必须 fail-closed，解密错误已记录
            contact_corrupted = True
            _logger.exception("complaint_contact_decrypt_failed complaint_id=%s", c.id)
    confidential = str(c.confidential_level or "NORMAL").upper() != "NORMAL"
    hide_business_detail = confidential and not can_sensitive
    return {
        "id": str(c.id), "complaintNo": c.complaint_no or "", "source": c.source,
        "targetType": c.target_type or "",
        "enterpriseId": str(c.enterprise_id) if c.enterprise_id else "",
        "studentId": str(c.student_id) if c.student_id else "",
        "studentName": student_name or ("企业投诉" if not c.student_id else ""),
        "batchId": str(c.batch_id) if c.batch_id else "",
        "category": c.category or "", "severity": c.severity,
        "content": "" if hide_business_detail else (c.content or ""),
        "evidenceFileId": "" if hide_business_detail else (c.evidence_file_id or ""),
        "contentMasked": hide_business_detail,
        "evidenceMasked": hide_business_detail,
        "complainantContact": (
            "***" if contact_corrupted else (contact if can_sensitive else _mask(contact))
        ),
        "complainantContactMasked": (not can_sensitive) or contact_corrupted,
        "complainantContactCorrupted": contact_corrupted,
        "confidentialLevel": c.confidential_level,
        "status": c.status, "statusLabel": STATUS_LABEL.get(c.status, c.status),
        "acceptedByName": c.accepted_by_name or "", "ownerName": c.owner_name or "",
        "acceptDeadline": c.accept_deadline or "", "resolveDeadline": c.resolve_deadline or "",
        "conclusion": "" if hide_business_detail else (c.conclusion or ""),
        "followupResult": "" if hide_business_detail else (c.followup_result or ""),
        "riskId": str(c.risk_id) if c.risk_id else "", "createdAt": _iso(c.created_at) or "",
    }


def _assert_complaint_writable(db, c, user, msg: str = "该投诉不在你的可写范围内"):
    """有学生：按学生范围；无学生企业投诉：仅校级 ADMIN_TENANT（教育部「学校是主体」口径）。"""
    from app.modules.internship.services.internship_service import assert_admin_tenant, assert_student_in_scope
    if not c.student_id:
        assert_admin_tenant(user, msg)
        return
    assert_student_in_scope(db, c.student_id, user, msg)


def _complaint_in_scope(db, c, user) -> bool:
    """投诉范围使用明确 internship_id/batch_id；禁止按学生最新实习记录猜测。"""
    from app.modules.internship.services.internship_service import (
        _current_scope, _rec_in_scope, assert_student_in_scope)

    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return True
    if not c.student_id:
        return False
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == c.student_id,
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if not student:
        return False
    record = None
    if c.internship_id:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == c.internship_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.student_id == c.student_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        if record is None:
            return False
    elif c.batch_id:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.student_id == c.student_id,
            InternshipRecord.batch_id == c.batch_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        if record is None:
            return False
    if record is not None:
        return _rec_in_scope(scope, db, record, student)
    try:
        assert_student_in_scope(db, c.student_id, user)
        return True
    except Exception:  # noqa: BLE001 — no_permission → 不在范围
        return False


def list_complaints(page, page_size, status=None, enterprise_id=None, severity=None,
                    batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import (
        batch_record_ids, parse_required_batch_id,
    )
    with session() as db:
        bid = parse_required_batch_id(batch_id)
        _, record_ids = batch_record_ids(db, batch_id)
        student_ids: list[int] = []
        if record_ids:
            student_ids = list(db.scalars(
                select(InternshipRecord.student_id).where(
                    InternshipRecord.id.in_(record_ids),
                    InternshipRecord.is_deleted.is_(False),
                )).all())
        # 明确挂本批，或未挂批次但学生属于本批实习记录（兼容历史未写 batch_id）
        batch_scope = [InternshipComplaint.batch_id == bid]
        if student_ids:
            batch_scope.append(and_(
                InternshipComplaint.batch_id.is_(None),
                InternshipComplaint.student_id.in_(student_ids),
            ))
        q = select(InternshipComplaint).where(
            InternshipComplaint.tenant_id == _tid(),
            InternshipComplaint.is_deleted.is_(False),
            or_(*batch_scope),
        )
        if status:
            q = q.where(InternshipComplaint.status == status)
        if enterprise_id:
            q = q.where(InternshipComplaint.enterprise_id == int(enterprise_id))
        if severity:
            q = q.where(InternshipComplaint.severity == severity)
        rows = db.scalars(q.order_by(InternshipComplaint.id.desc())).all()
        items = []
        for c in rows:
            if not _complaint_in_scope(db, c, user):
                continue
            stu_name = ""
            if c.student_id:
                stu = db.get(StudentProfile, c.student_id)
                stu_name = (stu.real_name if stu else "") or ""
            items.append(_row(c, user, stu_name))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_complaint(cid, user=None):
    with session() as db:
        c = _get(db, cid)
        if not _complaint_in_scope(db, c, user):
            raise no_permission("该投诉不在你的数据范围内")
        stu_name = ""
        if c.student_id:
            stu = db.get(StudentProfile, c.student_id)
            stu_name = (stu.real_name if stu else "") or ""
        item = _row(c, user, stu_name)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "COMPLAINT",
            InternshipAuditTrail.target_id == c.id).order_by(InternshipAuditTrail.id)).all()
        item["auditTrail"] = [{"action": t.action, "operator": t.operator_name or "",
                               "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at) or ""}
                              for t in trail]
        return item


def create_complaint(body, user=None):
    body = body or {}
    content = (body.get("content") or "").strip()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "投诉内容不少于 5 个字符")
    source = (body.get("source") or "STUDENT").upper()
    severity = (body.get("severity") or "MEDIUM").upper()
    if severity not in ("LOW", "MEDIUM", "HIGH"):
        raise AppException("VALIDATION_ERROR", "严重级别不合法")
    contact_plain = str(body.get("complainantContact") or "").strip()
    confidential_level = str(body.get("confidentialLevel") or "NORMAL").strip().upper()
    if confidential_level not in ("NORMAL", "CONFIDENTIAL", "RESTRICTED"):
        raise AppException("VALIDATION_ERROR", "保密级别不合法")
    with session() as db:
        internship_id = int(body["internshipId"]) if body.get("internshipId") else None
        student_id = int(body["studentId"]) if body.get("studentId") else None
        batch_id = int(body["batchId"]) if body.get("batchId") else None
        rec = None
        if internship_id:
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.id == internship_id,
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.is_deleted.is_(False)))
            if not rec:
                raise not_found("关联实习记录不存在或不在当前租户")
            if student_id and rec.student_id != student_id:
                raise AppException("DATA_CONFLICT", "投诉学生与实习记录不一致")
            if batch_id and rec.batch_id != batch_id:
                raise AppException("DATA_CONFLICT", "投诉批次与实习记录不一致")
            student_id, batch_id = rec.student_id, rec.batch_id
        elif student_id:
            if not batch_id:
                raise AppException("VALIDATION_ERROR", "关联学生投诉必须明确 internshipId 或 batchId")
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == student_id,
                InternshipRecord.batch_id == batch_id,
                InternshipRecord.is_deleted.is_(False)))
            if not rec:
                raise not_found("该学生在所选批次下无实习记录")
            internship_id = rec.id
        if student_id:
            from app.modules.internship.services.internship_service import assert_student_in_scope
            assert_student_in_scope(db, student_id, user, "该学生不在你的数据范围内，无法登记投诉")
        else:
            from app.modules.internship.services.internship_service import assert_admin_tenant
            assert_admin_tenant(user, "登记无关联学生的企业投诉")
        c = InternshipComplaint(
            tenant_id=_tid(), source=source,
            target_type=(body.get("targetType") or "").upper() or None,
            enterprise_id=int(body["enterpriseId"]) if body.get("enterpriseId") else None,
            position_id=int(body["positionId"]) if body.get("positionId") else None,
            student_id=student_id, internship_id=internship_id, batch_id=batch_id,
            category=(body.get("category") or "").strip() or None,
            severity=severity, content=content,
            evidence_file_id=(body.get("evidenceFileId") or "").strip() or None,
            complainant_contact_encrypted=encrypt_sensitive(
                contact_plain, "internship_complaint_contact") if contact_plain else None,
            complainant_contact_hash=hash_sensitive(
                contact_plain, "internship_complaint_contact") if contact_plain else None,
            confidential_level=confidential_level,
            status="RECEIVED", created_by=None)
        db.add(c)
        db.flush()
        c.complaint_no = f"CPL-{datetime.utcnow():%Y%m}-{c.id:05d}"
        _trail(db, c.id, "CREATE", {
            "source": source, "severity": severity,
            "internshipId": str(internship_id or ""), "contactEncrypted": bool(contact_plain),
        }, user)
        db.commit()
        return _row(c, user)


def transition(cid, action, body=None, user=None):
    action = (action or "").upper()
    if action not in _TRANSITIONS:
        raise AppException("VALIDATION_ERROR", "action 不合法")
    allowed_from, to = _TRANSITIONS[action]
    body = body or {}
    with session() as db:
        c = _get(db, cid)
        _assert_complaint_writable(db, c, user, "该投诉不在你的可写范围内")
        if c.status not in allowed_from:
            raise AppException("DATA_CONFLICT", f"当前状态 {c.status} 不可执行 {action}")
        if action == "ACCEPT":
            c.accepted_by_name = _op_name(user)
            c.owner_name = (body.get("ownerName") or "").strip() or _op_name(user)
            c.accept_deadline = (body.get("acceptDeadline") or "").strip() or None
            c.resolve_deadline = (body.get("resolveDeadline") or "").strip() or None
        if action in ("RESOLVE", "REJECT"):
            conclusion = (body.get("conclusion") or "").strip()
            if len(conclusion) < 5:
                raise AppException("VALIDATION_ERROR", "结论/处理意见不少于 5 个字符")
            c.conclusion = conclusion
        c.status = to
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, action, {"conclusion": body.get("conclusion")} if action in ("RESOLVE", "REJECT") else {}, user)
        db.commit()
        return _row(c, user)


def to_risk(cid, user=None):
    with session() as db:
        c = db.scalar(select(InternshipComplaint).where(
            InternshipComplaint.id == _as_id(cid),
            InternshipComplaint.tenant_id == _tid(),
            InternshipComplaint.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("投诉不存在或不在当前数据范围内")
        _assert_complaint_writable(db, c, user, "该投诉不在你的可写范围内")
        if c.risk_id:
            raise AppException("DATA_CONFLICT", "该投诉已转风险单")
        if c.status in ("WITHDRAWN", "CLOSED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "已撤回/关闭/不成立的投诉不可转风险")
        if not c.student_id:
            raise AppException("DATA_CONFLICT", "仅关联学生的投诉可转风险单")
        rec = None
        if c.internship_id:
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.id == c.internship_id,
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == c.student_id,
                InternshipRecord.is_deleted.is_(False)).with_for_update())
        elif c.batch_id:
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == c.student_id,
                InternshipRecord.batch_id == c.batch_id,
                InternshipRecord.is_deleted.is_(False)).with_for_update())
            if rec:
                c.internship_id = rec.id
        if not rec:
            raise not_found("投诉未精确关联实习记录，禁止按学生最新记录猜测转风险")
        risk_code = f"INT-CPL-{c.id}"
        existing = db.scalar(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(),
            RiskRecord.source_type == "COMPLAINT",
            RiskRecord.source_id == c.id,
            RiskRecord.risk_code == risk_code,
            RiskRecord.is_deleted.is_(False)).with_for_update())
        if existing:
            c.risk_id = existing.id
            db.commit()
            return _row(c, user)
        risk = RiskRecord(
            tenant_id=_tid(), internship_id=rec.id, risk_code=risk_code,
            risk_title=f"企业投诉转风险：{c.category or '企业投诉'}",
            risk_level=c.severity or "MEDIUM", source_module="complaint",
            source_type="COMPLAINT", source_id=c.id,
            source_version=int(c.version or 0),
            owner_name=c.owner_name or _op_name(user), status="PENDING_HANDLE")
        db.add(risk)
        db.flush()
        c.risk_id = risk.id
        if c.status in ("RECEIVED", "ACCEPTED"):
            c.status = "INVESTIGATING"
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "TO_RISK", {
            "riskId": str(risk.id), "internshipId": str(rec.id),
            "sourceVersion": int(risk.source_version or 0),
        }, user)
        db.commit()
        return _row(c, user)


def followup(cid, result, user=None):
    result = (result or "").strip()
    if len(result) < 2:
        raise AppException("VALIDATION_ERROR", "回访结果不少于 2 个字符")
    with session() as db:
        c = _get(db, cid)
        _assert_complaint_writable(db, c, user, "该投诉不在你的可写范围内")
        if c.status not in ("RESOLVED", "CLOSED"):
            raise AppException("DATA_CONFLICT", "仅办结/关闭的投诉可回访")
        c.followup_result = result
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "FOLLOWUP", {}, user)
        db.commit()
        return _row(c, user)
