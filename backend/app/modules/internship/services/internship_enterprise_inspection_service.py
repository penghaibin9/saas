from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import AppException, not_found
from app.models import EmpCompany, InternshipAuditTrail, InternshipEnterpriseInspection
from app.services.db_service import _as_id, _tid, session

def _op(user): return (user or {}).get("realName") or "系统"
def _row(x): return {"id": str(x.id), "companyId": str(x.company_id), "batchId": str(x.batch_id or ""), "status": x.status, "validUntil": x.valid_until.isoformat() if x.valid_until else None, "conclusion": x.conclusion or ""}
def _audit(db,x,a,u): db.add(InternshipAuditTrail(tenant_id=_tid(),target_id=x.id,target_type="ENTERPRISE_INSPECTION",action=a,operator_name=_op(u),occurred_at=datetime.utcnow()))

def list_by_company(company_id):
    with session() as db: return [_row(x) for x in db.scalars(select(InternshipEnterpriseInspection).where(InternshipEnterpriseInspection.tenant_id==_tid(),InternshipEnterpriseInspection.company_id==_as_id(company_id),InternshipEnterpriseInspection.is_deleted.is_(False)).order_by(InternshipEnterpriseInspection.id.desc())).all()]
def create(body,user=None):
    b=body or {}
    if not b.get("companyId"): raise AppException("VALIDATION_ERROR","companyId 必填")
    with session() as db:
        x=InternshipEnterpriseInspection(tenant_id=_tid(),company_id=_as_id(b["companyId"]),batch_id=_as_id(b["batchId"]) if b.get("batchId") else None,inspection_type=b.get("inspectionType") or "DOCUMENT",inspection_date=b.get("inspectionDate"),inspectors=b.get("inspectors"),conclusion=b.get("conclusion"),risk_items=b.get("riskItems"),rectification_items=b.get("rectificationItems"),file_ids=b.get("fileIds"),valid_until=b.get("validUntil"),status="DRAFT")
        db.add(x);db.flush();_audit(db,x,"CREATE",user);db.commit();return _row(x)
def submit(iid,user=None):
    with session() as db:
        x=db.get(InternshipEnterpriseInspection,_as_id(iid))
        if not x or x.tenant_id!=_tid(): raise not_found("企业考察不存在")
        if x.status!="DRAFT": raise AppException("DATA_CONFLICT","仅草稿可提交")
        x.status="SUBMITTED";_audit(db,x,"SUBMIT",user);db.commit();return _row(x)
def review(iid,action,comment="",valid_until=None,user=None):
    if action not in ("APPROVE","REJECT"): raise AppException("VALIDATION_ERROR","action 必须是 APPROVE/REJECT")
    with session() as db:
        x=db.get(InternshipEnterpriseInspection,_as_id(iid))
        if not x or x.tenant_id!=_tid(): raise not_found("企业考察不存在")
        if x.status!="SUBMITTED": raise AppException("DATA_CONFLICT","仅已提交记录可审核")
        x.status="APPROVED" if action=="APPROVE" else "REJECTED";x.review_comment=comment or None;x.reviewed_by_name=_op(user);x.reviewed_at=datetime.utcnow()
        if valid_until:
            if isinstance(valid_until, str):
                valid_until = datetime.fromisoformat(valid_until.replace("Z", ""))
            x.valid_until = valid_until
        if action=="APPROVE":
            c=db.get(EmpCompany,x.company_id)
            if c: c.access_valid_until=x.valid_until
        _audit(db,x,"REVIEW_"+action,user);db.commit();return _row(x)
def is_enterprise_access_valid(db,company_id,rules):
    c=db.get(EmpCompany,_as_id(company_id))
    if not c or c.tenant_id!=_tid(): return False,"企业不存在"
    if c.blacklist or c.coop_status in ("BLACKLIST","SUSPENDED","ARCHIVED"): return False,"企业合作状态不可准入"
    ea=(rules or {}).get("enterpriseAccess") or {}
    # 未要求考察时：仅校验主体与黑名单/合作状态
    if not ea.get("required") and not ea.get("requireOnsiteInspection"):
        if c.access_valid_until and c.access_valid_until < datetime.utcnow():
            return False,"企业准入有效期已过"
        return True,""
    x=db.scalars(select(InternshipEnterpriseInspection).where(InternshipEnterpriseInspection.tenant_id==_tid(),InternshipEnterpriseInspection.company_id==_as_id(company_id),InternshipEnterpriseInspection.status=="APPROVED",InternshipEnterpriseInspection.is_deleted.is_(False)).order_by(InternshipEnterpriseInspection.id.desc())).first()
    until=(x.valid_until if x else c.access_valid_until)
    if not x: return False,"缺少已通过的企业考察"
    if until and until < datetime.utcnow(): return False,"企业准入考察已过期"
    return True,""
