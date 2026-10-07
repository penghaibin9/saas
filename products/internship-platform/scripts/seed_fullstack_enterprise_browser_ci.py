#!/usr/bin/env python3
from datetime import datetime, timedelta

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import (
    EmpCompany, InternshipBatch, InternshipPlacementSnapshot, InternshipPosition,
    InternshipRecord, StudentProfile, Tenant, User,
)
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
POSITION_ID=88281
STUDENT_ID=88291
RECORD_ID=88301
PLACEMENT_ID=88311

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
    position=InternshipPosition(
        id=POSITION_ID, tenant_id=TENANT_ID, company_id=COMPANY_ID,
        company_name="益阳智能制造有限公司", batch_id=BATCH_ID, campaign_id=CAMPAIGN_ID,
        source_type="ENTERPRISE", title="智能制造产线运维实习生",
        category="智能制造", major_requirement="机电一体化/智能制造",
        grade_requirement="2026级", work_location="益阳高新区",
        work_address="湖南省益阳市高新区产业园", salary_range="3500-4500元/月",
        headcount=8, allocated_count=0, daily_hours=8, weekly_hours=40,
        shift_type="DAY", night_shift=False, overtime_allowed=False,
        rest_days_per_week=2, remuneration_type="MONTHLY",
        remuneration_amount=4000, remuneration_cycle="MONTH",
        accommodation_provided=True, meal_provided=True, hazardous_flag=False,
        work_content="产线巡检、设备点检、工艺记录与安全协作",
        rights_status="PASSED", status="PUBLISHED", publish_at=now-timedelta(days=1),
    )
    student=StudentProfile(
        id=STUDENT_ID, tenant_id=TENANT_ID, student_no="202688291",
        real_name="企业协同学生王强", grade="2026",
        current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE",
    )
    record=InternshipRecord(
        id=RECORD_ID, tenant_id=TENANT_ID, student_id=STUDENT_ID, batch_id=BATCH_ID,
        enterprise_name="益阳智能制造有限公司", position_name="智能制造产线运维实习生",
        advisor_name="校内指导教师刘老师", enterprise_mentor_name="企业HR李经理",
        enterprise_id=COMPANY_ID, position_id=POSITION_ID,
        eligibility_status="QUALIFIED", destination_type="ASSIGNED",
        status="ONBOARD", risk_level="NONE",
        intern_start_date=now-timedelta(days=20), intern_end_date=now+timedelta(days=100),
        agreement_info="SIGNED", insurance_info="VALID",
    )
    placement=InternshipPlacementSnapshot(
        id=PLACEMENT_ID, tenant_id=TENANT_ID, record_id=RECORD_ID,
        placement_seq=1, snapshot_version=1, campaign_id=CAMPAIGN_ID,
        batch_id=BATCH_ID, company_id=COMPANY_ID, position_id=POSITION_ID,
        company_name="益阳智能制造有限公司",
        company_credit_code="914309000000000001",
        position_title="智能制造产线运维实习生", position_category="智能制造",
        work_location="益阳高新区", work_address="湖南省益阳市高新区产业园",
        work_content="产线巡检、设备点检、工艺记录与安全协作",
        major_requirement="机电一体化/智能制造", grade_requirement="2026级",
        salary_range="3500-4500元/月", remuneration_type="MONTHLY",
        remuneration_amount=4000, remuneration_cycle="MONTH",
        daily_hours=8, weekly_hours=40, shift_type="DAY",
        night_shift=False, overtime_allowed=False, rest_days_per_week=2,
        accommodation_provided=True, meal_provided=True, hazardous_flag=False,
        enterprise_mentor_name="企业HR李经理", rights_status="PASSED",
        rights_rule_version="CI-FULLSTACK-1", rights_checked_at=now-timedelta(days=1),
        position_version=0, position_updated_at=now-timedelta(days=1),
        snapshot_json={"source":"fullstack-enterprise-ci","positionId":str(POSITION_ID)},
        snapshot_hash="a"*64, snapshot_sha256="a"*64,
        placement_at=now-timedelta(days=20), captured_at=now-timedelta(days=20),
        captured_by_user_id=USER_ID,
    )
    record.current_placement_snapshot_id=PLACEMENT_ID
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
    recruitment_grant=InternshipEnterpriseAccessGrant(
        tenant_id=TENANT_ID, member_id=MEMBER_ID, company_id=COMPANY_ID,
        grant_type="RECRUITMENT", campaign_id=CAMPAIGN_ID, batch_id=BATCH_ID,
        valid_from=now-timedelta(days=1), valid_until=now+timedelta(days=30), status="ACTIVE",
    )
    collaboration_grant=InternshipEnterpriseAccessGrant(
        tenant_id=TENANT_ID, member_id=MEMBER_ID, company_id=COMPANY_ID,
        grant_type="INTERNSHIP_COLLAB", campaign_id=None, batch_id=BATCH_ID,
        valid_from=now-timedelta(days=1), valid_until=now+timedelta(days=150), status="ACTIVE",
    )
    db.add_all([
        tenant,batch,company,user,campaign,position,student,record,placement,
        participation,member,recruitment_grant,collaboration_grant,
    ])
    db.commit()
    print({"tenantCode":"YIYANG-ENTERPRISE","campaignId":CAMPAIGN_ID,"memberId":MEMBER_ID})
except Exception:
    db.rollback()
    raise
finally:
    db.close()
