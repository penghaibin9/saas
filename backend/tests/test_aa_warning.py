"""13B-P5 学业预警规则引擎 · 端到端（扫描幂等 + 加列来源标识）。

W1 挂科扫描生成预警 + 幂等；W2 预警列表带 source_code/rule_code。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_fail(db_mode):
    """建学业台账 + 2 门挂科成绩（直接落 t_acad_grade）。"""
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="W001", real_name="预警甲", class_id=a.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    acad = AcademicStudent(tenant_id=TID, student_id=s.id, student_no="W001", name="预警甲",
                           class_name="软件2601")
    db.add(acad); db.flush()
    for cn in ("高数", "英语"):
        db.add(AcademicGrade(tenant_id=TID, acad_student_id=acad.id, course_name=cn, term="2026-2027-1",
                             nature="REQUIRED", credit_value=4, score=45, pass_status="FAIL",
                             exam_type="FINAL", record_status="ACTIVE"))
    db.commit()
    ids = {"student": s.id, "acad": acad.id}
    db.close()
    return ids


def test_w1_scan_generates_and_idempotent(client, db_mode):
    _seed_fail(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/warnings/scan", headers=hdr).json()["data"]
    assert r["created"] == 1  # 挂2门→1条预警(MEDIUM)
    # 幂等：再扫不重复建
    r2 = client.post(f"{BASE}/warnings/scan", headers=hdr).json()["data"]
    assert r2["created"] == 0


def test_w2_warning_list_source(client, db_mode):
    _seed_fail(db_mode)
    hdr = _hdr(client, "school_admin01")
    client.post(f"{BASE}/warnings/scan", headers=hdr)
    items = client.get(f"{BASE}/warnings?sourceCode=EXAM_FAIL", headers=hdr).json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["sourceCode"] == "EXAM_FAIL" and items[0]["ruleCode"].startswith("EXAM_FAIL")
    assert items[0]["level"] == "MEDIUM"  # 挂2门
