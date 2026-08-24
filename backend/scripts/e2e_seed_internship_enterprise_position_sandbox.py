from __future__ import annotations
import json, os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import _mysql_env  # noqa: F401
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipBatch, InternshipRecord, StudentProfile, Tenant
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_NO = "E2E20260001"
DEFAULT_FIXTURE_PATH = "../e2e/runtime/internship-enterprise-position-fixture.json"

def assert_safe_target():
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod","production"} or deploy_mode in {"prod","production"}:
        raise SystemExit("refusing IX-003/IX-005 E2E seed in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(x in lowered for x in ("e2e","test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(x in lowered for x in ("prod","production","staging")):
        raise SystemExit("DATABASE_URL looks like production/staging")
    if urlparse(db_url).hostname not in {"127.0.0.1","localhost","::1"}:
        raise SystemExit("IX-003/IX-005 seed only accepts a local database")

def run_id():
    raw = os.getenv("GITHUB_RUN_ID") or str(int(datetime.utcnow().timestamp()*1000))
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    return digits[-12:] or str(int(datetime.utcnow().timestamp()))

def fixture_path():
    return Path(os.getenv("E2E_INTERNSHIP_ENTERPRISE_POSITION_FIXTURE_FILE") or DEFAULT_FIXTURE_PATH).resolve()

def main():
    assert_safe_target()
    rid = run_id()
    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TENANT_ID)
        if not tenant or tenant.is_deleted or tenant.tenant_code != TENANT_CODE or tenant.status != "ACTIVE":
            raise SystemExit("sandbox-school tenant is missing or inactive")
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == TENANT_ID,
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not student:
            raise SystemExit(f"student {STUDENT_NO} is missing")
        batch = InternshipBatch(
            tenant_id=TENANT_ID, batch_name=f"IX-003-005 Browser First {rid}", batch_no=f"IXEP-{rid}",
            academic_year=f"{now.year}-{now.year+1}", term="第一学期",
            start_date=now-timedelta(days=15), end_date=now+timedelta(days=120),
            signup_start_date=now-timedelta(days=30), signup_end_date=now+timedelta(days=30),
            planned_count=2, status="RUNNING", stage_config=[],
            rules_config={"checkin":{},"weeklyReport":{},"guidance":{},"evaluation":{},"score":{}},
            remark="IX-003/IX-005 prerequisites only; enterprises/positions are browser-created",
        )
        db.add(batch); db.flush()
        campaign = InternshipRecruitmentCampaign(
            tenant_id=TENANT_ID, batch_id=batch.id, campaign_code=f"IXEP-{rid}",
            campaign_name=f"IX-003-005 招聘季 {rid}", round_no=1, status="OPEN",
            invite_start_at=now-timedelta(days=1), invite_end_at=now+timedelta(days=10),
            position_submit_start_at=now-timedelta(days=1), position_submit_end_at=now+timedelta(days=10),
            student_select_start_at=now-timedelta(days=1), student_select_end_at=now+timedelta(days=10),
            enterprise_decision_start_at=now-timedelta(days=1), enterprise_decision_end_at=now+timedelta(days=10),
            school_confirm_start_at=now-timedelta(days=1), school_confirm_end_at=now+timedelta(days=10),
            enterprise_access_end_at=now+timedelta(days=30), enterprise_confirm_required=False,
            teacher_confirm_sla_hours=48, application_material_policy_json={"schemaVersion":"V1"},
            remark="IX-003/IX-005 Browser First campaign prerequisite only",
        )
        db.add(campaign); db.flush()
        record = InternshipRecord(
            tenant_id=TENANT_ID, student_id=student.id, batch_id=batch.id,
            eligibility_status="QUALIFIED", destination_type="NONE", status="PREPARING",
            risk_level="NONE", intern_start_date=now+timedelta(days=14),
            intern_end_date=now+timedelta(days=104),
            remark="IX-003/IX-005 student prerequisite only; no placement seeded",
        )
        db.add(record); db.commit()
        payload = {"runId":rid,"tenantCode":TENANT_CODE,"batchId":str(batch.id),"batchName":batch.batch_name,
                   "campaignId":str(campaign.id),"campaignName":campaign.campaign_name,
                   "internshipId":str(record.id),"studentId":str(student.id),"studentNo":student.student_no,
                   "studentName":student.real_name,"initialStatus":record.status,
                   "initialDestinationType":record.destination_type}
        target = fixture_path(); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[e2e-ix-003-005-seed] ready:", json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())
