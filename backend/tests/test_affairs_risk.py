"""13A-P4 风险预警闭环 · 端到端（真实 DB 模式）。

R1 建单+分派；R2 处置→关闭进360；R3 无处置记录关闭409；R4 来源去重409；
R5 升级+超时扫描幂等；R6 心理来源明细按角色隐藏；越权跨班403。
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
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _create(client, hdr, sid, source="ACADEMIC_WARNING", ref="1001", level="MEDIUM", detail="学业预警明细"):
    return client.post(f"{BASE}/risk/records", headers=hdr, json={
        "studentId": str(sid), "source": source, "sourceRefId": ref, "riskLevel": level,
        "title": "风险", "detail": detail})


def test_r1_create_assign(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    r = client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": "486"}).json()
    assert r["data"]["status"] == "ASSIGNED" and r["data"]["ownerId"] == "486"


def test_r2_process_close_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": "486"})
    client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr, json={"content": "已约谈学生了解情况"})
    r = client.post(f"{BASE}/risk/records/{rid}/close", headers=hdr,
                    json={"conclusion": "学生情绪稳定，风险解除"}).json()
    assert r["data"]["status"] == "CLOSED"
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    db = get_sessionmaker()()
    assert db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="RISK_CLOSED").count() == 1
    db.close()


def test_r3_close_without_handle_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": "486"})
    # ASSIGNED 无处置记录直接关闭 → 状态校验 409（close 要求 PROCESSING/FOLLOWING/ESCALATED）
    assert client.post(f"{BASE}/risk/records/{rid}/close", headers=hdr,
                       json={"conclusion": "无处置直接关闭"}).status_code == 409


def test_r4_duplicate_source_ref_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _create(client, hdr, ids["sa"], source="ACADEMIC_WARNING", ref="2001")
    assert _create(client, hdr, ids["sa"], source="ACADEMIC_WARNING", ref="2001").status_code == 409


def test_r5_escalate_and_scan_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"], level="LOW").json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": "486"})
    client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr, json={"content": "首次处置记录"})
    r = client.post(f"{BASE}/risk/records/{rid}/escalate", headers=hdr, json={"reason": "情况恶化"}).json()
    assert r["data"]["status"] == "ESCALATED" and r["data"]["riskLevel"] == "MEDIUM"  # LOW→MEDIUM
    # 超时扫描幂等（无 ASSIGNED 超时项 → 0）
    r2 = client.post(f"{BASE}/risk/scan-timeout", headers=hdr).json()
    assert r2["data"]["escalated"] == 0


def test_r6_mental_detail_masked_by_role(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _create(client, admin, ids["sa"], source="MENTAL", ref="3001",
                  detail="心理咨询详细记录").json()["data"]["riskId"]
    # 学工处（授权）见明细
    d_admin = client.get(f"{BASE}/risk/records/{rid}", headers=admin).json()["data"]
    assert d_admin["detail"] == "心理咨询详细记录" and d_admin["mentalMasked"] is False
    # 辅导员（普通教师）明细受限
    d_c = client.get(f"{BASE}/risk/records/{rid}", headers=_hdr(client, "counselor01")).json()["data"]
    assert d_c["mentalMasked"] is True and "心理咨询详细记录" not in d_c["detail"]


def test_r7_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _create(client, admin, ids["sb"], ref="4001").json()["data"]["riskId"]
    r = client.get(f"{BASE}/risk/records/{rid}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"
