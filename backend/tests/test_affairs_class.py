"""13A-B2 班级与辅导员 · 端到端（真实 MySQL 模式）。

班级列表(名称+指标+筛选)/班级画像(聚合)/班级学生(脱敏)/班级材料(CRUD+附件校验+越权)/
辅导员考评(周期→自动指标→评分→排名→发布)。
"""
from __future__ import annotations

TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """学院/专业 + 2 班（各设不同辅导员 user_id）+ 3 学生 + counselor01 限 A 班范围。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    maj = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(maj); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="软件2101", grade="2021",
                    counselor_id=999001, status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="软件2102", grade="2021",
                    counselor_id=999002, status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    for no, name, cid, gender in [
        ("A001", "甲一", a.id, "男"),
        ("A002", "甲二", a.id, "女"),
        ("B001", "乙一", b.id, "男"),
    ]:
        db.add(StudentProfile(
            tenant_id=TID, student_no=no, real_name=name, class_id=cid, gender=gender,
            current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE",
        ))
    db.add(TeacherStudentScope(
        tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
        role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101", status="ACTIVE",
    ))
    db.commit()
    ids = {"A": a.id, "B": b.id, "col": col.id, "maj": maj.id}
    db.close()
    return ids


def test_c1_class_list_metrics(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    result = client.get("/api/v1/student-affairs/classes", headers=hdr).json()
    assert result["code"] == 0 and result["data"]["total"] == 2
    row = next(item for item in result["data"]["items"] if item["classId"] == str(ids["A"]))
    assert row["className"] == "软件2101" and row["majorName"] == "软件技术"
    assert row["collegeName"] == "软件学院" and row["studentCount"] == 2


def test_c2_class_list_filters(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    keyword = client.get("/api/v1/student-affairs/classes?keyword=2101", headers=hdr).json()
    assert keyword["data"]["total"] == 1
    assert keyword["data"]["items"][0]["classId"] == str(ids["A"])
    college = client.get(
        f"/api/v1/student-affairs/classes?collegeId={ids['col']}", headers=hdr,
    ).json()
    assert college["data"]["total"] == 2
    grade = client.get("/api/v1/student-affairs/classes?grade=2099", headers=hdr).json()
    assert grade["data"]["total"] == 0


def test_c3_class_profile(client, db_mode):
    ids = _seed(db_mode)
    result = client.get(
        f"/api/v1/student-affairs/classes/{ids['A']}/profile",
        headers=_hdr(client, "school_admin01"),
    ).json()
    assert result["code"] == 0
    metrics = {item["key"]: item["value"] for item in result["data"]["metrics"]}
    assert metrics["studentCount"] == 2 and metrics["male"] == 1 and metrics["female"] == 1


def test_c4_class_students_masked(client, db_mode):
    ids = _seed(db_mode)
    result = client.get(
        f"/api/v1/student-affairs/classes/{ids['A']}/students",
        headers=_hdr(client, "school_admin01"),
    ).json()
    assert result["data"]["total"] == 2
    assert "phoneMasked" in result["data"]["items"][0]


def test_c5_class_profile_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    response = client.get(
        f"/api/v1/student-affairs/classes/{ids['B']}/profile",
        headers=_hdr(client, "counselor01"),
    )
    assert response.status_code == 403 and response.json()["bizCode"] == "NO_DATA_SCOPE"


def test_c6_material_crud(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    assert client.post(
        f"/api/v1/student-affairs/classes/{ids['A']}/materials",
        headers=hdr,
        json={"materialType": "BAD", "title": "x"},
    ).status_code == 400
    created = client.post(
        f"/api/v1/student-affairs/classes/{ids['A']}/materials",
        headers=hdr,
        json={
            "materialType": "CLASS_MEETING", "title": "第3周主题班会记录",
            "materialAt": "2026-03-10", "remark": "全员到齐",
        },
    ).json()
    assert created["code"] == 0
    material_id = created["data"]["id"]
    assert created["data"]["materialTypeLabel"] == "班会记录"
    listed = client.get(
        f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr,
    ).json()
    assert listed["data"]["total"] == 1
    assert client.delete(
        f"/api/v1/student-affairs/classes/materials/{material_id}", headers=hdr,
    ).json()["code"] == 0
    listed_after = client.get(
        f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr,
    ).json()
    assert listed_after["data"]["total"] == 0


def test_c7_material_invalid_file(client, db_mode):
    ids = _seed(db_mode)
    response = client.post(
        f"/api/v1/student-affairs/classes/{ids['A']}/materials",
        headers=_hdr(client, "school_admin01"),
        json={"materialType": "OTHER", "title": "带附件", "fileId": "f-nonexistent"},
    )
    assert response.status_code == 400


def test_c8_material_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    response = client.post(
        f"/api/v1/student-affairs/classes/{ids['B']}/materials",
        headers=_hdr(client, "counselor01"),
        json={"materialType": "OTHER", "title": "越权材料"},
    )
    assert response.status_code == 403 and response.json()["bizCode"] == "NO_DATA_SCOPE"


def test_c9_counselor_assessment_flow(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    period_response = client.post(
        "/api/v1/student-affairs/counselor-assessment/periods",
        headers=hdr,
        json={"periodName": "2025-2026上 辅导员考评", "semester": "2025-1"},
    ).json()
    assert period_response["code"] == 0
    period_id = period_response["data"]["id"]

    collected = client.post(
        f"/api/v1/student-affairs/counselor-assessment/periods/{period_id}/collect",
        headers=hdr,
    ).json()
    assert collected["data"]["counselors"] == 2

    items = client.get(
        f"/api/v1/student-affairs/counselor-assessment/periods/{period_id}/assessments",
        headers=hdr,
    ).json()["data"]["items"]
    assert len(items) == 2
    first = next(item for item in items if item["counselorId"] == "999001")
    second = next(item for item in items if item["counselorId"] == "999002")
    assert first["classCount"] == 1 and first["studentCount"] == 2
    assert first["autoScore"] is not None

    first_score_response = client.post(
        f"/api/v1/student-affairs/counselor-assessment/assessments/{first['id']}/score",
        headers=hdr,
        json={"collegeScore": 92, "version": first["version"]},
    ).json()
    assert first_score_response["code"] == 0, first_score_response
    first_scored = first_score_response["data"]
    assert first_scored["status"] == "SCORED" and first_scored["totalScore"] is not None

    second_score_response = client.post(
        f"/api/v1/student-affairs/counselor-assessment/assessments/{second['id']}/score",
        headers=hdr,
        json={"collegeScore": 88, "version": second["version"]},
    ).json()
    assert second_score_response["code"] == 0, second_score_response
    second_scored = second_score_response["data"]
    assert second_scored["status"] == "SCORED" and second_scored["totalScore"] is not None
    assert {first_scored["rankNo"], second_scored["rankNo"]} == {1, 2}

    assert client.post(
        f"/api/v1/student-affairs/counselor-assessment/assessments/{first['id']}/score",
        headers=hdr,
        json={"collegeScore": 150, "version": first_scored["version"]},
    ).status_code in (400, 422)

    periods = client.get(
        "/api/v1/student-affairs/counselor-assessment/periods", headers=hdr,
    ).json()["data"]["items"]
    current_period = next(item for item in periods if item["id"] == str(period_id))
    published_response = client.post(
        f"/api/v1/student-affairs/counselor-assessment/periods/{period_id}/publish",
        headers=hdr,
        json={"version": current_period["version"]},
    ).json()
    assert published_response["code"] == 0, published_response
    assert published_response["data"]["status"] == "PUBLISHED"
    assert client.post(
        f"/api/v1/student-affairs/counselor-assessment/periods/{period_id}/collect",
        headers=hdr,
    ).status_code == 409
