"""A3 / P0-05：就业中心正式运行态 dataScope 回归。"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
BASE = "/api/v1/employment"


def _hdr(client, login_name="employment01"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_scoped_rows(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (College, EmpFollowup, EmpMaterial, EmpStudent, Major,
                            SchoolClass, StudentProfile, TeacherStudentScope)

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name="A3就业测试学院", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="A3就业测试专业", status="ACTIVE")
        db.add(major); db.flush()
        allowed_class = SchoolClass(
            tenant_id=TID, major_id=major.id, class_name="A3就业可见班", grade="2026",
            status="ACTIVE", class_status="NORMAL")
        denied_class = SchoolClass(
            tenant_id=TID, major_id=major.id, class_name="A3就业越权班", grade="2026",
            status="ACTIVE", class_status="NORMAL")
        db.add_all([allowed_class, denied_class]); db.flush()

        db.add(TeacherStudentScope(
            tenant_id=TID, teacher_key="employment01", teacher_name="刘芳",
            role_code="EMPLOYMENT_TEACHER", scope_type="CLASS",
            ref_value="A3就业可见班", status="ACTIVE"))

        allowed_profile = StudentProfile(
            tenant_id=TID, student_no="A3EMP0001", real_name="A3可见学生",
            college_id=college.id, major_id=major.id, class_id=allowed_class.id,
            grade="2026", current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        denied_profile = StudentProfile(
            tenant_id=TID, student_no="A3EMP0002", real_name="A3越权学生",
            college_id=college.id, major_id=major.id, class_id=denied_class.id,
            grade="2026", current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add_all([allowed_profile, denied_profile]); db.flush()

        allowed_emp = EmpStudent(
            tenant_id=TID, student_id=allowed_profile.id, student_no=allowed_profile.student_no,
            name=allowed_profile.real_name, college_name=college.college_name,
            major_name=major.major_name, class_id=str(allowed_class.id), class_name=allowed_class.class_name,
            destination_type="UNEMPLOYED", verify_status="PENDING_VERIFY",
            material_status="SUBMITTED", help_level="NORMAL", risk_level="LOW",
            record_status="ACTIVE")
        denied_emp = EmpStudent(
            tenant_id=TID, student_id=denied_profile.id, student_no=denied_profile.student_no,
            name=denied_profile.real_name, college_name=college.college_name,
            major_name=major.major_name, class_id=str(denied_class.id), class_name=denied_class.class_name,
            destination_type="UNEMPLOYED", verify_status="PENDING_VERIFY",
            material_status="SUBMITTED", help_level="NORMAL", risk_level="LOW",
            record_status="ACTIVE")
        db.add_all([allowed_emp, denied_emp]); db.flush()

        allowed_mat = EmpMaterial(
            tenant_id=TID, emp_student_id=allowed_emp.id, material_type="AGREEMENT",
            file_name="A3-visible.pdf", submit_time=datetime.utcnow(), status="SUBMITTED")
        denied_mat = EmpMaterial(
            tenant_id=TID, emp_student_id=denied_emp.id, material_type="AGREEMENT",
            file_name="A3-denied.pdf", submit_time=datetime.utcnow(), status="SUBMITTED")
        allowed_fu = EmpFollowup(
            tenant_id=TID, emp_student_id=allowed_emp.id, follow_time=datetime.utcnow(),
            way="PHONE", content="A3可见跟进", status="OPEN")
        denied_fu = EmpFollowup(
            tenant_id=TID, emp_student_id=denied_emp.id, follow_time=datetime.utcnow(),
            way="PHONE", content="A3越权跟进", status="OPEN")
        db.add_all([allowed_mat, denied_mat, allowed_fu, denied_fu])
        db.commit()
        return {
            "allowed_emp": str(allowed_emp.id), "denied_emp": str(denied_emp.id),
            "allowed_mat": str(allowed_mat.id), "denied_mat": str(denied_mat.id),
        }
    finally:
        db.close()


def test_employment_lists_and_detail_share_same_scope(client, db_mode):
    ids = _seed_scoped_rows(db_mode)
    hdr = _hdr(client)

    students = client.get(f"{BASE}/students?page=1&pageSize=200", headers=hdr).json()["data"]
    student_ids = {str(row["id"]) for row in students["items"]}
    assert ids["allowed_emp"] in student_ids
    assert ids["denied_emp"] not in student_ids

    allowed = client.get(f"{BASE}/students/{ids['allowed_emp']}", headers=hdr)
    assert allowed.status_code == 200 and allowed.json()["code"] == 0
    denied = client.get(f"{BASE}/students/{ids['denied_emp']}", headers=hdr)
    assert denied.status_code == 403 and denied.json()["bizCode"] == "NO_DATA_SCOPE"

    materials = client.get(f"{BASE}/materials?page=1&pageSize=200", headers=hdr).json()["data"]
    material_ids = {str(row["id"]) for row in materials["items"]}
    assert ids["allowed_mat"] in material_ids
    assert ids["denied_mat"] not in material_ids

    followups = client.get(f"{BASE}/followups?page=1&pageSize=200", headers=hdr).json()["data"]
    follow_student_ids = {str(row["studentId"]) for row in followups["items"]}
    assert ids["allowed_emp"] in follow_student_ids
    assert ids["denied_emp"] not in follow_student_ids


def test_employment_write_cannot_target_cross_scope_student(client, db_mode):
    ids = _seed_scoped_rows(db_mode)
    hdr = _hdr(client)
    denied = client.post(
        f"{BASE}/students/mark-destination", headers=hdr,
        json={"ids": [ids["denied_emp"]], "destinationType": "SIGNED"})
    assert denied.status_code == 403 and denied.json()["bizCode"] == "NO_DATA_SCOPE"

    allowed = client.post(
        f"{BASE}/students/mark-destination", headers=hdr,
        json={"ids": [ids["allowed_emp"]], "destinationType": "SIGNED"})
    assert allowed.status_code == 200 and allowed.json()["data"]["count"] == 1


def test_employment_material_detail_cannot_bypass_scope(client, db_mode):
    ids = _seed_scoped_rows(db_mode)
    hdr = _hdr(client)
    visible = client.get(f"{BASE}/materials/{ids['allowed_mat']}", headers=hdr)
    assert visible.status_code == 200 and visible.json()["data"]["material"]["id"] == ids["allowed_mat"]
    hidden = client.get(f"{BASE}/materials/{ids['denied_mat']}", headers=hdr)
    assert hidden.status_code == 403 and hidden.json()["bizCode"] == "NO_DATA_SCOPE"


def test_employment_export_row_count_matches_scoped_student_list(client, db_mode):
    _seed_scoped_rows(db_mode)
    hdr = _hdr(client)
    listed = client.get(f"{BASE}/students?page=1&pageSize=200", headers=hdr).json()["data"]
    exported = client.post(
        "/api/v1/export/domain/employment", headers=hdr,
        json={"purpose": "A3就业范围一致性验收"}).json()
    assert exported["code"] == 0, exported
    assert exported["data"]["rowCount"] == listed["total"]
