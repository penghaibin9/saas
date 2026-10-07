"""SP06/SP07 procurement fields tested through real student/admin APIs and MySQL.
Synthetic pre-existing internship facts are fixtures, not a claim of whole-lifecycle acceptance.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.field_crypto import encrypt_sensitive
from app.db.session import get_sessionmaker
from app.main import app
from app.models import (
    College, Major, SchoolClass, StudentProfile, StudentContact, User,
    InternshipRecord, InternshipEnterpriseContact, InternshipEnterpriseEval,
    InternshipCheckin, InternshipMakeup, WeeklyReport, InternshipProcessReport,
    InternshipFormalDocument,
)
from test_standalone_browser_auth_mysql import _login, TENANT_ID, STAFF_ID
from test_yiyang_gap09_minimum_age_mysql import admin, scenario, STUDENT_PASSWORD

PORTAL = "/api/v1/portal/internship/context/formal-documents"
STAFF = "/api/v1/internship/formal-documents"


@pytest.fixture
def finished(scenario):
    s = scenario(years=20, legacy_assigned=True)
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, int(s["id"]))
        student = db.get(StudentProfile, int(s["studentId"]))
        college = College(tenant_id=TENANT_ID, college_name="工程学院", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(tenant_id=TENANT_ID, college_id=college.id, major_name="机电一体化", status="ACTIVE")
        db.add(major); db.flush()
        group = SchoolClass(tenant_id=TENANT_ID, major_id=major.id, class_name="机电2401", grade="2024", status="ACTIVE", class_status="NORMAL")
        db.add(group); db.flush()
        # Class is the canonical organizational link; no fake duplicate college/major facts.
        student.class_id = group.id
        student.college_id = student.major_id = None
        student.grade, student.gender = "2024", "FEMALE"
        student.real_name = "文书验收学生"
        db.add(StudentContact(tenant_id=TENANT_ID, student_id=student.id, contact_type="PHONE",
               contact_value_encrypted=encrypt_sensitive("13900000001", "phone"), is_primary=True))
        db.get(User, STAFF_ID).phone_encrypted = encrypt_sensitive("13900000002", "phone")
        mentor = InternshipEnterpriseContact(tenant_id=TENANT_ID, company_id=record.enterprise_id,
                    name="企业导师甲", contact_type="MENTOR", status="ACTIVE",
                    phone_encrypted=encrypt_sensitive("13900000003", "phone"))
        db.add(mentor); db.flush()
        record.status = "ASSESSING"
        record.enterprise_name, record.position_name = "实习验收企业", "设备运维实习生"
        record.advisor_user_id, record.advisor_name = STAFF_ID, "校内导师甲"
        record.mentor_contact_id, record.enterprise_mentor_name = mentor.id, mentor.name
        record.intern_start_date, record.intern_end_date = datetime(2026, 9, 1), datetime(2026, 9, 30)
        evaluation = InternshipEnterpriseEval(tenant_id=TENANT_ID, internship_id=record.id,
            student_id=student.id, batch_id=record.batch_id, enterprise_id=record.enterprise_id,
            position_id=record.position_id, enterprise_contact_id=mentor.id, mentor_name=mentor.name,
            attendance_score=90, skill_score=90, attitude_score=90, collaboration_score=90, safety_score=90,
            overall_comment="能独立完成岗位任务，表现良好。", source_type="SCHOOL_RECORDED",
            submit_status="SUBMITTED", school_review_status="APPROVED", reviewed_by_name="校内导师甲",
            reviewed_at=datetime(2026, 9, 30, 10))
        db.add(evaluation)
        for day, result, deleted in [("2026-09-01", "NORMAL", False), ("2026-09-02", "NORMAL", False),
             ("2026-09-03", "MOCK_LOCATION", False), ("2026-09-04", "OUT_OF_RANGE", False),
             ("2026-08-31", "NORMAL", False), ("2026-10-01", "NORMAL", False),
             ("2026-09-06", "NORMAL", True), ("2026-09-07", "RECORDED", False)]:
            db.add(InternshipCheckin(tenant_id=TENANT_ID, internship_id=record.id, checkin_date=day,
                                    result=result, is_deleted=deleted))
        for day, status in [("2026-09-02", "APPROVED"), ("2026-09-05", "APPROVED"),
                            ("2026-09-05", "APPROVED"), ("2026-09-06", "REJECTED")]:
            db.add(InternshipMakeup(tenant_id=TENANT_ID, internship_id=record.id, student_id=student.id,
                                   checkin_date=day, status=status, reason="验收补签事实"))
        for week, state, submitted in [(1, "APPROVED", True), (2, "RETURNED", True), (3, "DRAFT", False)]:
            db.add(WeeklyReport(tenant_id=TENANT_ID, internship_id=record.id, week_number=week,
                work_content="验收周报", status=state, report_version=4 if week == 1 else 1,
                submitted_at=datetime(2026, 9, 20) if submitted else None))
        for typ, period, state, submitted, deleted in [
            ("DAILY", "2026-09-01", "APPROVED", True, False),
            ("DAILY", "2026-09-02", "PENDING_REVIEW", True, False),
            ("DAILY", "2026-09-03", "DRAFT", False, False),
            ("DAILY", "2026-09-04", "APPROVED", True, True),
            ("MONTHLY", "2026-09", "APPROVED", True, False),
            ("SUMMARY", "FINAL", "APPROVED", True, False)]:
            db.add(InternshipProcessReport(tenant_id=TENANT_ID, internship_id=record.id,
                report_type=typ, period_key=period, content="验收报告正文", status=state, is_deleted=deleted,
                submitted_at=datetime(2026, 9, 30) if submitted else None))
        db.commit()
        s["evaluationId"], s["mentorId"] = evaluation.id, mentor.id
    return s


def own_client(s):
    client = TestClient(app)
    response = _login(client, login_name=s["login"], password=STUDENT_PASSWORD,
                      client_type="STUDENT_PC", session_id="sp06-" + s["id"])
    assert response.status_code == 200, response.text
    client.headers.update({"Authorization": "Bearer " + response.json()["data"]["accessToken"]})
    return client


def generate(client, s, document_type="ENTERPRISE_EVALUATION"):
    response = client.post(PORTAL + "/generate", json={"batchId": s["batchId"], "internshipId": s["id"], "documentType": document_type})
    assert response.status_code == 200 and response.json()["code"] == 0, response.text
    return response.json()["data"]


def snapshot(meta):
    with get_sessionmaker()() as db:
        return db.get(InternshipFormalDocument, int(meta["id"])).source_snapshot_json


def pdf(client, s, doc):
    response = client.get(f"{PORTAL}/{doc['id']}/pdf", params={"batchId": s["batchId"], "internshipId": s["id"]})
    assert response.status_code == 200 and response.json()["code"] == 0, response.text
    content = base64.b64decode(response.json()["data"]["contentBase64"])
    assert content.startswith(b"%PDF") and len(content) > 1000
    return content


def test_sp06_all_required_fields_and_encrypted_contact_snapshots(finished):
    with own_client(finished) as client:
        doc = generate(client, finished)
        data = snapshot(doc)
        assert data["schemaVersion"] >= 2
        assert data["student"]["gender"] == "女"
        assert data["student"]["collegeName"] == "工程学院"
        assert data["student"]["majorName"] == "机电一体化"
        assert data["contacts"]["student"]["phoneEncrypted"]
        assert data["contacts"]["advisor"]["phoneEncrypted"]
        assert data["contacts"]["enterpriseMentor"]["phoneEncrypted"]
        assert data["enterpriseEvaluation"]["gradeLevel"] == "优秀"
        assert data["processFacts"]["reports"] == {"DAILY": 2, "WEEKLY": 2, "MONTHLY": 1, "SUMMARY": 1}
        for value in ("13900000001", "13900000002", "13900000003"):
            assert value not in json.dumps(data, ensure_ascii=False)
            assert value not in json.dumps(doc, ensure_ascii=False)
        pdf(client, finished, doc)


def test_sp07_distinct_verified_attendance_within_record_period(finished):
    with own_client(finished) as client:
        doc = generate(client, finished, "INTERNSHIP_CERTIFICATE")
        data = snapshot(doc)
        # NORMAL/RECORDED 9/1, 9/2, 9/7 plus approved 9/5; duplicates and abnormal/outside dates do not count.
        assert data["completion"]["attendanceDays"] == 4
        assert data["completion"]["checkinDays"] == 3
        assert data["completion"]["makeupDays"] == 2
        pdf(client, finished, doc)


def test_same_source_reused_source_change_creates_new_immutable_version(admin, finished):
    with own_client(finished) as client:
        first = generate(client, finished)
        first_pdf = pdf(client, finished, first)
        again = generate(client, finished)
        assert again["reused"] is True and again["id"] == first["id"]
        response = admin.post(STAFF + "/generate", json={"internshipId": finished["id"], "documentType": "ENTERPRISE_EVALUATION"})
        assert response.json()["code"] == 0, response.text
        assert response.json()["data"]["id"] == first["id"]
        with get_sessionmaker()() as db:
            row = db.get(InternshipEnterpriseContact, finished["mentorId"])
            row.phone_encrypted = encrypt_sensitive("13900000009", "phone")
            db.commit()
        newer = generate(client, finished)
        assert newer["documentVersion"] == first["documentVersion"] + 1
        assert newer["sourceHash"] != first["sourceHash"]
        assert pdf(client, finished, first) == first_pdf
        assert pdf(client, finished, newer) != first_pdf


def test_own_document_rejects_wrong_batch_and_other_student(finished, scenario):
    with own_client(finished) as client:
        doc = generate(client, finished)
        invalid = client.get(f"{PORTAL}/{doc['id']}/pdf", params={"batchId": "999999", "internshipId": finished["id"]})
        assert invalid.json()["code"] != 0
    other = scenario(years=20)
    with own_client(other) as client:
        denied = client.get(f"{PORTAL}/{doc['id']}/pdf", params={"batchId": other["batchId"], "internshipId": other["id"]})
        assert denied.json()["code"] != 0


def test_unapproved_evaluation_cannot_generate_formal_appraisal(finished):
    with get_sessionmaker()() as db:
        db.get(InternshipEnterpriseEval, finished["evaluationId"]).school_review_status = "RETURNED"
        db.commit()
    with own_client(finished) as client:
        response = client.post(PORTAL + "/generate", json={"batchId": finished["batchId"], "internshipId": finished["id"], "documentType": "ENTERPRISE_EVALUATION"})
        assert response.json()["code"] != 0


def test_first_student_and_staff_generation_share_one_version(admin, finished):
    from concurrent.futures import ThreadPoolExecutor
    with own_client(finished) as student:
        body = {"batchId": finished["batchId"], "internshipId": finished["id"], "documentType": "ENTERPRISE_EVALUATION"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(client.post, url, json=body) for client, url in
                       [(student, PORTAL + "/generate"), (admin, STAFF + "/generate")] * 2]
            responses = [future.result(timeout=20) for future in futures]
        for response in responses:
            assert response.status_code == 200 and response.json()["code"] == 0, response.text
        assert len({response.json()["data"]["id"] for response in responses}) == 1
        assert {response.json()["data"]["documentVersion"] for response in responses} == {1}


def test_wrong_company_mentor_is_not_exported_and_missing_phone_is_explicit(admin, finished):
    with get_sessionmaker()() as db:
        mentor = db.get(InternshipEnterpriseContact, finished["mentorId"])
        mentor.company_id += 999999
        db.commit()
    with own_client(finished) as student:
        data = snapshot(generate(student, finished))
        assert data["contacts"]["enterpriseMentor"]["phoneEncrypted"] == ""
        assert "企业导师联系电话" in data["missingFields"]
    response = admin.get(f"{STAFF}/by-internship/{finished['id']}/readiness")
    assert response.json()["code"] == 0, response.text
    item = next(x for x in response.json()["data"]["items"] if x["documentType"] == "ENTERPRISE_EVALUATION")
    assert "企业导师联系电话" in item["missingFields"]


def test_login_alias_not_student_number_still_resolves_owned_document(finished):
    with get_sessionmaker()() as db:
        account = db.scalar(select(User).where(User.tenant_id == TENANT_ID, User.login_name == finished['login']))
        account.login_name = 'alias-' + finished['login']
        finished['login'] = account.login_name
        db.commit()
    with own_client(finished) as client:
        assert snapshot(generate(client, finished))['student']['id'] == finished['studentId']


def test_revoked_account_link_cannot_keep_downloading_student_documents(finished):
    from app.models import StudentAccountLink
    with own_client(finished) as client:
        doc = generate(client, finished)
        with get_sessionmaker()() as db:
            link = db.scalar(select(StudentAccountLink).where(StudentAccountLink.tenant_id == TENANT_ID,
                             StudentAccountLink.student_id == int(finished['studentId'])))
            link.link_status = 'REVOKED'
            db.commit()
        denied = client.get(f"{PORTAL}/{doc['id']}/pdf", params={'batchId': finished['batchId'], 'internshipId': finished['id']})
        assert denied.json()['code'] != 0
        assert 'contentBase64' not in denied.text
