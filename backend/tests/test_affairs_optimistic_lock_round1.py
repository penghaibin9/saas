"""学工第一轮 · 乐观锁接入冒烟。

覆盖：risk 并发冲突 409、mental follow 错 version 409、aid review 缺/错 version。
复用 risk 测试同款 seed/login 口径。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    resp = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"})
    assert resp.status_code == 200, f"mock-login failed: {resp.status_code} {resp.text}"
    payload = resp.json()
    data = payload.get("data")
    assert data and data.get("accessToken"), f"mock-login payload missing token: {payload}"
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Role, SchoolClass, StudentProfile, TeacherStudentScope, User, UserRole
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="OL001", real_name="锁一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    role = Role(tenant_id=TID, role_code="COUNSELOR", role_name="辅导员", status="ACTIVE")
    db.add(role); db.flush()
    owner = User(tenant_id=TID, login_name="ol_owner01", real_name="锁责任人",
                 password_hash="x", user_type="TEACHER", status="ACTIVE")
    db.add(owner); db.flush()
    db.add(UserRole(tenant_id=TID, user_id=owner.id, role_id=role.id, status="ACTIVE"))
    db.commit()
    ids = {"sa": sa.id, "owner": owner.id}
    db.close()
    return ids


def test_risk_stale_version_conflict_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    created = client.post(f"{BASE}/risk/records", headers=hdr, json={
        "studentId": str(ids["sa"]), "source": "MANUAL", "sourceRefId": f"ol-{ids['sa']}",
        "riskLevel": "MEDIUM", "title": "乐观锁", "detail": "并发测试明细不少于五字"}).json()["data"]
    rid, ver = created["riskId"], created["version"]
    ok = client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr,
                     json={"ownerId": str(ids["owner"]), "version": ver})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "ASSIGNED"
    stale = client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr,
                        json={"content": "用旧版本处置应冲突不少于五", "version": ver})
    assert stale.status_code == 409 and stale.json()["bizCode"] == "APPROVAL_VERSION_CONFLICT"
    missing = post_versioned(client, f"{BASE}/risk/records/{rid}/process", headers=hdr,
                          json={"content": "缺少 version 也应拦截不少于"})
    assert missing.status_code in (400, 422)


def test_mental_follow_wrong_version_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    ref = client.post(f"{BASE}/mental/referrals", headers=hdr, json={
        "studentId": str(ids["sa"]), "level": "FOCUS", "channel": "校内咨询",
        "reasonSummary": "情绪波动需持续关注", "note": "明细"}).json()["data"]
    rid, ver = ref["referralId"], ref["version"]
    bad = client.post(f"{BASE}/mental/referrals/{rid}/follow", headers=hdr,
                      json={"content": "回访记录不少于五字", "version": int(ver) + 9})
    assert bad.status_code == 409 and bad.json()["bizCode"] == "APPROVAL_VERSION_CONFLICT"
    ok = client.post(f"{BASE}/mental/referrals/{rid}/follow", headers=hdr,
                     json={"content": "回访记录不少于五字", "version": ver})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "FOLLOWING"


def test_aid_review_version_required_and_conflict(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/aid/batches", headers=hdr, json={
        "batchName": "OL困难认定", "schoolYear": "2025-2026",
        "publicityDays": 1, "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
        "publish": True}).json()["data"]["batchId"]
    app = client.post(f"{BASE}/aid/applications", headers=hdr, json={
        "batchId": str(bid), "studentId": str(ids["sa"]), "applyLevel": "DIFFICULT",
        "statement": "家庭收入较低，父母务农，需要资助支持完成学业",
        "memberCount": 4, "annualIncome": "25000"}).json()["data"]
    aid_id, ver = app["applyId"], app["version"]
    missing = client.post(f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                          json={"action": "APPROVE"})
    assert missing.status_code in (400, 422)
    stale = client.post(f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                        json={"action": "APPROVE", "version": int(ver) + 7})
    assert stale.status_code == 409 and stale.json()["bizCode"] == "APPROVAL_VERSION_CONFLICT"
