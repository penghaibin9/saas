"""Canonical school queue: MySQL queries, frozen submissions and scope before pagination."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import InternshipApplication, InternshipBatch, InternshipPosition, InternshipRecord, StudentProfile
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_school_volunteer_service as svc

TID = 1000000000000000001
ADMIN = {"userId": "db-1", "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN"}
MENTOR = {"userId": "db-99117", "userType": "TEACHER", "currentRoleCode": "INTERN_MENTOR"}
BASE = "/api/v1/internship/recruitment-campaigns"


def _seed():
    suffix = uuid4().hex[:10]
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        assert db.bind.dialect.name == "mysql"
        batch = InternshipBatch(tenant_id=TID, batch_name="学校确认队列", batch_no=suffix, status="RUNNING")
        db.add(batch); db.flush()
        campaign = InternshipRecruitmentCampaign(tenant_id=TID, batch_id=batch.id,
            campaign_code=suffix, campaign_name="虚构招聘季", round_no=1, status="OPEN")
        db.add(campaign); db.flush()
        ids = {"campaign": campaign.id, "batch": batch.id}
        for index, status in enumerate(("SUBMITTED", "LOCKED", "APPROVED", "DRAFT")):
            student = StudentProfile(tenant_id=TID, student_no=f"QUEUE-{suffix}-{index}",
                real_name=f"虚构学生{index}", status="ACTIVE", student_status="NORMAL")
            db.add(student); db.flush()
            record = InternshipRecord(tenant_id=TID, student_id=student.id, batch_id=batch.id,
                advisor_user_id=99117 if index in (0, 2) else 99118, status="PREPARING")
            db.add(record); db.flush()
            group = InternshipVolunteerGroup(tenant_id=TID, student_id=student.id, record_id=record.id,
                batch_id=batch.id, campaign_id=campaign.id, status=status, submission_version=2,
                submitted_at=now, teacher_confirm_deadline=now-timedelta(minutes=1) if status=="LOCKED" else None)
            db.add(group); db.flush()
            ids[str(index)] = group.id
            if index:
                continue
            position = InternshipPosition(tenant_id=TID, company_id=12345, company_name="虚构企业",
                batch_id=batch.id, campaign_id=campaign.id, title="软件实习生", status="PUBLISHED", headcount=3)
            db.add(position); db.flush()
            snapshots = []
            for version in (1, 2):
                snapshot = InternshipApplicationMaterialSnapshot(tenant_id=TID, volunteer_group_id=group.id,
                    student_id=student.id, batch_id=batch.id, campaign_id=campaign.id,
                    submission_version=version, profile_version=version,
                    profile_snapshot_json={"summary": f"第{version}次冻结材料"}, school_fact_snapshot_json={},
                    consent_version="v1", consent_at=now, contact_sharing_policy={"mode":"NONE"},
                    snapshot_hash=f"{suffix}-{version}")
                db.add(snapshot); db.flush(); snapshots.append(snapshot)
            group.current_material_snapshot_id = snapshots[1].id
            app = InternshipApplication(tenant_id=TID, campaign_record_id=record.id, student_id=student.id,
                batch_id=batch.id, campaign_id=campaign.id, application_type="POSITION", volunteer_no=1,
                position_id=position.id, material_snapshot_id=snapshots[1].id,
                application_statement="希望参与前端开发", status="PENDING_REVIEW")
            db.add(app); db.flush()
            for snapshot, status, effect in ((snapshots[0],"ACCEPT_INTENT","SUPERSEDED"),
                                            (snapshots[1],"INTERVIEW","ACTIVE")):
                db.add(InternshipEnterpriseApplicationDecision(tenant_id=TID, application_id=app.id,
                    volunteer_group_id=group.id, campaign_id=campaign.id, batch_id=batch.id,
                    company_id=position.company_id, position_id=position.id, material_snapshot_id=snapshot.id,
                    submission_version=snapshot.submission_version, decision_status=status, effect_status=effect))
            # Same record has a legitimate old school-source application; it is not a canonical choice.
            db.add(InternshipApplication(tenant_id=TID, record_id=record.id, student_id=student.id,
                batch_id=batch.id, application_type="POSITION", volunteer_no=1,
                application_note="旧单据不应混入", status="PENDING_REVIEW"))
        db.commit()
        return ids


def test_school_http_queue_and_current_material_keep_legacy_and_history_separate(client, auth_headers, db_mode):
    ids = _seed()
    root = f"{BASE}/{ids['campaign']}/volunteer-groups"
    context = client.get(BASE+'/review-context', headers=auth_headers, params={"batchId":ids['batch']})
    assert context.status_code == 200, context.json()
    assert [item['id'] for item in context.json()['data']['items']] == [str(ids['campaign'])]
    response = client.get(root, headers=auth_headers, params={"pageSize":1})
    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert data["total"] == 2 and len(data["items"]) == 1
    assert data["items"][0]["id"] == str(ids["1"])
    assert data["items"][0]["lockExpired"] is True
    assert data["items"][0]["status"] == "LOCKED"  # read never changes the workflow
    detail = client.get(f"{root}/{ids['0']}", headers=auth_headers)
    assert detail.status_code == 200, detail.json()
    row = detail.json()["data"]
    assert row["material"]["profileSnapshot"] == {"summary":"第2次冻结材料"}
    assert len(row["volunteers"]) == 1
    assert row["volunteers"][0]["currentSubmission"] is True
    assert row["volunteers"][0]["enterpriseDecision"]["status"] == "INTERVIEW"
    assert len(row["decisionHistory"]) == 2
    assert "旧单据不应混入" not in detail.text
    assert client.get(root, headers=auth_headers, params={"status":"invalid"}).status_code == 400
    assert client.get(root, headers=auth_headers, params={"pageSize":101}).status_code == 400


def test_school_scope_is_applied_to_count_pages_and_direct_detail(db_mode):
    ids = _seed()
    set_tenant({"tenantId":str(TID)})
    try:
        page = svc.list_groups(campaign_id=ids["campaign"], user=MENTOR, page_size=1)
        assert page["total"] == 1 and page["items"][0]["id"] == str(ids["0"])
        assert svc.list_groups(campaign_id=ids["campaign"], user=MENTOR, page=2, page_size=1)["items"] == []
        assert svc.get_group(campaign_id=ids["campaign"], group_id=ids["0"], user=MENTOR)["id"] == str(ids["0"])
        with pytest.raises(AppException) as denied:
            svc.get_group(campaign_id=ids["campaign"], group_id=ids["1"], user=MENTOR)
        assert denied.value.http_status == 404
        assert svc.list_groups(campaign_id=ids["campaign"], user=MENTOR, keyword="%")['total'] == 0
        assert svc.list_groups(campaign_id=ids["campaign"], user=MENTOR, status="ALL")['total'] == 2
        assert len(svc.review_context(batch_id=ids['batch'], user=MENTOR)['items']) == 1
        assert svc.review_context(batch_id=ids['batch']+1000, user=MENTOR)['items'] == []
        set_tenant({"tenantId":str(TID+1)})
        with pytest.raises(AppException) as foreign:
            svc.get_group(campaign_id=ids["campaign"], group_id=ids["0"], user=ADMIN)
        assert foreign.value.http_status == 404
    finally:
        set_tenant(None)


def test_mobile_same_group_current_material_and_required_scope(client, db_mode):
    from tests.test_teacher_mobile_position_catalog import headers
    ids = _seed()
    root = "/api/v1/mobile/teacher/internship/context/volunteer-groups"
    params = {"campaignId":ids["campaign"], "batchId":ids["batch"]}
    own = headers(99117)
    queue = client.get(root, headers=own, params=params)
    assert queue.status_code == 200, queue.json()
    assert queue.json()["data"]["total"] == 1
    detail = client.get(f"{root}/{ids['0']}", headers=own, params=params)
    assert detail.status_code == 200, detail.json()
    assert detail.json()["data"]["material"]["profileSnapshot"]["summary"] == "第2次冻结材料"
    assert client.get(f"{root}/{ids['1']}", headers=own, params=params).status_code == 404
    assert client.get(root, headers=own, params={**params,"batchId":ids['batch']+1000}).status_code == 404
    assert client.get(root, headers=own, params={"campaignId":ids["campaign"]}).status_code == 400
    assert client.get(root, headers=headers(99117,role="STUDENT"), params=params).status_code == 403
    assert client.get(root, params=params).status_code == 401
