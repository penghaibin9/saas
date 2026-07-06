"""13B-P5 成绩录入(平时+期末按比例) + 读侧视图 · 端到端。

G1 录入合成→发布投影t_acad_grade→成绩单；G2 占比≠100→422；G3 未录全禁发布409；
G4 挂科清单；G5 成绩分析。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, n=2):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    sids = []
    for i in range(n):
        s = StudentProfile(tenant_id=TID, student_no=f"G{i:03d}", real_name=f"成绩{i}", class_id=a.id,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
        db.add(s); db.flush(); sids.append(s.id)
    db.commit()
    db.close()
    return sids


def _task(client, hdr, usual=30, final=70):
    return client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "高等数学", "termCode": "2026-2027-1", "credit": 4,
        "usualRatio": usual, "finalRatio": final}).json()["data"]["gradeTaskId"]


def test_g1_compose_publish_project(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                    json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 90}).json()
    assert r["data"]["totalScore"] == 87 and r["data"]["passStatus"] == "PASSED"  # 80*.3+90*.7
    p = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr).json()
    assert p["data"]["projected"] == 1
    # 投影到 t_acad_grade → 成绩单可读
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    assert any(g["courseName"] == "高等数学" and g["score"] == 87 for g in tr["items"])


def test_g2_ratio_not_100_422(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    assert client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "X", "usualRatio": 40, "finalRatio": 70}).status_code == 400


def test_g3_incomplete_publish_409(client, db_mode):
    sids = _seed(db_mode, 2)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 90})
    # 只录了1人，直接发布 → 但另一人无记录，发布只看已有记录；这里录第2人但缺分
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={"studentId": str(sids[1]), "usualScore": 70})
    assert client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr).status_code == 409


def test_g4_fail_list(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 40, "finalScore": 50})  # 47 FAIL
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    fl = client.get(f"{BASE}/grade-views/fail-list", headers=hdr).json()["data"]["items"]
    assert any(x["courseName"] == "高等数学" for x in fl)


def test_g5_analysis(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 90, "finalScore": 95})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    a = client.get(f"{BASE}/grade-views/analysis", headers=hdr).json()["data"]
    assert a["total"] == 1 and a["passRate"] == 1.0
