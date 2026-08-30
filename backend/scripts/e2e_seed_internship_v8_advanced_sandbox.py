"""Prepare isolated MySQL prerequisites for IX-GJ-05 through IX-GJ-08.

Only stable prerequisites are inserted here. The browser suite must still create
reports, changes, risks, evaluations, scores and appeals through production APIs.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.field_crypto import encrypt_sensitive, hash_sensitive
from app.db.session import get_sessionmaker
from app.models import (
    EmpCompany,
    InternshipAgreement,
    InternshipBatch,
    InternshipBatchParticipant,
    InternshipBatchPlan,
    InternshipCheckin,
    InternshipGuidance,
    InternshipInsurance,
    InternshipPlanAck,
    InternshipPlanTaskProgress,
    InternshipPosition,
    InternshipProcessReport,
    InternshipRecord,
    InternshipVisit,
    StudentProfile,
    TeacherStudentScope,
    User,
    WeeklyReport,
)
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise,
    InternshipEnterpriseMember,
    InternshipRecruitmentCampaign,
)
from app.modules.internship.services import internship_enterprise_access_service as enterprise_access_svc
from app.modules.internship.services import internship_placement_snapshot_service as placement_snapshot_svc
from app.services import system_role_shadow_service


TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "e2e" / "runtime" / "internship-v8-advanced-fixture.json"


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy in {"prod", "production"}:
        raise SystemExit("refusing to seed advanced internship fixtures in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    raw = str(os.getenv("DATABASE_URL") or "")
    lowered = raw.lower()
    if not raw or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must identify an E2E/test database")
    parsed = urlparse(raw)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("advanced internship seed accepts only a local database")


def one(db, model, entity_id: int):
    row = db.get(model, entity_id)
    if row is None or getattr(row, "tenant_id", TENANT_ID) != TENANT_ID:
        raise SystemExit(f"required {model.__name__} #{entity_id} is missing")
    return row


def ensure_employment_scope(db, student: StudentProfile) -> None:
    """Give the dedicated employment E2E identity an explicit student scope."""
    user = db.scalars(select(User).where(
        User.tenant_id == TENANT_ID,
        User.login_name == "e2e_ix_employment",
        User.is_deleted.is_(False),
    )).first()
    if user is None:
        return
    row = db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == TENANT_ID,
        TeacherStudentScope.teacher_key == user.login_name,
        TeacherStudentScope.role_code == "EMPLOYMENT_TEACHER",
        TeacherStudentScope.scope_type == "STUDENT",
        TeacherStudentScope.ref_value == student.student_no,
        TeacherStudentScope.is_deleted.is_(False),
    )).first()
    if row is None:
        db.add(TeacherStudentScope(
            tenant_id=TENANT_ID,
            teacher_key=user.login_name,
            teacher_name=user.real_name,
            role_code="EMPLOYMENT_TEACHER",
            scope_type="STUDENT",
            ref_value=student.student_no,
            status="ACTIVE",
        ))
    else:
        row.teacher_name = user.real_name
        row.status = "ACTIVE"


def require_enterprise_collaborator(db):
    """Reuse the enterprise account created by the earlier browser lifecycle journey."""
    result = db.execute(
        select(InternshipEnterpriseMember, User, EmpCompany)
        .join(
            User,
            (User.id == InternshipEnterpriseMember.user_id)
            & (User.tenant_id == InternshipEnterpriseMember.tenant_id),
        )
        .join(
            EmpCompany,
            (EmpCompany.id == InternshipEnterpriseMember.company_id)
            & (EmpCompany.tenant_id == InternshipEnterpriseMember.tenant_id),
        )
        .where(
            InternshipEnterpriseMember.tenant_id == TENANT_ID,
            InternshipEnterpriseMember.status == "ACTIVE",
            InternshipEnterpriseMember.is_deleted.is_(False),
            User.login_name.like("ixep_%"),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            EmpCompany.is_deleted.is_(False),
        )
        .order_by(InternshipEnterpriseMember.id.desc())
    ).first()
    if result is None:
        raise SystemExit(
            "active ixep enterprise collaborator is missing; "
            "run the enterprise-position browser journey first"
        )
    member, user, company = result
    company.status = "ACTIVE"
    company.coop_status = "ACTIVE"
    company.qualification_status = "PASSED"
    company.blacklist = False
    return member, user, company


def ensure_campaign(db, *, batch: InternshipBatch, company: EmpCompany, member):
    now = datetime.utcnow()
    campaign_code = "PW-V8-GJ08-ADVANCED"
    campaign = db.scalars(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.tenant_id == TENANT_ID,
        InternshipRecruitmentCampaign.campaign_code == campaign_code,
    )).first()
    values = {
        "batch_id": batch.id,
        "campaign_name": "GJ08 企业评价与成绩闭环招聘季",
        "round_no": 1,
        "status": "OPEN",
        "invite_start_at": now - timedelta(days=30),
        "invite_end_at": now + timedelta(days=30),
        "position_submit_start_at": now - timedelta(days=30),
        "position_submit_end_at": now + timedelta(days=30),
        "student_select_start_at": now - timedelta(days=30),
        "student_select_end_at": now + timedelta(days=30),
        "enterprise_decision_start_at": now - timedelta(days=30),
        "enterprise_decision_end_at": now + timedelta(days=30),
        "school_confirm_start_at": now - timedelta(days=30),
        "school_confirm_end_at": now + timedelta(days=30),
        "enterprise_access_end_at": now + timedelta(days=180),
        "enterprise_confirm_required": False,
        "application_material_policy_json": {"schemaVersion": "V1"},
        "teacher_confirm_sla_hours": 48,
        "remark": "Only for the isolated GJ08 browser journey",
    }
    if campaign is None:
        campaign = InternshipRecruitmentCampaign(
            tenant_id=TENANT_ID,
            campaign_code=campaign_code,
            **values,
        )
        db.add(campaign)
        db.flush()
    else:
        for key, value in values.items():
            setattr(campaign, key, value)
        campaign.is_deleted = False

    relation = db.scalars(select(InternshipCampaignEnterprise).where(
        InternshipCampaignEnterprise.tenant_id == TENANT_ID,
        InternshipCampaignEnterprise.campaign_id == campaign.id,
        InternshipCampaignEnterprise.company_id == company.id,
    )).first()
    if relation is None:
        relation = InternshipCampaignEnterprise(
            tenant_id=TENANT_ID,
            campaign_id=campaign.id,
            company_id=company.id,
            status="ACCEPTED",
            invite_source="MANUAL",
            invited_by_user_id=member.user_id,
            invited_at=now,
            accepted_at=now,
        )
        db.add(relation)
    else:
        relation.status = "ACCEPTED"
        relation.accepted_at = relation.accepted_at or now
        relation.declined_at = None
        relation.revoked_at = None
        relation.revoke_reason = None
        relation.is_deleted = False
    db.flush()
    return campaign


def ensure_journey_record(
    db,
    *,
    code: str,
    student: StudentProfile,
    mentor: User,
    member,
    company: EmpCompany,
):
    """Create one stable, formal placement per journey without relying on database IDs."""
    now = datetime.utcnow()
    batch_no = f"PW-V8-{code}-ADVANCED"
    batch = db.scalars(select(InternshipBatch).where(
        InternshipBatch.tenant_id == TENANT_ID,
        InternshipBatch.batch_no == batch_no,
    )).first()
    batch_values = {
        "batch_name": f"{code} 高级黄金旅程独立批次",
        "academic_year": f"{now.year}-{now.year + 1}",
        "term": "第一学期",
        "start_date": now - timedelta(days=30),
        "end_date": now + timedelta(days=90),
        "signup_start_date": now - timedelta(days=45),
        "signup_end_date": now + timedelta(days=30),
        "planned_count": 1,
        "status": "RUNNING",
        "stage_config": [],
        "rules_config": {
            "checkin": {},
            "weeklyReport": {},
            "guidance": {},
            "evaluation": {},
            "score": {},
        },
        "remark": f"Only for the isolated {code} browser journey",
    }
    if batch is None:
        batch = InternshipBatch(
            tenant_id=TENANT_ID,
            batch_no=batch_no,
            **batch_values,
        )
        db.add(batch)
        db.flush()
    else:
        for key, value in batch_values.items():
            setattr(batch, key, value)
        batch.is_deleted = False

    campaign = ensure_campaign(db, batch=batch, company=company, member=member) if code == "GJ08" else None
    title = f"{code} 高级黄金旅程基础岗位"
    position = db.scalars(select(InternshipPosition).where(
        InternshipPosition.tenant_id == TENANT_ID,
        InternshipPosition.batch_id == batch.id,
        InternshipPosition.title == title,
    )).first()
    position_values = {
        "company_id": company.id,
        "company_name": company.name,
        "campaign_id": campaign.id if campaign else None,
        "source_type": "SCHOOL",
        "category": "软件质量",
        "major_requirement": "软件技术/计算机应用",
        "grade_requirement": f"{now.year + 1}届",
        "work_location": "长沙市岳麓区",
        "work_address": "岳麓区高级黄金旅程测试园区 8 号",
        "work_content": "软件质量验证、缺陷闭环与安全记录",
        "headcount": 3,
        "allocated_count": 1,
        "mentor_contact_id": member.contact_id,
        "mentor_name": "企业质量导师",
        "daily_hours": 8,
        "weekly_hours": 40,
        "shift_type": "DAY",
        "night_shift": False,
        "overtime_allowed": False,
        "rest_days_per_week": 2,
        "remuneration_type": "MONTHLY",
        "remuneration_amount": 3600,
        "remuneration_cycle": "MONTHLY",
        "salary_range": "3600 元/月",
        "accommodation_provided": False,
        "meal_provided": True,
        "hazardous_flag": False,
        "rights_status": "PASSED",
        "rights_rule_version": "e2e-advanced-v1",
        "rights_checked_at": now,
        "status": "PUBLISHED",
        "publish_at": now,
    }
    if position is None:
        position = InternshipPosition(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            title=title,
            **position_values,
        )
        db.add(position)
        db.flush()
    else:
        for key, value in position_values.items():
            setattr(position, key, value)
        position.is_deleted = False

    record = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == TENANT_ID,
        InternshipRecord.student_id == student.id,
        InternshipRecord.batch_id == batch.id,
    )).first()
    record_values = {
        "enterprise_name": company.name,
        "position_name": position.title,
        "advisor_name": mentor.real_name,
        "advisor_user_id": mentor.id,
        "enterprise_mentor_name": position.mentor_name,
        "enterprise_id": company.id,
        "position_id": position.id,
        "mentor_contact_id": member.contact_id,
        "eligibility_status": "QUALIFIED",
        "destination_type": "ASSIGNED",
        "status": "ONBOARD",
        "risk_level": "NONE",
        "intern_start_date": now - timedelta(days=30),
        "intern_end_date": now + timedelta(days=30),
        "insurance_info": "GJ 高级旅程实习责任险",
        "agreement_info": "GJ 高级旅程三方协议已生效",
        "remark": f"Only for the isolated {code} browser journey",
    }
    if record is None:
        record = InternshipRecord(
            tenant_id=TENANT_ID,
            student_id=student.id,
            batch_id=batch.id,
            **record_values,
        )
        db.add(record)
        db.flush()
    else:
        for key, value in record_values.items():
            setattr(record, key, value)
        record.is_deleted = False

    participant = db.scalars(select(InternshipBatchParticipant).where(
        InternshipBatchParticipant.tenant_id == TENANT_ID,
        InternshipBatchParticipant.batch_id == batch.id,
        InternshipBatchParticipant.student_id == student.id,
    )).first()
    participant_values = {
        "source": "MANUAL",
        "snapshot_student_no": student.student_no,
        "snapshot_name": student.real_name,
        "internship_id": record.id,
        "status": "ACTIVE",
        "remove_reason": None,
    }
    if participant is None:
        participant = InternshipBatchParticipant(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            student_id=student.id,
            **participant_values,
        )
        db.add(participant)
    else:
        for key, value in participant_values.items():
            setattr(participant, key, value)
        participant.is_deleted = False
    db.flush()

    current_snapshot = None
    if record.current_placement_snapshot_id:
        from app.models.internship_placement_snapshot import InternshipPlacementSnapshot

        current_snapshot = db.scalars(select(InternshipPlacementSnapshot).where(
            InternshipPlacementSnapshot.id == record.current_placement_snapshot_id,
            InternshipPlacementSnapshot.tenant_id == TENANT_ID,
            InternshipPlacementSnapshot.record_id == record.id,
            InternshipPlacementSnapshot.company_id == company.id,
            InternshipPlacementSnapshot.position_id == position.id,
        )).first()
    if current_snapshot is None:
        placement_snapshot_svc.capture_placement_snapshot_in_tx(
            db,
            record=record,
            position=position,
            company=company,
            rights={"passed": True, "ruleVersion": "e2e-advanced-v1"},
        )
    return batch, record


def ensure_enterprise_collaboration_grant(
    db,
    *,
    batch: InternshipBatch,
    company_id: int,
    member_id: int,
):
    """Establish the formal GJ08 precondition through the production Grant Authority."""
    member = db.scalars(select(InternshipEnterpriseMember).where(
        InternshipEnterpriseMember.tenant_id == TENANT_ID,
        InternshipEnterpriseMember.id == member_id,
        InternshipEnterpriseMember.company_id == company_id,
        InternshipEnterpriseMember.status == "ACTIVE",
        InternshipEnterpriseMember.is_deleted.is_(False),
    ).order_by(InternshipEnterpriseMember.id.desc())).first()
    if member is None:
        raise SystemExit(f"active enterprise member for company #{company_id} is missing")
    user = db.scalars(select(User).where(
        User.id == member.user_id,
        User.tenant_id == TENANT_ID,
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    )).first()
    if user is None:
        raise SystemExit(f"active enterprise account for company #{company_id} is missing")
    campaign = db.scalars(
        select(InternshipRecruitmentCampaign)
        .join(
            InternshipCampaignEnterprise,
            InternshipCampaignEnterprise.campaign_id == InternshipRecruitmentCampaign.id,
        )
        .where(
            InternshipRecruitmentCampaign.tenant_id == TENANT_ID,
            InternshipRecruitmentCampaign.batch_id == batch.id,
            InternshipRecruitmentCampaign.status == "OPEN",
            InternshipRecruitmentCampaign.is_deleted.is_(False),
            InternshipCampaignEnterprise.tenant_id == TENANT_ID,
            InternshipCampaignEnterprise.company_id == company_id,
            InternshipCampaignEnterprise.status == "ACCEPTED",
            InternshipCampaignEnterprise.is_deleted.is_(False),
        )
        .order_by(InternshipRecruitmentCampaign.id.desc())
    ).first()
    if campaign is None:
        raise SystemExit(f"accepted recruitment campaign for company #{company_id} and batch #{batch.id} is missing")
    valid_from = datetime.utcnow() - timedelta(days=1)
    valid_until = datetime.utcnow() + timedelta(days=180)
    enterprise_access_svc.issue_grant_in_tx(
        db,
        tenant_id=TENANT_ID,
        member_id=member.id,
        grant_type="INTERNSHIP_COLLAB",
        campaign_id=None,
        batch_id=batch.id,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    return user.login_name, campaign.campaign_name


def ensure_plan(db, *, batch: InternshipBatch, record: InternshipRecord) -> InternshipBatchPlan:
    plan = db.scalars(select(InternshipBatchPlan).where(
        InternshipBatchPlan.tenant_id == TENANT_ID,
        InternshipBatchPlan.batch_id == batch.id,
        InternshipBatchPlan.is_deleted.is_(False),
    )).first()
    task = {
        "sortOrder": 1,
        "name": "完成质量巡检与日报复盘",
        "requirement": "按安全规范完成一次巡检，形成可复核的完成说明",
        "deadline": (datetime.utcnow() + timedelta(days=14)).isoformat(),
    }
    if plan is None:
        plan = InternshipBatchPlan(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            title="GJ05 在岗过程计划",
            objectives="完成过程报告、指导、巡访与整改闭环",
            content="先确认计划，再按周提交真实过程事实；退回后必须基于当前版本重交。",
            tasks_json=[task],
            status="PUBLISHED",
            published_at=datetime.utcnow(),
            published_by_name="E2E学校管理员",
        )
        db.add(plan)
        db.flush()
    else:
        plan.title = "GJ05 在岗过程计划"
        plan.objectives = "完成过程报告、指导、巡访与整改闭环"
        plan.content = "先确认计划，再按周提交真实过程事实；退回后必须基于当前版本重交。"
        plan.tasks_json = [task]
        plan.status = "PUBLISHED"
        plan.published_at = plan.published_at or datetime.utcnow()

    ack = db.scalars(select(InternshipPlanAck).where(
        InternshipPlanAck.tenant_id == TENANT_ID,
        InternshipPlanAck.internship_id == record.id,
        InternshipPlanAck.plan_id == plan.id,
        InternshipPlanAck.is_deleted.is_(False),
    )).first()
    if ack is None:
        db.add(InternshipPlanAck(
            tenant_id=TENANT_ID,
            plan_id=plan.id,
            internship_id=record.id,
            student_id=record.student_id,
            status="PENDING",
        ))
    else:
        ack.status = "PENDING"
        ack.acknowledged_at = None

    progress = db.scalars(select(InternshipPlanTaskProgress).where(
        InternshipPlanTaskProgress.tenant_id == TENANT_ID,
        InternshipPlanTaskProgress.internship_id == record.id,
        InternshipPlanTaskProgress.plan_id == plan.id,
        InternshipPlanTaskProgress.task_sort_order == 1,
        InternshipPlanTaskProgress.is_deleted.is_(False),
    )).first()
    if progress is None:
        db.add(InternshipPlanTaskProgress(
            tenant_id=TENANT_ID,
            plan_id=plan.id,
            internship_id=record.id,
            student_id=record.student_id,
            task_sort_order=1,
            task_name=task["name"],
            status="NOT_STARTED",
        ))
    else:
        progress.status = "NOT_STARTED"
        progress.student_note = None
        progress.review_comment = None
        progress.submitted_at = None
    return plan


def ensure_change_target(db, *, batch: InternshipBatch, record: InternshipRecord) -> InternshipPosition:
    company_name = "GJ06 重新上岗目标企业"
    company = db.scalars(select(EmpCompany).where(
        EmpCompany.tenant_id == TENANT_ID,
        EmpCompany.name == company_name,
        EmpCompany.is_deleted.is_(False),
    )).first()
    if company is None:
        company = EmpCompany(
            tenant_id=TENANT_ID,
            name=company_name,
            credit_code="GJ06REONBOARD20260830",
            industry="软件和信息技术服务业",
            city="长沙",
            address="岳麓区重新上岗测试园区 6 号",
            contact_person="赵老师",
            coop_status="ACTIVE",
            qualification_status="PASSED",
            status="ACTIVE",
            blacklist=False,
        )
        db.add(company)
        db.flush()
    else:
        company.coop_status = "ACTIVE"
        company.qualification_status = "PASSED"
        company.status = "ACTIVE"
        company.blacklist = False

    base_title = "GJ06 重新上岗质量工程岗"
    current_position = db.get(InternshipPosition, int(record.position_id or 0)) if record.position_id else None
    # A repeated Browser replay must still perform a real position change. Alternate between two
    # equally valid targets instead of weakening the production guard that rejects a no-op change.
    suffix = "B" if current_position and current_position.title == f"{base_title} A" else "A"
    title = f"{base_title} {suffix}"
    position = db.scalars(select(InternshipPosition).where(
        InternshipPosition.tenant_id == TENANT_ID,
        InternshipPosition.batch_id == batch.id,
        InternshipPosition.title == title,
        InternshipPosition.is_deleted.is_(False),
    )).first()
    if position is None:
        position = InternshipPosition(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            company_id=company.id,
            company_name=company.name,
            title=title,
            work_location="长沙市岳麓区",
            work_address="岳麓区重新上岗测试园区 6 号",
            work_content="软件质量验证、缺陷闭环与安全记录",
            headcount=3,
            allocated_count=0,
            daily_hours=8,
            weekly_hours=40,
            shift_type="DAY",
            night_shift=False,
            overtime_allowed=False,
            rest_days_per_week=2,
            remuneration_type="MONTHLY",
            remuneration_amount=3200,
            remuneration_cycle="MONTHLY",
            salary_range="3200 元/月",
            accommodation_provided=False,
            meal_provided=True,
            hazardous_flag=False,
            status="PUBLISHED",
            publish_at=datetime.utcnow(),
        )
        db.add(position)
        db.flush()
    else:
        position.status = "PUBLISHED"
        position.headcount = max(int(position.headcount or 0), 3)
        position.allocated_count = 0
        position.shift_type = "DAY"
        position.night_shift = False
        position.overtime_allowed = False
        position.remuneration_type = "MONTHLY"
        position.remuneration_amount = 3200
        position.remuneration_cycle = "MONTHLY"
        position.salary_range = "3200 元/月"
        position.accommodation_provided = False
        position.meal_provided = True
        position.hazardous_flag = False
    record.status = "ONBOARD"
    record.risk_level = "NONE"
    return position


def ensure_score_facts(db, *, record: InternshipRecord) -> None:
    today = date.today()
    # The journey seals the record again in GJ09. Re-open this isolated E2E record so a second
    # exact-HEAD replay can execute GJ08 before exercising the real archive transition again.
    record.status = "ASSESSING"
    record.risk_level = "NONE"
    company = one(db, EmpCompany, int(record.enterprise_id))
    position = one(db, InternshipPosition, int(record.position_id))
    company.status = "ACTIVE"
    company.coop_status = "ACTIVE"
    company.qualification_status = "PASSED"
    company.blacklist = False
    position.status = "PUBLISHED"

    def missing(model, *conditions):
        return db.scalars(select(model).where(*conditions)).first() is None

    common = [lambda model: model.tenant_id == TENANT_ID, lambda model: model.internship_id == record.id]
    if missing(InternshipInsurance, common[0](InternshipInsurance), common[1](InternshipInsurance), InternshipInsurance.is_deleted.is_(False)):
        db.add(InternshipInsurance(tenant_id=TENANT_ID, internship_id=record.id, student_id=record.student_id, status="VERIFIED"))
    if missing(InternshipAgreement, common[0](InternshipAgreement), common[1](InternshipAgreement), InternshipAgreement.is_deleted.is_(False)):
        db.add(InternshipAgreement(tenant_id=TENANT_ID, internship_id=record.id, student_id=record.student_id, status="EFFECTIVE"))
    start = record.intern_start_date
    end = record.intern_end_date
    start_date = start.date() if isinstance(start, datetime) else start
    end_date = end.date() if isinstance(end, datetime) else end
    if not isinstance(start_date, date) or not isinstance(end_date, date) or start_date > end_date:
        raise SystemExit(f"record #{record.id} has no valid internship period")

    # The score gate counts scheduled weekdays inside the internship period. Seed
    # one independently auditable normal check-in for every scheduled weekday.
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5 and missing(
            InternshipCheckin,
            common[0](InternshipCheckin),
            common[1](InternshipCheckin),
            InternshipCheckin.checkin_date == cursor.isoformat(),
            InternshipCheckin.is_deleted.is_(False),
        ):
            db.add(InternshipCheckin(
                tenant_id=TENANT_ID,
                internship_id=record.id,
                checkin_date=cursor.isoformat(),
                checkin_at=datetime.combine(cursor, datetime.min.time()).replace(hour=8, minute=30),
                result="NORMAL",
                address="GJ08 合规实习岗位",
                note="GJ08 可复核在岗事实",
            ))
        cursor += timedelta(days=1)

    # The 13-week batch rule requires an approved report for each week. Existing
    # reports are preserved; only missing weeks receive complete reviewed facts.
    expected_weeks = max(1, ((end_date - start_date).days // 7) + 1)
    for week_number in range(1, expected_weeks + 1):
        if missing(
            WeeklyReport,
            common[0](WeeklyReport),
            common[1](WeeklyReport),
            WeeklyReport.week_number == week_number,
            WeeklyReport.is_deleted.is_(False),
        ):
            db.add(WeeklyReport(
                tenant_id=TENANT_ID,
                internship_id=record.id,
                week_number=week_number,
                work_content=f"第 {week_number} 周完成岗位质量检查、问题登记和闭环验证。",
                harvest_content="掌握了安全操作、质量复核与证据留存方法。",
                plan_content="下周继续完成计划任务并复核风险项。",
                word_count=800,
                report_version=1,
                submitted_at=datetime.combine(
                    min(start_date + timedelta(days=week_number * 7 - 1), end_date),
                    datetime.min.time(),
                ).replace(hour=18),
                status="APPROVED",
                review_action="APPROVE",
                review_comment="内容和证据完整，通过。",
                reviewed_by_name=record.advisor_name,
                reviewed_at=datetime.utcnow(),
            ))
    if missing(InternshipProcessReport, common[0](InternshipProcessReport), common[1](InternshipProcessReport), InternshipProcessReport.is_deleted.is_(False)):
        db.add(InternshipProcessReport(tenant_id=TENANT_ID, internship_id=record.id, report_type="MONTHLY", period_key=today.strftime("%Y-%m"), content="GJ08 完整月报事实", word_count=800, submitted_at=datetime.utcnow(), status="APPROVED"))
    if missing(InternshipGuidance, common[0](InternshipGuidance), common[1](InternshipGuidance), InternshipGuidance.is_deleted.is_(False)):
        db.add(InternshipGuidance(tenant_id=TENANT_ID, internship_id=record.id, student_id=record.student_id, advisor_name=record.advisor_name, method="ONSITE", content="GJ08 完整指导事实", status="NORMAL"))
    if missing(InternshipVisit, common[0](InternshipVisit), common[1](InternshipVisit), InternshipVisit.is_deleted.is_(False)):
        db.add(InternshipVisit(tenant_id=TENANT_ID, internship_id=record.id, student_id=record.student_id, advisor_name=record.advisor_name, enterprise_name=record.enterprise_name, visit_at=datetime.utcnow(), method="ONSITE", rectify_status="NONE"))


def main() -> int:
    assert_safe_target()
    # Runtime SYSTEM roles consume the immutable published template, not the
    # legacy pattern map directly.  Keep the E2E authority snapshot converged
    # whenever the delivered role contract changes.
    system_role_shadow_service.converge_published_system_templates(
        actor_user_id=None,
        source_commit_sha="internship-v8-advanced-e2e",
    )
    db = get_sessionmaker()()
    try:
        student_a = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TENANT_ID, StudentProfile.student_no == "E2E20260001", StudentProfile.is_deleted.is_(False))).first()
        if student_a is None:
            raise SystemExit("E2E20260001 is missing")
        resident_id = "430102200001010011"
        student_a.id_card_encrypted = encrypt_sensitive(resident_id, "id_card")
        student_a.id_card_hash = hash_sensitive(resident_id, "id_card")
        ensure_employment_scope(db, student_a)

        mentor = db.scalars(select(User).where(
            User.tenant_id == TENANT_ID,
            User.login_name == "e2e_advisor_a",
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )).first()
        if mentor is None:
            raise SystemExit("active e2e_advisor_a mentor is missing")
        enterprise_member, _enterprise_user, company = require_enterprise_collaborator(db)
        gj05_batch, gj05_record = ensure_journey_record(
            db, code="GJ05", student=student_a, mentor=mentor,
            member=enterprise_member, company=company,
        )
        gj06_batch, gj06_record = ensure_journey_record(
            db, code="GJ06", student=student_a, mentor=mentor,
            member=enterprise_member, company=company,
        )
        gj07_batch, gj07_record = ensure_journey_record(
            db, code="GJ07", student=student_a, mentor=mentor,
            member=enterprise_member, company=company,
        )
        gj08_batch, gj08_record = ensure_journey_record(
            db, code="GJ08", student=student_a, mentor=mentor,
            member=enterprise_member, company=company,
        )

        gj05_record.status = "ONBOARD"
        gj05_plan = ensure_plan(db, batch=gj05_batch, record=gj05_record)
        target = ensure_change_target(db, batch=gj06_batch, record=gj06_record)
        gj07_record.status = "ONBOARD"
        gj07_record.risk_level = "NONE"
        enterprise_login, enterprise_campaign_name = ensure_enterprise_collaboration_grant(
            db,
            batch=gj08_batch,
            company_id=int(gj08_record.enterprise_id),
            member_id=int(enterprise_member.id),
        )
        ensure_score_facts(db, record=gj08_record)
        db.commit()

        payload = {
            "tenantCode": TENANT_CODE,
            "student": {"username": "E2E20260001", "name": student_a.real_name},
            "mentor": {"username": "e2e_advisor_a", "name": gj05_record.advisor_name},
            "enterprise": {
                "username": enterprise_login,
                "companyId": str(gj08_record.enterprise_id),
                "companyName": gj08_record.enterprise_name,
                "campaignName": enterprise_campaign_name,
            },
            "gj05": {"batchId": str(gj05_batch.id), "batchName": gj05_batch.batch_name, "internshipId": str(gj05_record.id), "planId": str(gj05_plan.id)},
            "gj06": {"batchId": str(gj06_batch.id), "batchName": gj06_batch.batch_name, "internshipId": str(gj06_record.id), "targetPositionId": str(target.id), "targetPositionName": target.title, "targetCompanyId": str(target.company_id), "targetCompanyName": target.company_name},
            "gj07": {"batchId": str(gj07_batch.id), "batchName": gj07_batch.batch_name, "internshipId": str(gj07_record.id)},
            "gj08": {"batchId": str(gj08_batch.id), "batchName": gj08_batch.batch_name, "internshipId": str(gj08_record.id), "placementSnapshotId": str(gj08_record.current_placement_snapshot_id or "")},
        }
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[e2e-internship-v8-advanced-seed] ready:", json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
