from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import AppException, not_found
from app.models import InternshipRecord, InternshipSpecialFiling
from app.services.db_service import _as_id, _tid, session
def evaluate_triggers(position, student=None, school_region=None):
    out=[]
    if position and position.night_shift:out.append(("NIGHT_SHIFT","岗位包含夜班"))
    if position and position.hazardous_flag:out.append(("HIGH_RISK","岗位标记为危险/高风险"))
    region=getattr(position,"work_location",None) or ""
    if school_region and region and school_region not in region:out.append(("CROSS_PROVINCE","岗位地点跨省"))
    return out
def create(body,user=None):
    b=body or {}
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec=assert_internship_record_scope(db,b.get("internshipId"),user,"创建特殊备案")
        x=InternshipSpecialFiling(tenant_id=_tid(),internship_id=rec.id,batch_id=rec.batch_id,student_id=rec.student_id,filing_type=b.get("filingType") or "OTHER",trigger_reason=b.get("triggerReason"),destination_region=b.get("destinationRegion"),work_address=b.get("workAddress"),risk_description=b.get("riskDescription"),student_application=b.get("studentApplication"),guardian_consent_required=bool(b.get("guardianConsentRequired")),file_ids=b.get("fileIds"),status="DRAFT")
        db.add(x);db.commit();return {"id":str(x.id),"status":x.status}
def submit(fid,user=None):
    with session() as db:
        x=db.get(InternshipSpecialFiling,_as_id(fid))
        if not x or x.tenant_id!=_tid():raise not_found("特殊备案不存在")
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db,x.internship_id,user,"提交特殊备案")
        if x.status!="DRAFT":raise AppException("DATA_CONFLICT","仅草稿可提交")
        x.status="PENDING_COLLEGE";db.commit();return {"id":str(x.id),"status":x.status}
def review(fid,level,action,comment="",user=None):
    if level not in ("COLLEGE","SCHOOL") or action not in ("APPROVE","REJECT"):raise AppException("VALIDATION_ERROR","审核参数错误")
    with session() as db:
        x=db.get(InternshipSpecialFiling,_as_id(fid))
        if not x or x.tenant_id!=_tid():raise not_found("特殊备案不存在")
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db,x.internship_id,user,"审核特殊备案")
        expected="PENDING_"+level
        if x.status!=expected:raise AppException("DATA_CONFLICT","当前备案不在该审核环节")
        n=(user or {}).get("realName") or "系统"
        if level=="COLLEGE":x.college_review_by=n;x.college_review_at=datetime.utcnow();x.college_comment=comment;x.status="PENDING_SCHOOL" if action=="APPROVE" else "REJECTED"
        else:x.school_review_by=n;x.school_review_at=datetime.utcnow();x.school_comment=comment;x.status="APPROVED" if action=="APPROVE" else "REJECTED";x.approved_by_name=n if action=="APPROVE" else None;x.approved_at=datetime.utcnow() if action=="APPROVE" else None
        db.commit();return {"id":str(x.id),"status":x.status}
def supersede_old(db,internship_id):
    for x in db.scalars(select(InternshipSpecialFiling).where(InternshipSpecialFiling.tenant_id==_tid(),InternshipSpecialFiling.internship_id==_as_id(internship_id),InternshipSpecialFiling.status=="APPROVED")).all():x.status="SUPERSEDED"
