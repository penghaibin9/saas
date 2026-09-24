"""No recruitment season is a business state; a foreign batch remains an error."""
from datetime import datetime, timedelta
import uuid
import pytest
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipRecord, PlatformConfig, Role, StudentAccountLink, Tenant, User, UserRole
from app.core.security import create_access_token
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from tests.test_internship_student import IST, TID, _mk_batch, _record, _student


def _linked_student_headers(student_id, student_no):
    """Exercise the real module gate and stable account link used by the catalog."""
    with get_sessionmaker()() as db:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code="catalog-fixture", school_name="虚构目录验收学校", status="ACTIVE"))
        config = db.scalar(select(PlatformConfig).where(PlatformConfig.tenant_id == TID,
            PlatformConfig.config_type == "FEATURES", PlatformConfig.config_key == "-"))
        if config is None:
            config = PlatformConfig(tenant_id=TID, config_type="FEATURES", config_key="-", enabled=True, status="ACTIVE")
            db.add(config)
        config.config_json = {**(config.config_json or {}), "internship": True}
        account = User(tenant_id=TID, login_name=student_no, real_name="目录测试学生",
                       user_type="STUDENT", password_hash="unused-test-account", status="ACTIVE")
        role = Role(tenant_id=TID, role_code="STUDENT", role_name="学生", status="ACTIVE")
        db.add_all([account, role]); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE"))
        db.add(StudentAccountLink(tenant_id=TID, user_id=account.id, student_id=int(student_id), link_status="ACTIVE"))
        db.commit(); user_id = account.id
        tenant_code = db.get(Tenant, TID).tenant_code
    token = create_access_token({"userId": f"db-{user_id}", "userType": "STUDENT",
                                 "tenantId": str(TID), "tid": tenant_code,
                                 "studentNo": student_no, "currentRoleCode": "STUDENT"})
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.parametrize("prefix", ["/api/v1/portal/internship", "/api/v1/mobile/internship"])
def test_catalog_preparation_open_closed_and_wrong_batch(client, auth_headers, db_mode, prefix):
    student_no = "CATALOG-" + uuid.uuid4().hex[:10]
    sid = _student(client, auth_headers, student_no)
    rid = _record(client, auth_headers, sid)
    record = client.get(f"{IST}/{rid}", headers=auth_headers).json()["data"]
    own = {**_linked_student_headers(sid, student_no), "X-Internship-Batch-Id": record["batchId"]}
    response = client.get(prefix + "/catalog/context", headers=own)
    assert response.status_code == 200, response.json()
    empty = response.json()["data"]
    assert empty["catalogState"] == "NO_OPEN_CAMPAIGN" and empty["canSelect"] is False
    assert "stats" not in empty and "campaignId" not in empty

    wrong = client.get(prefix + "/catalog/context", headers={**own, "X-Internship-Batch-Id": "99999999"})
    assert wrong.status_code == 404
    assert (wrong.json().get("data") or {}).get("catalogState") != "NO_OPEN_CAMPAIGN"

    with get_sessionmaker()() as db:
        row = db.get(InternshipRecord, int(rid))
        campaign = InternshipRecruitmentCampaign(
            tenant_id=row.tenant_id, batch_id=row.batch_id, campaign_code=uuid.uuid4().hex,
            campaign_name="虚构选岗入口验收", status="OPEN", round_no=1,
            student_select_start_at=datetime.utcnow() - timedelta(days=1),
            student_select_end_at=datetime.utcnow() + timedelta(days=1))
        db.add(campaign); db.commit(); campaign_id = campaign.id
    available = client.get(prefix + "/catalog/context", headers=own)
    assert available.status_code == 200
    assert available.json()["data"]["catalogState"] == "AVAILABLE"
    assert available.json()["data"]["campaignId"] == str(campaign_id)
    with get_sessionmaker()() as db:
        campaign = db.get(InternshipRecruitmentCampaign, campaign_id)
        campaign.status = "CLOSED"; db.commit()
    closed = client.get(prefix + "/catalog/context", headers=own)
    assert closed.status_code == 200
    assert closed.json()["data"]["catalogState"] == "NO_OPEN_CAMPAIGN"


