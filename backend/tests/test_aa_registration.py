"""13B-P1 入学/学年注册 + change_student_status 单一写入口 · 端到端。

R1 注册→主档学籍REGISTERED+异动流水+360；R2 重复注册409；R3 未开放批次409；
R4 名册在籍标记；R5 change_student_status 非法转移422；R6 is_enrolled 判定。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


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
    s = StudentProfile(tenant_id=TID, student_no="AA001", real_name="新生甲", class_id=a.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"s": s.id}
    db.commit()
    db.close()
    return ids


def _open_batch(client, hdr, rtype="ENROLL"):
    return client.post(f"{BASE}/registration-batches", headers=hdr, json={
        "batchName": "2026级入学注册", "registerType": rtype, "open": True}).json()["data"]["batchId"]


def test_r1_register_updates_profile_via_single_entry(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    r = client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                    json={"studentId": str(ids["s"])}).json()
    assert r["data"]["studentStatus"] == "REGISTERED" and r["data"]["changeType"] == "ENROLL_REGISTER"
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange, StudentProfile, StudentStageEvent
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.student_status == "REGISTERED"  # 主档已改
    assert db.query(AaStatusChange).filter_by(student_id=ids["s"], to_status="REGISTERED").count() == 1
    ev = db.query(StudentStageEvent).filter_by(student_id=ids["s"], to_stage="REGISTERED",
                                               source_module="academic-affairs").count()
    assert ev == 1  # 进 360
    db.close()


def test_r2_duplicate_register_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    assert client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                       json={"studentId": str(ids["s"])}).status_code == 409


def test_r3_batch_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/registration-batches", headers=hdr, json={
        "batchName": "草稿批次", "registerType": "ENROLL", "open": False}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                       json={"studentId": str(ids["s"])}).status_code == 409


def test_r4_roster_enrolled_flag(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    roster = client.get(f"{BASE}/roster", headers=hdr).json()["data"]["items"]
    row = next(x for x in roster if x["studentId"] == str(ids["s"]))
    assert row["studentStatus"] == "REGISTERED" and row["enrolled"] is True


def test_r5_illegal_transition_422(client, db_mode):
    ids = _seed(db_mode)
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.services.academic_affairs_status_service import change_student_status
    from app.core.exceptions import AppException
    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    # 先合法置为 WITHDRAWN（NORMAL→WITHDRAWN 允许）
    change_student_status(db, ids["s"], "WITHDRAWN", change_type="WITHDRAW", reason="退学")
    db.commit()
    # WITHDRAWN 无出边 → 任何目标非法 422
    raised = False
    try:
        change_student_status(db, ids["s"], "REGISTERED", change_type="ANNUAL_REGISTER")
    except AppException as e:
        raised = e.code == "VALIDATION_ERROR"
    db.close()
    assert raised


def test_r6_is_enrolled():
    from app.services.academic_affairs_status_service import is_enrolled
    assert is_enrolled("REGISTERED") and is_enrolled("NORMAL") and is_enrolled("RETAINED")
    assert not is_enrolled("SUSPENDED") and not is_enrolled("WITHDRAWN") and not is_enrolled("GRADUATED")
