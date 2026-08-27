from __future__ import annotations
import os
import _mysql_env  # noqa: F401
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import (
    EmpCompany, InternshipAuditTrail, InternshipBatchParticipant, InternshipPosition, InternshipRecord,
)
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise, InternshipEnterpriseAccessGrant, InternshipEnterpriseMember,
)

TENANT_ID = 1000000000000000007

def req(name):
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value

def main():
    company_id = int(req("E2E_IX003_COMPANY_ID"))
    position_id = int(req("E2E_IX005_POSITION_ID"))
    campaign_id = int(req("E2E_IX005_CAMPAIGN_ID"))
    batch_id = int(req("E2E_IX005_BATCH_ID"))
    internship_id = int(req("E2E_IX005_INTERNSHIP_ID"))
    expected_title = req("E2E_IX005_POSITION_TITLE")
    db = get_sessionmaker()()
    try:
        company = db.get(EmpCompany, company_id)
        assert company and company.tenant_id == TENANT_ID and not company.is_deleted
        assert company.coop_status == "ACTIVE", company.coop_status
        assert company.qualification_status == "PASSED", company.qualification_status
        assert company.blacklist is False

        participation = db.scalar(select(InternshipCampaignEnterprise).where(
            InternshipCampaignEnterprise.tenant_id == TENANT_ID,
            InternshipCampaignEnterprise.campaign_id == campaign_id,
            InternshipCampaignEnterprise.company_id == company_id,
            InternshipCampaignEnterprise.is_deleted.is_(False),
        ))
        assert participation and participation.status == "ACCEPTED"

        member = db.scalar(select(InternshipEnterpriseMember).where(
            InternshipEnterpriseMember.tenant_id == TENANT_ID,
            InternshipEnterpriseMember.company_id == company_id,
            InternshipEnterpriseMember.status == "ACTIVE",
            InternshipEnterpriseMember.is_deleted.is_(False),
        ).order_by(InternshipEnterpriseMember.id.desc()))
        assert member is not None
        grant = db.scalar(select(InternshipEnterpriseAccessGrant).where(
            InternshipEnterpriseAccessGrant.tenant_id == TENANT_ID,
            InternshipEnterpriseAccessGrant.member_id == member.id,
            InternshipEnterpriseAccessGrant.company_id == company_id,
            InternshipEnterpriseAccessGrant.campaign_id == campaign_id,
            InternshipEnterpriseAccessGrant.grant_type == "RECRUITMENT",
            InternshipEnterpriseAccessGrant.status == "ACTIVE",
            InternshipEnterpriseAccessGrant.is_deleted.is_(False),
        ))
        assert grant is not None

        position = db.get(InternshipPosition, position_id)
        assert position and position.tenant_id == TENANT_ID and not position.is_deleted
        assert position.company_id == company_id
        assert position.campaign_id == campaign_id
        assert position.batch_id == batch_id
        assert position.source_type == "ENTERPRISE"
        assert position.title == expected_title, (position.title, expected_title)
        assert position.status == "PUBLISHED", position.status
        assert int(position.headcount or 0) == 2
        assert int(position.allocated_count or 0) == 0

        record = db.get(InternshipRecord, internship_id)
        assert record and record.tenant_id == TENANT_ID and not record.is_deleted
        assert record.batch_id == batch_id
        assert record.position_id is None
        assert record.enterprise_id is None
        assert record.destination_type == "NONE"
        assert record.eligibility_status == "QUALIFIED"

        participant = db.scalar(select(InternshipBatchParticipant).where(
            InternshipBatchParticipant.tenant_id == TENANT_ID,
            InternshipBatchParticipant.batch_id == batch_id,
            InternshipBatchParticipant.student_id == record.student_id,
            InternshipBatchParticipant.is_deleted.is_(False),
        ))
        assert participant is not None
        assert participant.status == "ACTIVE", participant.status
        assert participant.source == "MANUAL", participant.source
        assert int(participant.internship_id or 0) == int(record.id), (
            participant.internship_id, record.id,
        )

        enterprise_actions = list(db.scalars(select(InternshipAuditTrail.action).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "ENTERPRISE",
            InternshipAuditTrail.target_id == company_id,
        )))
        for action in ("CREATE","REVIEW_APPROVE","COOP_SUSPEND","COOP_RESUME","BLACKLIST_ON","BLACKLIST_OFF"):
            assert action in enterprise_actions, (action, enterprise_actions)

        position_actions = list(db.scalars(select(InternshipAuditTrail.action).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "POSITION",
            InternshipAuditTrail.target_id == position_id,
        )))
        for action in (
            "ENTERPRISE_POSITION_CREATE","ENTERPRISE_POSITION_SUBMIT","UPDATE",
            "STATUS_PUBLISH","STATUS_OFFLINE","RISK_ON","RISK_OFF","STATUS_SUSPEND",
        ):
            assert action in position_actions, (action, position_actions)
        assert position_actions.count("STATUS_PUBLISH") >= 3, position_actions

        print("[e2e-ix-003-005-verify] PASS", {
            "companyId": company_id,
            "positionId": position_id,
            "campaignId": campaign_id,
            "participantId": participant.id,
            "enterpriseActions": enterprise_actions,
            "positionActions": position_actions,
        })
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())
