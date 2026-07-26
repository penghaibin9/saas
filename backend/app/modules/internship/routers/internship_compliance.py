"""岗位实习 P2 合规、准入与证据包 API。"""
from fastapi import APIRouter, Body, Depends
from fastapi.responses import FileResponse

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import (
    internship_audit_service as internship_audit,
    internship_compliance_notice_service as notice,
    internship_compliance_service as compliance,
    internship_compliance_template_service as tpl,
    internship_consent_service as consent,
    internship_enterprise_inspection_service as insp,
    internship_evidence_package_service as evidence,
    internship_incident_service as incident,
    internship_safety_service as safety,
    internship_special_filing_service as filing,
)

router = APIRouter(prefix="/internship/compliance", tags=["岗位实习·合规"])


@router.get("/templates")
def templates(user=Depends(require_permission("internship.compliance.view"))):
    return success(tpl.list_templates())


@router.post("/templates")
def template_create(body: dict = Body(...), user=Depends(require_permission("internship.compliance.manage"))):
    return success(tpl.create_draft(body, user))


@router.post("/templates/{iid}/activate")
def template_activate(iid: str, body: dict = Body(default={}),
                      user=Depends(require_permission("internship.compliance.review"))):
    return success(tpl.activate(iid, body, user))


@router.get("/inspections/{company_id}")
def inspections(company_id: str,
                user=Depends(require_permission("internship.enterprise.inspection.view"))):
    return success(insp.list_by_company(company_id))


@router.post("/inspections")
def inspection_create(body: dict = Body(...),
                      user=Depends(require_permission("internship.enterprise.inspection.manage"))):
    return success(insp.create(body, user))


@router.post("/inspections/{iid}/{action}")
def inspection_action(iid: str, action: str, body: dict = Body(default={}),
                      user=Depends(require_permission("internship.enterprise.inspection.manage"))):
    normalized = str(action or "").lower()
    if normalized == "submit":
        return success(insp.submit(iid, user))
    return success(insp.review(
        iid, normalized.upper(), body.get("comment", ""), body.get("validUntil"), user))


@router.post("/consents")
def consent_create(body: dict = Body(...),
                   user=Depends(require_permission("internship.consent.manage"))):
    return success(consent.create_pending(body, user))


@router.post("/consents/{iid}/revoke")
def consent_revoke(iid: str, body: dict = Body(...),
                   user=Depends(require_permission("internship.consent.manage"))):
    return success(consent.revoke_task(iid, body, user))


@router.get("/safety/{batch_id}")
def safety_courses(batch_id: str,
                   user=Depends(require_permission("internship.safety.view"))):
    return success(safety.list_courses(batch_id, user=user))


@router.post("/safety")
def safety_create(body: dict = Body(...),
                  user=Depends(require_permission("internship.safety.manage"))):
    return success(safety.create_course(body, user=user))


@router.post("/safety/completions")
def safety_ensure(body: dict = Body(...),
                  user=Depends(require_permission("internship.safety.manage"))):
    return success(safety.ensure_completion(body, user))


@router.post("/safety/completions/{iid}/review")
def safety_review(iid: str, body: dict = Body(...),
                  user=Depends(require_permission("internship.safety.manage"))):
    return success(safety.teacher_review_completion(
        iid, score=body.get("score"), action=body.get("action"),
        comment=body.get("comment"), expected_version=body.get("expectedVersion"), user=user))


@router.get("/batches/{batch_id}/stats")
def batch_stats(batch_id: str,
                user=Depends(require_permission("internship.compliance.view"))):
    return success(compliance.batch_compliance_stats(batch_id, user))


@router.post("/filings")
def filing_create(body: dict = Body(...),
                  user=Depends(require_permission("internship.filing.review"))):
    """特殊备案由学院/学校合规角色建单；普通只读角色不得用 view 权限创建。"""
    return success(filing.create(body, user))


@router.post("/filings/{iid}/{level}/{action}")
def filing_action(iid: str, level: str, action: str, body: dict = Body(default={}),
                  user=Depends(require_permission("internship.filing.review"))):
    normalized = str(action or "").lower()
    if normalized == "submit":
        return success(filing.submit(iid, user, expected_version=body.get("expectedVersion")))
    return success(filing.review(
        iid, level.upper(), normalized.upper(), body.get("comment", ""), user,
        expected_version=body.get("expectedVersion")))


@router.post("/incidents")
def incident_report(body: dict = Body(...),
                    user=Depends(require_permission("internship.incident.report"))):
    return success(incident.report_incident(body, user))


@router.post("/incidents/{iid}/transition")
def incident_transition(iid: str, body: dict = Body(...),
                        user=Depends(require_permission("internship.incident.handle"))):
    return success(incident.transition(iid, body.get("status", ""), body, user))


@router.post("/emergency-plans")
def emergency_create(body: dict = Body(...),
                     user=Depends(require_permission("internship.incident.handle"))):
    return success(incident.create_plan(body, user=user))


@router.post("/emergency-plans/{iid}/{action}")
def emergency_action(iid: str, action: str,
                     user=Depends(require_permission("internship.incident.handle"))):
    return success(incident.review_plan(iid, action.upper(), user))


@router.get("/evaluate/{internship_id}")
def evaluate(internship_id: str, operation: str = "ONBOARD",
             user=Depends(require_permission("internship.compliance.view"))):
    return success(compliance.evaluate_internship_compliance(internship_id, operation, user))


@router.post("/exemptions")
def exemption(body: dict = Body(...),
              user=Depends(require_permission("internship.compliance.exempt.request"))):
    return success(compliance.grant_exemption(body, user))


@router.post("/exemptions/{exemption_id}/review")
def exemption_review(exemption_id: str, body: dict = Body(...),
                     user=Depends(require_permission("internship.compliance.exempt.approve"))):
    return success(compliance.review_exemption(exemption_id, body, user))


@router.post("/notices")
def notice_send(body: dict = Body(...),
                user=Depends(require_permission("internship.consent.manage"))):
    return success(notice.send_compliance_notice(
        body["receiverUserId"], body.get("title") or "实习合规提醒",
        body.get("content") or "", body.get("consentId"), user))


@router.get("/notices/{message_id}/receipts")
def notice_receipts(message_id: str,
                    user=Depends(require_permission("internship.compliance.view"))):
    return success(notice.list_receipts(message_id))


@router.post("/notices/{message_id}/ack")
def notice_ack(message_id: str,
               user=Depends(require_permission("internship.consent.manage"))):
    return success(notice.ack_message(message_id, user))


@router.post("/evidence-packages/{package_type}/{target_id}")
def package(package_type: str, target_id: str,
            user=Depends(require_permission("internship.evidence.export"))):
    return success(evidence.generate(package_type, target_id, user))


@router.get("/evidence-packages/{package_id}/download")
def package_download(package_id: str,
                     user=Depends(require_permission("internship.evidence.export"))):
    path, filename = evidence.resolve_package_download(package_id, user)
    return FileResponse(path, filename=filename, media_type="application/zip")


@router.get("/audit-outbox/health")
def audit_outbox_health(user=Depends(require_permission("internship.compliance.view"))):
    return success(internship_audit.health_status())
