"""合规模板版本化服务：ACTIVE 永不原地覆盖。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipAuditTrail, InternshipComplianceTemplate
from app.services.db_service import _as_id, _tid, session


def _name(user): return (user or {}).get("realName") or "系统"


def _audit(db, obj, action, user, detail=None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=obj.id, target_type="COMPLIANCE_TPL",
           action=action, operator_name=_name(user), detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _row(t):
    return {"id": str(t.id), "code": t.template_code, "name": t.template_name, "version": t.template_version,
            "status": t.status, "config": t.config or {}, "changeReason": t.change_reason or "",
            "effectiveAt": t.effective_at.isoformat() if t.effective_at else None}


def list_templates(status=None):
    with session() as db:
        q = select(InternshipComplianceTemplate).where(InternshipComplianceTemplate.tenant_id == _tid(),
            InternshipComplianceTemplate.is_deleted.is_(False))
        if status: q = q.where(InternshipComplianceTemplate.status == status.upper())
        return [_row(x) for x in db.scalars(q.order_by(InternshipComplianceTemplate.template_code, InternshipComplianceTemplate.template_version.desc())).all()]


def create_draft(body, user=None):
    b = body or {}; code = (b.get("templateCode") or b.get("code") or "").strip()
    if not code or not (b.get("templateName") or b.get("name")): raise AppException("VALIDATION_ERROR", "模板编码和名称必填")
    with session() as db:
        latest = db.scalars(select(InternshipComplianceTemplate).where(InternshipComplianceTemplate.tenant_id == _tid(),
            InternshipComplianceTemplate.template_code == code).order_by(InternshipComplianceTemplate.template_version.desc())).first()
        t = InternshipComplianceTemplate(tenant_id=_tid(), template_code=code, template_name=b.get("templateName") or b.get("name"),
            template_version=(latest.template_version + 1 if latest else 1), status="DRAFT", config=deepcopy(b.get("config") or {}),
            change_reason=(b.get("changeReason") or "").strip() or None, remark=(b.get("remark") or "").strip() or None)
        db.add(t); db.flush(); _audit(db, t, "CREATE_DRAFT", user); db.commit(); return _row(t)


def activate(template_id, body=None, user=None):
    b = body or {}
    with session() as db:
        source = db.get(InternshipComplianceTemplate, _as_id(template_id))
        if not source or source.tenant_id != _tid() or source.is_deleted: raise not_found("合规模板不存在")
        if source.status == "ACTIVE":
            reason = (b.get("changeReason") or "").strip()
            if not reason:
                raise AppException("VALIDATION_ERROR", "启用新版 ACTIVE 模板必须填写变更原因（禁止原地覆盖）")
            source.status = "RETIRED"
            next_ver = source.template_version + 1
            active = InternshipComplianceTemplate(
                tenant_id=_tid(), template_code=source.template_code,
                template_name=b.get("templateName") or source.template_name,
                template_version=next_ver, status="ACTIVE",
                config=deepcopy(b.get("config", source.config) or {}),
                effective_at=datetime.utcnow(), approved_by_name=_name(user),
                approved_at=datetime.utcnow(), change_reason=reason)
            db.add(active); db.flush(); _audit(db, source, "RETIRE_FOR_NEW_VERSION", user)
            _audit(db, active, "ACTIVATE", user, {"fromVersion": source.template_version}); db.commit()
            return _row(active)
        reason = (b.get("changeReason") or source.change_reason or "").strip()
        for old in db.scalars(select(InternshipComplianceTemplate).where(
            InternshipComplianceTemplate.tenant_id == _tid(),
            InternshipComplianceTemplate.template_code == source.template_code,
            InternshipComplianceTemplate.status == "ACTIVE",
            InternshipComplianceTemplate.id != source.id)).all():
            old.status = "RETIRED"
        source.status = "ACTIVE"
        source.config = deepcopy(b.get("config", source.config) or {})
        source.effective_at = datetime.utcnow()
        source.approved_by_name = _name(user)
        source.approved_at = datetime.utcnow()
        source.change_reason = reason or source.change_reason
        _audit(db, source, "ACTIVATE", user); db.commit(); return _row(source)


def get_active(db, code=None):
    q = select(InternshipComplianceTemplate).where(InternshipComplianceTemplate.tenant_id == _tid(),
        InternshipComplianceTemplate.status == "ACTIVE", InternshipComplianceTemplate.is_deleted.is_(False))
    if code: q = q.where(InternshipComplianceTemplate.template_code == code)
    return db.scalars(q.order_by(InternshipComplianceTemplate.approved_at.desc(), InternshipComplianceTemplate.id.desc())).first()
