"""13A-P6 学工归档 · 端到端（真实 DB 模式）。

V1 批次→收集档案包→逐级流转→ARCHIVED 登记 t_export_task 水印包。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="A002", real_name="甲二", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.add(s2); db.flush()
    ids = {"s1": s1.id, "s2": s2.id}
    db.commit()
    db.close()
    return ids


def test_v1_archive_full_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=hdr, json={
        "batchName": "2026届学工归档", "yearCode": "2026"}).json()["data"]["batchId"]
    c = client.post(f"{BASE}/archive/batches/{bid}/collect", headers=hdr,
                    json={"studentIds": [str(ids["s1"]), str(ids["s2"])]}).json()
    assert c["data"]["packagesCreated"] == 2 and c["data"]["status"] == "COLLECTING"
    # COLLECTING→COLLEGE_REVIEW→SA_CONFIRM→ARCHIVED
    for _ in range(3):
        r = client.post(f"{BASE}/archive/batches/{bid}/advance", headers=hdr, json={"action": "APPROVE"}).json()
    assert r["data"]["status"] == "ARCHIVED"
    # 水印包登记 t_export_task + 档案包归档
    d = client.get(f"{BASE}/archive/batches/{bid}", headers=hdr).json()["data"]
    assert all(p["status"] == "ARCHIVED" and p["exportTaskId"] for p in d["packages"])
    from app.db.session import get_sessionmaker
    from app.models import ExportTask
    db = get_sessionmaker()()
    assert db.query(ExportTask).filter_by(module_code="affairs_archive").count() == 1
    db.close()
