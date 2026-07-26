from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAuditTrail, InternshipEmergencyPlan, InternshipIncident, RiskRecord,
)
from app.services.db_service import _as_id, _tid, session


def _op(user):
    return (user or {}).get("realName") or "系统"


def _uid(user):
    return str((user or {}).get("userId") or "")


def _audit(db, target_id, target_type, action, user=None, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=target_id, target_type=target_type,
        action=action, operator_name=_op(user), detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def create_plan(body, user=None):
    b = body or {}
    name = str(b.get("planName") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "预案名称必填")
    if not b.get("companyId") and not b.get("batchId"):
        raise AppException("VALIDATION_ERROR", "应急预案必须关联企业或实习批次")
    if not str(b.get("responsiblePerson") or "").strip():
        raise AppException("VALIDATION_ERROR", "应急责任人必填")
    if not str(b.get("emergencyContact") or "").strip():
        raise AppException("VALIDATION_ERROR", "应急联系电话必填")
    if not str(b.get("responseSteps") or "").strip():
        raise AppException("VALIDATION_ERROR", "应急处置步骤必填")
    with session() as db:
        x = InternshipEmergencyPlan(
            tenant_id=_tid(),
            company_id=_as_id(b["companyId"]) if b.get("companyId") else None,
            batch_id=_as_id(b["batchId"]) if b.get("batchId") else None,
            plan_name=name,
            responsible_person=str(b.get("responsiblePerson") or "").strip(),
            emergency_contact=str(b.get("emergencyContact") or "").strip(),
            backup_contact=str(b.get("backupContact") or "").strip() or None,
            hospital_or_support=str(b.get("hospitalOrSupport") or "").strip() or None,
            response_steps=str(b.get("responseSteps") or "").strip(),
            valid_from=b.get("validFrom"), valid_until=b.get("validUntil"),
            file_ids=b.get("fileIds") or [], status="DRAFT")
        db.add(x)
        db.flush()
        _audit(db, x.id, "EMERGENCY_PLAN", "CREATE", user, {
            "companyId": str(x.company_id or ""), "batchId": str(x.batch_id or ""),
            "actorUserId": _uid(user), "version": int(x.version or 0),
        })
        db.commit()
        return {"id": str(x.id), "status": x.status, "version": int(x.version or 0)}


def review_plan(pid, action, user=None, expected_version=None, comment=""):
    action = str(action or "").upper()
    with session() as db:
        x = db.scalar(select(InternshipEmergencyPlan).where(
            InternshipEmergencyPlan.id == _as_id(pid),
            InternshipEmergencyPlan.tenant_id == _tid(),
            InternshipEmergencyPlan.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("应急预案不存在")
        if expected_version is not None and int(expected_version) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "应急预案版本已变化，请刷新后重试")
        before = x.status
        if action == "SUBMIT" and x.status == "DRAFT":
            if not x.file_ids:
                raise AppException("VALIDATION_ERROR", "提交审核前至少上传一份应急预案附件")
            x.status = "PENDING_REVIEW"
        elif action == "APPROVE" and x.status == "PENDING_REVIEW":
            x.status = "APPROVED"
            x.reviewed_by_name = _op(user)
            x.reviewed_at = datetime.utcnow()
        elif action == "REJECT" and x.status == "PENDING_REVIEW":
            if len(str(comment or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            x.status = "DRAFT"
        else:
            raise AppException("DATA_CONFLICT", "预案状态不允许该操作")
        x.version = int(x.version or 0) + 1
        _audit(db, x.id, "EMERGENCY_PLAN", f"{action}", user, {
            "beforeStatus": before, "afterStatus": x.status,
            "comment": str(comment or "").strip(), "actorUserId": _uid(user),
            "version": int(x.version or 0),
        })
        db.commit()
        return {"id": str(x.id), "status": x.status, "version": int(x.version or 0)}


def report_incident(body, user=None):
    b = dict(body or {})
    key = str(b.get("idempotencyKey") or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "idempotencyKey 必填")
    if not str(b.get("summary") or "").strip():
        raise AppException("VALIDATION_ERROR", "事故情况摘要必填")
    with session() as db:
        if b.get("internshipId"):
            from app.modules.internship.services.internship_scope import assert_internship_record_scope
            rec = assert_internship_record_scope(db, b["internshipId"], user, "事故上报")
            b["studentId"], b["batchId"], b["companyId"] = (
                rec.student_id, rec.batch_id, rec.enterprise_id)
        existing = db.scalars(select(InternshipIncident).where(
            InternshipIncident.tenant_id == _tid(),
            InternshipIncident.idempotency_key == key,
            InternshipIncident.is_deleted.is_(False))).first()
        if existing:
            return {"id": str(existing.id), "status": existing.status,
                    "version": int(existing.version or 0), "idempotent": True}
        no = f"INC-{datetime.utcnow():%Y%m%d%H%M%S%f}"
        x = InternshipIncident(
            tenant_id=_tid(), incident_no=no,
            batch_id=_as_id(b["batchId"]) if b.get("batchId") else None,
            internship_id=_as_id(b["internshipId"]) if b.get("internshipId") else None,
            company_id=_as_id(b["companyId"]) if b.get("companyId") else None,
            student_id=_as_id(b["studentId"]) if b.get("studentId") else None,
            incident_type=b.get("incidentType") or "OTHER",
            severity=str(b.get("severity") or "MEDIUM").upper(),
            occurred_at=b.get("occurredAt"), location=b.get("location"),
            summary=str(b.get("summary") or "").strip(),
            injury_flag=bool(b.get("injuryFlag")),
            affected_persons=b.get("affectedPersons"),
            emergency_action=b.get("emergencyAction"),
            file_ids=b.get("fileIds") or [], reported_by_name=_op(user),
            reported_at=datetime.utcnow(), idempotency_key=key, status="REPORTED")
        db.add(x)
        db.flush()
        if x.internship_id and x.severity in ("HIGH", "CRITICAL"):
            r = RiskRecord(
                tenant_id=_tid(), internship_id=x.internship_id,
                risk_code="INT-INCIDENT", risk_title="实习事故：" + (x.incident_type or "其他"),
                risk_level="HIGH", source_module="incident", status="PENDING_HANDLE")
            db.add(r)
            db.flush()
            x.risk_id = r.id
        _audit(db, x.id, "INTERNSHIP_INCIDENT", "REPORT", user, {
            "incidentNo": no, "severity": x.severity,
            "riskId": str(x.risk_id or ""), "actorUserId": _uid(user),
        })
        db.commit()
        return {"id": str(x.id), "status": x.status,
                "version": int(x.version or 0), "riskId": str(x.risk_id or "")}


def transition(iid, status, body=None, user=None):
    allowed = {
        "REPORTED": {"EMERGENCY_HANDLING", "INVESTIGATING"},
        "EMERGENCY_HANDLING": {"INVESTIGATING"},
        "INVESTIGATING": {"RECTIFYING", "PENDING_REVIEW"},
        "RECTIFYING": {"PENDING_REVIEW"},
        "PENDING_REVIEW": {"CLOSED"},
    }
    target = str(status or "").upper()
    with session() as db:
        x = db.scalar(select(InternshipIncident).where(
            InternshipIncident.id == _as_id(iid),
            InternshipIncident.tenant_id == _tid(),
            InternshipIncident.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("事故不存在")
        if x.internship_id:
            from app.modules.internship.services.internship_scope import assert_internship_record_scope
            assert_internship_record_scope(db, x.internship_id, user, "事故处置")
        b = body or {}
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "事故记录版本已变化，请刷新后重试")
        old_status = x.status
        if target not in allowed.get(old_status, set()):
            raise AppException("DATA_CONFLICT", f"不允许 {old_status}→{target}")
        for key, attr in (
            ("investigationConclusion", "investigation_conclusion"),
            ("rectificationPlan", "rectification_plan"),
            ("responsibilityConclusion", "responsibility_conclusion"),
            ("fileIds", "file_ids"),
        ):
            if key in b:
                setattr(x, attr, b[key])
        if target == "CLOSED":
            from app.core.permissions import enforce_permission, is_super_admin
            enforce_permission(user or {}, "internship.incident.close")
            role = str((user or {}).get("currentRoleCode") or "").upper()
            if x.severity in ("HIGH", "CRITICAL") and role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
                raise AppException("NO_PERMISSION", "HIGH/CRITICAL事故只能由学校管理员关闭")
            if (not x.investigation_conclusion or not x.rectification_plan or
                    not x.responsibility_conclusion or not x.file_ids):
                raise AppException("VALIDATION_ERROR", "关闭须具备调查结论、整改方案、复核意见和附件")
        x.status = target
        if target == "CLOSED":
            x.closed_at = datetime.utcnow()
            x.closed_by_name = _op(user)
        x.version = int(x.version or 0) + 1
        _audit(db, x.id, "INTERNSHIP_INCIDENT", f"TRANSITION_{target}", user, {
            "from": old_status, "to": target, "severity": x.severity,
            "actorUserId": _uid(user), "version": int(x.version or 0),
        })
        db.commit()
        return {"id": str(x.id), "status": x.status, "version": int(x.version or 0)}