def test_campaign_local_window_roundtrip_and_partial_edit(client, auth_headers, db_mode):
    batch_id = _mk_batch(client, auth_headers)
    root = "/api/v1/internship/recruitment-campaigns"
    response = client.post(root, headers=auth_headers, json={
        "batchId": batch_id, "campaignCode": uuid.uuid4().hex, "campaignName": "虚构时区验收",
        "inviteStartAt": "2026-09-06T00:00:00+08:00", "inviteEndAt": "2026-09-06T23:59:59+08:00",
        "enterpriseAccessEndAt": "2026-09-07T23:59:59+08:00",
    })
    assert response.status_code == 200, response.json()
    campaign = response.json()["data"]
    assert campaign["inviteStartAt"].startswith("2026-09-05T16:00:00")
    assert campaign["inviteEndAt"].startswith("2026-09-06T15:59:59")
    edited = client.put(f"{root}/{campaign['id']}", headers=auth_headers, json={
        "expectedVersion": campaign["version"], "inviteStartAt": "2026-09-06T09:00:00+08:00",
    })
    assert edited.status_code == 200, edited.json()
    assert edited.json()["data"]["inviteStartAt"].startswith("2026-09-06T01:00:00")
    with get_sessionmaker()() as db:
        saved = db.get(InternshipRecruitmentCampaign, int(campaign["id"]))
        assert saved.invite_start_at == datetime(2026, 9, 6, 1, 0)
        assert saved.invite_end_at == datetime(2026, 9, 6, 15, 59, 59)


def test_campaign_settings_material_roundtrip_conflict_and_readonly(client, auth_headers, db_mode):
    from app.modules.internship.services.internship_application_material_snapshot_service import evaluate_material_readiness
    root = "/api/v1/internship/recruitment-campaigns"
    policy = {
        "schemaVersion": "V1", "profileRequired": True, "requiredSections": ["SELF_INTRO", "SKILLS"],
        "requiredItemTypes": ["CERTIFICATE"], "applicationStatementRequired": True,
        "minStatementLength": 30, "resumePdfEnabled": False, "allowedContactSharingModes": ["MASKED_ONLY"],
    }
    created = client.post(root, headers=auth_headers, json={
        "batchId": _mk_batch(client, auth_headers), "campaignCode": uuid.uuid4().hex,
        "campaignName": "虚构完整设置验收", "applicationMaterialPolicy": policy,
        "enterpriseConfirmRequired": True, "teacherConfirmSlaHours": 24,
    })
    assert created.status_code == 200, created.json()
    draft = created.json()["data"]
    assert draft["status"] == "DRAFT" and draft["inviteStartAt"] is None
    assert draft["applicationMaterialPolicy"] == policy
    assert draft["enterpriseConfirmRequired"] is True and draft["teacherConfirmSlaHours"] == 24
    assert evaluate_material_readiness({}, draft["applicationMaterialPolicy"])["ready"] is False
    updated = client.put(f"{root}/{draft['id']}", headers=auth_headers, json={
        "expectedVersion": draft["version"], "campaignName": "虚构修改草稿",
        "applicationMaterialPolicy": {**policy, "minStatementLength": 60}, "teacherConfirmSlaHours": 72,
    })
    assert updated.status_code == 200, updated.json()
    current = updated.json()["data"]
    stale = client.put(f"{root}/{draft['id']}", headers=auth_headers, json={
        "expectedVersion": draft["version"], "campaignName": "不应覆盖",
    })
    assert stale.status_code == 409, stale.json()
    reread = client.get(f"{root}/{draft['id']}", headers=auth_headers).json()["data"]
    assert reread["campaignName"] == "虚构修改草稿"
    assert reread["applicationMaterialPolicy"]["minStatementLength"] == 60
    with get_sessionmaker()() as db:
        saved = db.get(InternshipRecruitmentCampaign, int(draft["id"]))
        assert saved.teacher_confirm_sla_hours == 72 and saved.enterprise_confirm_required is True
        # Existing legacy rules are intentionally omitted from an unrelated draft edit.
        saved.application_material_policy_json = {"requiredProfileFields": ["headline"], "minItemCount": 2}
        db.commit()
    preserved = client.put(f"{root}/{draft['id']}", headers=auth_headers, json={
        "expectedVersion": current["version"], "remark": "虚构备注修改",
    })
    assert preserved.status_code == 200, preserved.json()
    assert preserved.json()["data"]["applicationMaterialPolicy"]["minItemCount"] == 2
    with get_sessionmaker()() as db:
        saved = db.get(InternshipRecruitmentCampaign, int(draft["id"]))
        saved.status = "OPEN"; db.commit()
    forbidden = client.put(f"{root}/{draft['id']}", headers=auth_headers, json={
        "expectedVersion": preserved.json()["data"]["version"], "campaignName": "已开启不应修改",
    })
    assert forbidden.status_code == 409, forbidden.json()
    assert client.get(f"{root}/{draft['id']}", headers=auth_headers).json()["data"]["campaignName"] == "虚构修改草稿"
