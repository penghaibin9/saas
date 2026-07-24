"""岗位实习 P2 合规、准入与证据包 API。"""
from fastapi import APIRouter, Body, Depends
from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_compliance_template_service as tpl, internship_enterprise_inspection_service as insp, internship_consent_service as consent, internship_safety_service as safety, internship_special_filing_service as filing, internship_incident_service as incident, internship_compliance_service as compliance, internship_compliance_notice_service as notice, internship_evidence_package_service as evidence
router=APIRouter(prefix="/internship/compliance",tags=["岗位实习·合规"])
@router.get("/templates")
def templates(user=Depends(require_permission("internship.compliance.view"))):return success(tpl.list_templates())
@router.post("/templates")
def template_create(body:dict=Body(...),user=Depends(require_permission("internship.compliance.manage"))):return success(tpl.create_draft(body,user))
@router.post("/templates/{iid}/activate")
def template_activate(iid:str,body:dict=Body(default={}),user=Depends(require_permission("internship.compliance.review"))):return success(tpl.activate(iid,body,user))
@router.get("/inspections/{company_id}")
def inspections(company_id:str,user=Depends(require_permission("internship.enterprise.inspection.view"))):return success(insp.list_by_company(company_id))
@router.post("/inspections")
def inspection_create(body:dict=Body(...),user=Depends(require_permission("internship.enterprise.inspection.manage"))):return success(insp.create(body,user))
@router.post("/inspections/{iid}/{action}")
def inspection_action(iid:str,action:str,body:dict=Body(default={}),user=Depends(require_permission("internship.enterprise.inspection.manage"))):return success(insp.submit(iid,user) if action=="submit" else insp.review(iid,action.upper(),body.get("comment",""),body.get("validUntil"),user))
@router.post("/consents")
def consent_create(body:dict=Body(...),user=Depends(require_permission("internship.consent.manage"))):return success(consent.create_pending(body,user))
@router.post("/consents/{iid}/confirm")
def consent_confirm(iid:str,body:dict=Body(...),user=Depends(require_permission("internship.consent.manage"))):return success(consent.confirm(iid,body,user))
@router.get("/safety/{batch_id}")
def safety_courses(batch_id:str,user=Depends(require_permission("internship.safety.view"))):return success(safety.list_courses(batch_id))
@router.post("/safety")
def safety_create(body:dict=Body(...),user=Depends(require_permission("internship.safety.manage"))):return success(safety.create_course(body))
@router.post("/safety/completions")
def safety_ensure(body: dict = Body(...), user=Depends(require_permission("internship.safety.manage"))):
    return success(safety.ensure_completion(body, user))


@router.post("/safety/completions/{iid}/review")
def safety_review(iid: str, body: dict = Body(...), user=Depends(require_permission("internship.safety.manage"))):
    return success(safety.teacher_review_completion(
        iid, body.get("score"), body.get("studiedMinutes"), body.get("commitment"), user))


@router.get("/batches/{batch_id}/stats")
def batch_stats(batch_id: str, user=Depends(require_permission("internship.compliance.view"))):
    return success(compliance.batch_compliance_stats(batch_id, user))
@router.post("/filings")
def filing_create(body:dict=Body(...),user=Depends(require_permission("internship.filing.view"))):return success(filing.create(body,user))
@router.post("/filings/{iid}/{level}/{action}")
def filing_action(iid:str,level:str,action:str,body:dict=Body(default={}),user=Depends(require_permission("internship.filing.review"))):return success(filing.submit(iid) if action=="submit" else filing.review(iid,level.upper(),action.upper(),body.get("comment",""),user))
@router.post("/incidents")
def incident_report(body:dict=Body(...),user=Depends(require_permission("internship.incident.handle"))):return success(incident.report_incident(body,user))
@router.post("/incidents/{iid}/transition")
def incident_transition(iid:str,body:dict=Body(...),user=Depends(require_permission("internship.incident.close"))):return success(incident.transition(iid,body.get("status",""),body,user))
@router.post("/emergency-plans")
def emergency_create(body:dict=Body(...),user=Depends(require_permission("internship.incident.handle"))):return success(incident.create_plan(body))
@router.post("/emergency-plans/{iid}/{action}")
def emergency_action(iid:str,action:str,user=Depends(require_permission("internship.incident.handle"))):return success(incident.review_plan(iid,action.upper(),user))
@router.get("/evaluate/{internship_id}")
def evaluate(internship_id:str,operation:str="ONBOARD",user=Depends(require_permission("internship.compliance.view"))):return success(compliance.evaluate_internship_compliance(internship_id,operation,user))
@router.post("/exemptions")
def exemption(body:dict=Body(...),user=Depends(require_permission("internship.compliance.exempt"))):return success(compliance.grant_exemption(body,user))
@router.post("/notices")
def notice_send(body:dict=Body(...),user=Depends(require_permission("internship.consent.manage"))):return success(notice.send_compliance_notice(body["receiverUserId"],body.get("title") or "实习合规提醒",body.get("content") or "",body.get("consentId"),user))
@router.get("/notices/{message_id}/receipts")
def notice_receipts(message_id:str,user=Depends(require_permission("internship.compliance.view"))):return success(notice.list_receipts(message_id))
@router.post("/notices/{message_id}/ack")
def notice_ack(message_id:str,user=Depends(require_permission("internship.consent.manage"))):return success(notice.ack_message(message_id,user))
@router.post("/evidence-packages/{package_type}/{target_id}")
def package(package_type:str,target_id:str,user=Depends(require_permission("internship.evidence.export"))):return success(evidence.generate(package_type,target_id,user))
