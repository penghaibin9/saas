"""Opt-in, isolated MySQL/API acceptance for the non-waivable age gate.
Run with APP_ENV=test, GAP09_MYSQL_ACCEPTANCE=1 and a dedicated *_test / *_ci / *gap09 DB.
All users are test accounts; normal login/RBAC and production routers are used unchanged.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.main import app
from app.models import (
    EmpCompany, InternshipBatch, InternshipRecord, InternshipPosition,
    InternshipComplianceExemption, InternshipAuditTrail, StudentProfile,
    StudentAccountLink, User, UserRole,
)
from test_standalone_browser_auth_mysql import _seed, _login, TENANT_ID, STUDENT_ROLE_ID
from test_yiyang_gap09_minimum_age import encrypted_student

IST = "/api/v1/internship/intern-students"
CMP = "/api/v1/internship/compliance"
STUDENT_PASSWORD = "Gap09-Isolated-Student-2026!"


@pytest.fixture(scope="module")
def admin():
    if os.environ.get("GAP09_MYSQL_ACCEPTANCE") != "1":
        pytest.skip("requires explicit isolated MySQL acceptance opt-in")
    url = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == "test"
    assert url.get_backend_name() == "mysql"
    assert any(x in (url.database or "").lower() for x in ("gap09", "_test", "_ci"))
    _seed()
    with TestClient(app) as client:
        response = _login(client, login_name="auth.staff", password="Staff-Evidence-2026!",
                          client_type="PC", session_id="gap09-admin")
        assert response.status_code == 200, response.text
        token = response.json()["data"]["accessToken"]
        client.headers.update({"Authorization": "Bearer " + token})
        yield client


@pytest.fixture
def scenario(admin):
    def create(*, years=15, legacy_assigned=False, guardian_required=False, unknown=False):
        suffix = uuid.uuid4().hex[:10]
        today = date.today()
        birth = date(today.year - years, 1, 1)
        rules = {name: {"required": False} for name in (
            "enterpriseAccess", "safetyEducation", "insurance", "agreement", "advisor",
            "specialFiling", "emergency", "workRights",
        )}
        rules["studentConsent"] = {"required": False, "requireGuardianConsentForMinor": guardian_required}
        rules["guardianConsent"] = {"required": guardian_required, "severity": "BLOCK"}
        rules["workRights"].update({"requireEnterpriseAccess": False})
        rules["minimumAge"] = {"required": False, "severity": "WARN"}
        with get_sessionmaker()() as db:
            student = StudentProfile(
                tenant_id=TENANT_ID, student_no="g09-" + suffix, real_name="年龄门禁验收学生",
                current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE",
                id_card_encrypted=None if unknown else encrypted_student(birth).id_card_encrypted,
            )
            user = User(tenant_id=TENANT_ID, login_name="g09-" + suffix, real_name=student.real_name,
                        password_hash=hash_password(STUDENT_PASSWORD), user_type="STUDENT", status="ACTIVE",
                        credential_version=0, must_change_password=False)
            company = EmpCompany(tenant_id=TENANT_ID, name="年龄门禁验收企业-" + suffix,
                                 coop_status="ACTIVE", qualification_status="PASSED", status="ACTIVE", blacklist=False)
            batch = InternshipBatch(tenant_id=TENANT_ID, batch_name="年龄门禁-" + suffix,
                                    batch_no="G09-" + suffix, status="RUNNING", rules_version=1,
                                    start_date=datetime(today.year, 1, 1),
                                    end_date=datetime(today.year + 1, 1, 1), rules_config={"compliance": rules})
            db.add_all([student, user, company, batch]); db.flush()
            pos = InternshipPosition(
                tenant_id=TENANT_ID, company_id=company.id, batch_id=batch.id,
                title="测试实习岗位", status="PUBLISHED", work_content="课程实习训练与记录",
                work_location="测试园区", work_address="测试园区", daily_hours=8, weekly_hours=40,
                night_shift=False, overtime_allowed=False, rest_days_per_week=2,
                remuneration_type="MONTHLY", remuneration_amount=3000, remuneration_cycle="MONTHLY",
                accommodation_provided=False, meal_provided=True, hazardous_flag=False,
                headcount=10, allocated_count=1 if legacy_assigned else 0,
            )
            db.add(pos); db.flush()
            record = InternshipRecord(
                tenant_id=TENANT_ID, student_id=student.id, batch_id=batch.id,
                eligibility_status="QUALIFIED", status="READY",
                destination_type="ASSIGNED" if legacy_assigned else "NONE",
                enterprise_id=company.id if legacy_assigned else None,
                position_id=pos.id if legacy_assigned else None,
            )
            db.add_all([record, UserRole(tenant_id=TENANT_ID, user_id=user.id,
                        role_id=STUDENT_ROLE_ID, status="ACTIVE"),
                        StudentAccountLink(tenant_id=TENANT_ID, student_id=student.id, user_id=user.id,
                        link_status="ACTIVE", source="IDENTITY_IMPORT", bound_login_name=user.login_name,
                        bound_student_no=student.student_no)])
            db.commit()
            return {"id": str(record.id), "studentId": str(student.id), "batchId": str(batch.id),
                    "positionId": str(pos.id), "login": user.login_name, "version": int(record.version or 0)}
    return create


def age_item(result):
    return next(x for x in result["items"] if x["code"] == "minimumAge")


def read_record(record_id):
    with get_sessionmaker()() as db:
        row = db.get(InternshipRecord, int(record_id))
        return row.status, int(row.version or 0), row.position_id


def test_under16_assignment_rejected_and_capacity_unchanged(admin, scenario):
    s = scenario()
    response = admin.post(f"{IST}/{s['id']}/assign", json={"positionId": s["positionId"], "expectedVersion": s["version"]})
    assert response.json()["code"] != 0, response.text
    assert "16" in response.text, response.text
    assert read_record(s["id"]) == ("READY", s["version"], None)
    with get_sessionmaker()() as db:
        assert db.get(InternshipPosition, int(s["positionId"])).allocated_count == 0


@pytest.mark.parametrize("unknown", [False, True])
def test_legacy_assignment_cannot_onboard_and_student_sees_same_blocker(admin, scenario, unknown):
    s = scenario(legacy_assigned=True, unknown=unknown)
    evaluated = admin.get(f"{CMP}/evaluate/{s['id']}")
    assert evaluated.status_code == 200, evaluated.text
    server_age = age_item(evaluated.json()["data"])
    assert server_age["status"] == ("PENDING" if unknown else "REJECTED")
    before = read_record(s["id"])
    response = admin.post(f"{IST}/{s['id']}/status", json={"action": "ONBOARD", "expectedVersion": s["version"]})
    assert response.json()["code"] != 0, response.text
    assert read_record(s["id"]) == before
    with TestClient(app) as student:
        logged = _login(student, login_name=s["login"], password=STUDENT_PASSWORD,
                        client_type="STUDENT_PC", session_id="g09-" + s["id"])
        assert logged.status_code == 200, logged.text
        headers = {"Authorization": "Bearer " + logged.json()["data"]["accessToken"]}
        result = student.get("/api/v1/mobile/internship/compliance/my", headers=headers,
                             params={"batchId": s["batchId"]})
        assert result.status_code == 200, result.text
        assert age_item(result.json()["data"])["status"] == server_age["status"]
        denied = student.post(f"{CMP}/exemptions", headers=headers,
                              json={"internshipId": s["id"], "checkCode": "minimumAge"})
        assert denied.status_code == 403, denied.text


def test_legacy_approved_age_waiver_invalidates_instead_of_bypassing_gate(admin, scenario):
    s = scenario(legacy_assigned=True)
    with get_sessionmaker()() as db:
        exemption = InternshipComplianceExemption(tenant_id=TENANT_ID, internship_id=int(s["id"]),
            batch_id=int(s["batchId"]), check_code="minimumAge", reason="模拟迁移前已批准的历史年龄豁免",
            status="APPROVED", valid_until=datetime.utcnow() + timedelta(days=3))
        db.add(exemption); db.commit(); eid = exemption.id
    result = admin.get(f"{CMP}/evaluate/{s['id']}")
    assert result.status_code == 200, result.text
    assert age_item(result.json()["data"])["status"] == "REJECTED"
    assert result.json()["data"]["passed"] is False
    with get_sessionmaker()() as db:
        assert db.get(InternshipComplianceExemption, eid).status == "INVALIDATED"
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_id == int(s["id"]),
            InternshipAuditTrail.action == "INVALIDATE")) >= 1


def test_new_age_request_denied_and_legacy_pending_can_only_be_rejected(admin, scenario):
    s = scenario()
    denied = admin.post(f"{CMP}/exemptions", json={"internshipId": s["id"],
                        "checkCode": "minimumAge", "reason": "测试年龄不能通过豁免绕过"})
    assert denied.json()["code"] != 0 and "不可豁免" in denied.text
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipComplianceExemption).where(
            InternshipComplianceExemption.internship_id == int(s["id"]))) == 0
        row = InternshipComplianceExemption(tenant_id=TENANT_ID, internship_id=int(s["id"]),
              batch_id=int(s["batchId"]), check_code="minimumAge", reason="模拟旧版本遗留待审核申请",
              status="PENDING_REVIEW", valid_until=datetime.utcnow() + timedelta(days=3))
        db.add(row); db.commit(); eid, version = row.id, int(row.version or 0)
    response = admin.post(f"{CMP}/exemptions/{eid}/review", json={"action": "APPROVE", "expectedVersion": version})
    assert response.json()["code"] != 0 and "不可豁免" in response.text
    with get_sessionmaker()() as db:
        assert db.get(InternshipComplianceExemption, eid).status == "PENDING_REVIEW"
        assert db.get(InternshipComplianceExemption, eid).version == version
    rejected = admin.post(f"{CMP}/exemptions/{eid}/review", json={"action": "REJECT", "expectedVersion": version,
                          "comment": "年龄条件不可豁免，请核实主档"})
    assert rejected.json()["code"] == 0, rejected.text
    assert rejected.json()["data"]["status"] == "REJECTED"


def test_valid_adult_still_assigns_onboards_and_is_readable_after_commit(admin, scenario):
    s = scenario(years=20)
    assigned = admin.post(f"{IST}/{s['id']}/assign", json={"positionId": s["positionId"], "expectedVersion": s["version"]})
    assert assigned.json()["code"] == 0, assigned.text
    version = read_record(s["id"])[1]
    result = admin.post(f"{IST}/{s['id']}/status", json={"action": "ONBOARD", "expectedVersion": version})
    assert result.json()["code"] == 0, result.text
    assert read_record(s["id"])[0] == "ONBOARD"
    again = admin.get(f"{IST}/{s['id']}")
    assert again.json()["code"] == 0, again.text
    assert again.json()["data"]["status"] == "ONBOARD"
