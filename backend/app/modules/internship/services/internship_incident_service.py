from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import AppException, not_found
from app.models import InternshipEmergencyPlan, InternshipIncident, RiskRecord
from app.services.db_service import _as_id, _tid, session
def _op(user):return (user or {}).get("realName") or "系统"
def create_plan(body):
    b=body or {}
    with session() as db:
        x=InternshipEmergencyPlan(tenant_id=_tid(),company_id=_as_id(b["companyId"]) if b.get("companyId") else None,batch_id=_as_id(b["batchId"]) if b.get("batchId") else None,plan_name=b.get("planName") or "",responsible_person=b.get("responsiblePerson"),emergency_contact=b.get("emergencyContact"),backup_contact=b.get("backupContact"),hospital_or_support=b.get("hospitalOrSupport"),response_steps=b.get("responseSteps"),valid_from=b.get("validFrom"),valid_until=b.get("validUntil"),file_ids=b.get("fileIds"),status="DRAFT")
        if not x.plan_name:raise AppException("VALIDATION_ERROR","预案名称必填")
        db.add(x);db.commit();return {"id":str(x.id),"status":x.status}
def review_plan(pid,action,user=None):
    with session() as db:
        x=db.get(InternshipEmergencyPlan,_as_id(pid))
        if not x or x.tenant_id!=_tid():raise not_found("应急预案不存在")
        if action=="SUBMIT" and x.status=="DRAFT":x.status="PENDING_REVIEW"
        elif action=="APPROVE" and x.status=="PENDING_REVIEW":x.status="APPROVED";x.reviewed_by_name=_op(user);x.reviewed_at=datetime.utcnow()
        else:raise AppException("DATA_CONFLICT","预案状态不允许该操作")
        db.commit();return {"id":str(x.id),"status":x.status}
def report_incident(body,user=None):
    b=body or {}; key=(b.get("idempotencyKey") or "").strip()
    if not key:raise AppException("VALIDATION_ERROR","idempotencyKey 必填")
    with session() as db:
        if b.get("internshipId"):
            from app.modules.internship.services.internship_scope import assert_internship_record_scope
            rec = assert_internship_record_scope(db, b["internshipId"], user, "事故上报")
            b["studentId"], b["batchId"], b["companyId"] = (
                rec.student_id, rec.batch_id, rec.enterprise_id)
        existing=db.scalars(select(InternshipIncident).where(InternshipIncident.tenant_id==_tid(),InternshipIncident.idempotency_key==key,InternshipIncident.is_deleted.is_(False))).first()
        if existing:return {"id":str(existing.id),"status":existing.status,"idempotent":True}
        no=f"INC-{datetime.utcnow():%Y%m%d%H%M%S%f}"
        x=InternshipIncident(tenant_id=_tid(),incident_no=no,batch_id=_as_id(b["batchId"]) if b.get("batchId") else None,internship_id=_as_id(b["internshipId"]) if b.get("internshipId") else None,company_id=_as_id(b["companyId"]) if b.get("companyId") else None,student_id=_as_id(b["studentId"]) if b.get("studentId") else None,incident_type=b.get("incidentType") or "OTHER",severity=b.get("severity") or "MEDIUM",occurred_at=b.get("occurredAt"),location=b.get("location"),summary=b.get("summary"),injury_flag=bool(b.get("injuryFlag")),file_ids=b.get("fileIds"),reported_by_name=_op(user),reported_at=datetime.utcnow(),idempotency_key=key,status="REPORTED")
        db.add(x);db.flush()
        if x.internship_id and x.severity in ("HIGH","CRITICAL"):
            r=RiskRecord(tenant_id=_tid(),internship_id=x.internship_id,risk_code="INT-INCIDENT",risk_title="实习事故："+(x.incident_type or "其他"),risk_level="HIGH",source_module="incident",status="PENDING_HANDLE");db.add(r);db.flush();x.risk_id=r.id
        db.commit();return {"id":str(x.id),"status":x.status,"riskId":str(x.risk_id or "")}
def transition(iid,status,body=None,user=None):
    allowed={"REPORTED":{"EMERGENCY_HANDLING","INVESTIGATING"},"EMERGENCY_HANDLING":{"INVESTIGATING"},"INVESTIGATING":{"RECTIFYING","PENDING_REVIEW"},"RECTIFYING":{"PENDING_REVIEW"},"PENDING_REVIEW":{"CLOSED"}}
    with session() as db:
        x=db.get(InternshipIncident,_as_id(iid))
        if not x or x.tenant_id!=_tid():raise not_found("事故不存在")
        if x.internship_id:
            from app.modules.internship.services.internship_scope import assert_internship_record_scope
            assert_internship_record_scope(db,x.internship_id,user,"事故处置")
        if status not in allowed.get(x.status,set()):raise AppException("DATA_CONFLICT",f"不允许 {x.status}→{status}")
        b=body or {}
        for k,a in (("investigationConclusion","investigation_conclusion"),("rectificationPlan","rectification_plan"),("fileIds","file_ids")):
            if k in b:setattr(x,a,b[k])
        if status=="CLOSED" and (not x.investigation_conclusion or not x.rectification_plan or not x.file_ids):raise AppException("VALIDATION_ERROR","关闭须具备调查结论、整改方案和附件")
        x.status=status
        if status=="CLOSED":x.closed_at=datetime.utcnow();x.closed_by_name=_op(user)
        db.commit();return {"id":str(x.id),"status":x.status}
