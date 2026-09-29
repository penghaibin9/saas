#!/usr/bin/env python3
from datetime import datetime, timedelta

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import EmpCompany, InternshipBatch, Tenant, User
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise,
    InternshipEnterpriseAccessGrant,
    InternshipEnterpriseMember,
    InternshipRecruitmentCampaign,
)

TENANT_ID=88201
BATCH_ID=88241
COMPANY_ID=88251
USER_ID=88213
MEMBER_ID=88261
CAMPAIGN_ID=88271

db=get_sessionmaker()()
now=datetime.utcnow().replace(microsecond=0)
try:
    tenant=Tenant(
        id=TENANT_ID, tenant_code="YIYANG-ENTERPRISE",
        school_name="益阳职业技术学院", short_name="益阳职院",
        deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
    )
    batch=InternshipBatch(
        id=BATCH_ID, tenant_id=TENANT_ID, batch_name="2026岗位实习",
        batch_no="YIYANG-2026-ENTERPRISE", academic_year="2026-2027",
        term="1", planned_count=20, status="RUNNING",
        archive_status="NOT_ARCHIVED", rules_version=1,
    )
    company=EmpCompany(
        id=COMPANY_ID, tenant_id=TENANT_ID, name="益阳智能制造有限公司",
        credit_code="914309000000000001", industry="智能制造", city="益阳",
        status="ACTIVE", coop_status="ACTIVE", qualification_status="PASSED",
        blacklist=False, access_valid_until=now+timedelta(days=90),
        short_name="益阳智造", address="湖南省益阳市高新区",
    )
    user=User(
        id=USER_ID, tenant_id=TENANT_ID, login_name="enterprise.fullstack.hr",
        real_name="企业HR李经理", password_hash=hash_password("Enterprise-Evidence-2026!"),
        user_type="ENTERPRISE_MENTOR", status="ACTIVE",
        must_change_password=False, credential_version=0,
    )
    campaign=InternshipRecruitmentCampaign(
        id=CAMPAIGN_ID, tenant_id=TENANT_ID, batch_id=BATCH_ID,
        campaign_code="YIYANG-2026-R1", campaign_name="2026岗位实习企业双选",
        round_no=1, status="OPEN",
        invite_start_at=now-timedelta(days=5), invite_end_at=now+timedelta(days=10),
        position_submit_start_at=now-timedelta(days=5), position_submit_end_at=now+timedelta(days=10),
        student_select_start_at=now-timedelta(days=2), student_select_end_at=now+timedelta(days=15),
        enterprise_decision_start_at=now-timedelta(days=1), enterprise_decision_end_at=now+timedelta(days=20),
        school_confirm_start_at=now, school_confirm_end_at=now+timedelta(days=25),
        enterprise_access_end_at=now+timedelta(days=30),
    )
    participation=InternshipCampaignEnterprise(
        tenant_id=TENANT_ID, campaign_id=CAMPAIGN_ID, company_id=COMPANY_ID,
        status="ACCEPTED", invite_source="MANUAL",
        invited_at=now-timedelta(days=3), accepted_at=now-timedelta(days=2),
    )
    member=InternshipEnterpriseMember(
        id=MEMBER_ID, tenant_id=TENANT_ID, company_id=COMPANY_ID, user_id=USER_ID,
        member_role="HR", status="ACTIVE", is_primary=True,
        accepted_at=now-timedelta(days=2), last_active_at=now,
    )
    grant=InternshipEnterpriseAccessGrant(
        tenant_id=TENANT_ID, member_id=MEMBER_ID, company_id=COMPANY_ID,
        grant_type="RECRUITMENT", campaign_id=CAMPAIGN_ID, batch_id=BATCH_ID,
        valid_from=now-timedelta(days=1), valid_until=now+timedelta(days=30), status="ACTIVE",
    )
    db.add_all([tenant,batch,company,user,campaign,participation,member,grant])
    db.commit()
    print({"tenantCode":"YIYANG-ENTERPRISE","campaignId":CAMPAIGN_ID,"memberId":MEMBER_ID})
except Exception:
    db.rollback()
    raise
finally:
    db.close()
