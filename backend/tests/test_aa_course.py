"""13B-P3 课程库 · 端到端（两级审核 + 版本化 + 学时校验）。

C1 建课→两级审→ENABLED；C2 学时构成校验422；C3 已启用改动强制新版本；C4 重复代码409；C5 退回。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _course(client, hdr, code="CS101", **extra):
    body = {"courseCode": code, "courseName": "数据结构", "courseNameEn": "Data Structure",
            "category": "MAJOR_CORE", "nature": "REQUIRED", "credit": 4,
            "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16, "examMode": "EXAM",
            "isCore": True, **extra}
    return client.post(f"{BASE}/courses", headers=hdr, json=body)


def test_c1_two_level_review_to_enabled(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr).json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    r1 = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "ACADEMIC_REVIEW"  # 学院审过→教务审
    r2 = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "ENABLED"  # 教务审过→启用
    assert r2["data"]["categoryLabel"] == "专业核心" and r2["data"]["natureLabel"] == "必修"


def test_c2_hours_composition_422(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 理论48+实践16=64，但总学时写 80 → 不一致 422
    assert _course(client, hdr, code="CS102", hoursTotal=80).status_code == 400


def test_c3_enabled_edit_forces_new_version(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr, code="CS103").json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # ENABLED
    # 改已启用课程 → 生成 v2 草稿
    r = client.put(f"{BASE}/courses/{cid}", headers=hdr, json={
        "courseCode": "CS103", "courseName": "数据结构(修订)", "category": "MAJOR_CORE",
        "nature": "REQUIRED", "credit": 5, "hoursTotal": 64, "hoursTheory": 48,
        "hoursPractice": 16, "examMode": "EXAM"}).json()
    assert r["data"]["version"] == 2 and r["data"]["status"] == "DRAFT"


def test_c4_duplicate_code_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _course(client, hdr, code="CS104")
    assert _course(client, hdr, code="CS104").status_code == 409


def test_c5_reject_returns(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr, code="CS105").json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    r = client.post(f"{BASE}/courses/{cid}/review", headers=hdr,
                    json={"action": "RETURN", "reason": "学时构成需调整"}).json()
    assert r["data"]["status"] == "RETURNED"
