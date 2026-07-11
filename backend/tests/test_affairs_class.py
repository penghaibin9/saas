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
    db.add(col)
    db.flush()
    maj = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(maj)
    db.flush()
    a = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="软件2101", grade="2021",
                    counselor_id=999001, status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="软件2102", grade="2021",
                    counselor_id=999002, status="ACTIVE")
    db.add(a)
    db.add(b)
    db.flush()
    for no, name, cid, g in [("A001", "甲一", a.id, "男"), ("A002", "甲二", a.id, "女"),
                             ("B001", "乙一", b.id, "男")]:
        db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, class_id=cid, gender=g,
                              current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE"))
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "col": col.id, "maj": maj.id}
    db.close()
    return ids


def test_c1_class_list_metrics(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get("/api/v1/student-affairs/classes", headers=hdr).json()
    assert r["code"] == 0 and r["data"]["total"] == 2
    a = next(x for x in r["data"]["items"] if x["classId"] == str(ids["A"]))
    assert a["className"] == "软件2101" and a["majorName"] == "软件技术"
    assert a["collegeName"] == "软件学院" and a["studentCount"] == 2


def test_c2_class_list_filters(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 关键词
    kw = client.get("/api/v1/student-affairs/classes?keyword=2101", headers=hdr).json()
    assert kw["data"]["total"] == 1 and kw["data"]["items"][0]["classId"] == str(ids["A"])
    # 学院筛选
    col = client.get(f"/api/v1/student-affairs/classes?collegeId={ids['col']}", headers=hdr).json()
    assert col["data"]["total"] == 2
    # 年级筛选（无匹配）
    g = client.get("/api/v1/student-affairs/classes?grade=2099", headers=hdr).json()
    assert g["data"]["total"] == 0


def test_c3_class_profile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"/api/v1/student-affairs/classes/{ids['A']}/profile", headers=hdr).json()
    assert r["code"] == 0
    m = {x["key"]: x["value"] for x in r["data"]["metrics"]}
    assert m["studentCount"] == 2 and m["male"] == 1 and m["female"] == 1


def test_c4_class_students_masked(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"/api/v1/student-affairs/classes/{ids['A']}/students", headers=hdr).json()
    assert r["data"]["total"] == 2
    assert "phoneMasked" in r["data"]["items"][0]


def test_c5_class_profile_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    r = client.get(f"/api/v1/student-affairs/classes/{ids['B']}/profile",
                   headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_c6_material_crud(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 非法类型 → 400
    assert client.post(f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr,
                       json={"materialType": "BAD", "title": "x"}).status_code == 400
    # 新增
    r = client.post(f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr,
                    json={"materialType": "CLASS_MEETING", "title": "第3周主题班会记录",
                          "materialAt": "2026-03-10", "remark": "全员到齐"}).json()
    assert r["code"] == 0
    mid = r["data"]["id"]
    assert r["data"]["materialTypeLabel"] == "班会记录"
    # 列表
    lst = client.get(f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr).json()
    assert lst["data"]["total"] == 1
    # 作废
    assert client.delete(f"/api/v1/student-affairs/classes/materials/{mid}", headers=hdr).json()["code"] == 0
    lst2 = client.get(f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr).json()
    assert lst2["data"]["total"] == 0


def test_c7_material_invalid_file(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 无效 file_id → 400
    assert client.post(f"/api/v1/student-affairs/classes/{ids['A']}/materials", headers=hdr,
                       json={"materialType": "OTHER", "title": "带附件", "fileId": "f-nonexistent"}
                       ).status_code == 400


def test_c8_material_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(f"/api/v1/student-affairs/classes/{ids['B']}/materials",
                    headers=_hdr(client, "counselor01"),
                    json={"materialType": "OTHER", "title": "越权材料"})
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_c9_counselor_assessment_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 建周期
    p = client.post("/api/v1/student-affairs/counselor-assessment/periods", headers=hdr,
                    json={"periodName": "2025-2026上 辅导员考评", "semester": "2025-1"}).json()
    assert p["code"] == 0
    pid = p["data"]["id"]
    # 生成指标（2 位辅导员：A班 999001 / B班 999002）
    col = client.post(f"/api/v1/student-affairs/counselor-assessment/periods/{pid}/collect",
                      headers=hdr).json()
    assert col["data"]["counselors"] == 2
    lst = client.get(f"/api/v1/student-affairs/counselor-assessment/periods/{pid}/assessments",
                     headers=hdr).json()
    assert len(lst["data"]["items"]) == 2
    a_row = next(x for x in lst["data"]["items"] if x["counselorId"] == "999001")
    assert a_row["classCount"] == 1 and a_row["studentCount"] == 2 and a_row["autoScore"] is not None
    # 学院评分 → 综合分 + 排名
    sc = client.post(f"/api/v1/student-affairs/counselor-assessment/assessments/{a_row['id']}/score",
                     headers=hdr, json={"collegeScore": 92}).json()
    assert sc["data"]["status"] == "SCORED" and sc["data"]["totalScore"] is not None
    assert sc["data"]["rankNo"] in (1, 2)
    # 评分越界 → 拒绝（Pydantic le=100 + 服务端双校验）
    assert client.post(f"/api/v1/student-affairs/counselor-assessment/assessments/{a_row['id']}/score",
                       headers=hdr, json={"collegeScore": 150}).status_code in (400, 422)
    # 发布 → PUBLISHED，再 collect → 409
    pub = client.post(f"/api/v1/student-affairs/counselor-assessment/periods/{pid}/publish",
                      headers=hdr).json()
    assert pub["data"]["status"] == "PUBLISHED"
    assert client.post(f"/api/v1/student-affairs/counselor-assessment/periods/{pid}/collect",
                       headers=hdr).status_code == 409
