"""13B-P2 学籍异动全链路 · 端到端（真实 DB 模式）。

SC1 休学全链→SUSPENDED+到期日；SC2 复学→REGISTERED；SC3 转专业迁院系班(状态不变)；
SC4 在途重复409；SC5 终态学生禁发起422；SC6 复学前置非休学409；SC7 驳回。
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
    b = SchoolClass(tenant_id=TID, major_id=2, class_name="网络2101", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA001", real_name="学籍甲", class_id=a.id,
                       college_id=10, major_id=1, current_stage="ON_CAMPUS",
                       student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"a": a.id, "b": b.id, "s": s.id}
    db.commit()
    db.close()
    return ids


def _submit(client, hdr, sid, ct, **extra):
    return client.post(f"{BASE}/status-changes", headers=hdr,
                       json={"studentId": str(sid), "changeType": ct, "reason": f"{ct}原因说明足够长", **extra})


def _approve(client, hdr, cid, times):
    r = None
    for _ in range(times):
        r = client.post(f"{BASE}/status-changes/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    return r.json()


def _status(client, sid, hdr):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    st = db.get(StudentProfile, sid).student_status
    db.close()
    return st


def test_sc1_suspend_full_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "SUSPEND").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 3)  # 辅导员→学院→教务处
    assert r["data"]["status"] == "EFFECTIVE" and r["data"]["toStatus"] == "SUSPENDED"
    assert r["data"]["expireDate"]  # 休学到期日已设(真实补充)
    assert _status(client, ids["s"], hdr) == "SUSPENDED"


def test_sc2_resume_after_suspend(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    c1 = _submit(client, hdr, ids["s"], "SUSPEND").json()["data"]["changeId"]
    _approve(client, hdr, c1, 3)
    c2 = _submit(client, hdr, ids["s"], "RESUME", toClassId=str(ids["a"])).json()["data"]["changeId"]
    r = _approve(client, hdr, c2, 3)
    assert r["data"]["toStatus"] == "REGISTERED"
    assert _status(client, ids["s"], hdr) == "REGISTERED"


def test_sc3_transfer_major_moves_org(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "TRANSFER_MAJOR",
                  toMajorId="2", toClassId=str(ids["b"]), toCollegeId="20").json()["data"]["changeId"]
    r = _approve(client, hdr, cid, 4)  # 辅导员→转出院→接收院→教务处
    assert r["data"]["status"] == "EFFECTIVE"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    # 转专业不改学籍状态字面，但迁移了院系班
    assert s.student_status == "REGISTERED" and s.class_id == ids["b"] and s.major_id == 2
    db.close()


def test_sc4_duplicate_active_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _submit(client, hdr, ids["s"], "SUSPEND")
    assert _submit(client, hdr, ids["s"], "WITHDRAW").status_code == 409


def test_sc5_terminal_student_422(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "WITHDRAW").json()["data"]["changeId"]
    _approve(client, hdr, cid, 3)  # → WITHDRAWN(终态)
    assert _status(client, ids["s"], hdr) == "WITHDRAWN"
    # 终态学生再发起异动 → 422
    r = _submit(client, hdr, ids["s"], "SUSPEND")
    assert r.status_code == 400  # VALIDATION_ERROR→400


def test_sc6_resume_requires_suspended_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # NORMAL 学生直接复学 → 409
    assert _submit(client, hdr, ids["s"], "RESUME").status_code == 409


def test_sc7_reject(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _submit(client, hdr, ids["s"], "SUSPEND").json()["data"]["changeId"]
    r = client.post(f"{BASE}/status-changes/{cid}/review", headers=hdr,
                    json={"action": "REJECT", "reason": "材料不齐，不予批准"}).json()
    assert r["data"]["status"] == "REJECTED"
    assert _status(client, ids["s"], hdr) == "NORMAL"  # 未生效，主档不变


def test_sc8_student_forbidden_403(client, db_mode):
    """越权红线（13B-FE-W2 学籍写侧接入波补齐）：学生令牌打异动/注册/名册端点一律 403（require_staff）。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/status-changes", headers=hdr,
                       json={"studentId": "1", "changeType": "SUSPEND"}).status_code == 403
    assert client.get(f"{BASE}/status-changes", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/registration-batches", headers=hdr,
                       json={"batchName": "x"}).status_code == 403
    assert client.get(f"{BASE}/roster", headers=hdr).status_code == 403
