"""13B-P2 培养方案编制骨架 · 端到端。

PG1 建方案+加课程+学分差额；PG2 编制态可编辑；PG3 列表。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_pg1_create_add_course_credit_gap(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "软件技术2026培养方案", "majorId": "1", "gradeYear": "2026",
        "totalCredits": 120, "requirement": {"公共": 40, "专业": 60, "实践": 20}}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "高等数学", "openTermNo": 1, "module": "公共", "credit": 5})
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "数据结构", "openTermNo": 2, "module": "专业", "credit": 4})
    d = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    assert len(d["courses"]) == 2
    assert d["creditSum"] == 9 and d["creditGap"] == 111  # 120-9


def test_pg2_editable_in_draft(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "初版", "totalCredits": 100}).json()["data"]["programId"]
    r = client.put(f"{BASE}/programs/{pid}", headers=hdr, json={"totalCredits": 130}).json()
    assert r["data"]["totalCredits"] == 130


def test_pg3_list(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    client.post(f"{BASE}/programs", headers=hdr, json={"programName": "方案A", "majorId": "1"})
    items = client.get(f"{BASE}/programs?majorId=1", headers=hdr).json()["data"]["items"]
    assert any(p["programName"] == "方案A" for p in items)
