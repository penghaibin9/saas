"""P10 收口补齐测试：实习打卡真实落库 / 消息已读本人闭环 / 令牌 DB 持久化（多 worker）。"""
from __future__ import annotations

MAIN = 1000000000000000001


def _stu_token(real_name, student_no=None):
    from app.core.security import create_access_token
    claims = {"userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
              "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
              "currentRoleCode": "STUDENT", "clientType": "MP"}
    if student_no:
        claims["studentNo"] = student_no
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile, UnifiedMessage
    db = get_sessionmaker()()
    try:
        p = StudentProfile(tenant_id=MAIN, student_no="CK0001", real_name="打卡生", grade="2023",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        q = StudentProfile(tenant_id=MAIN, student_no="CK0002", real_name="无实习生", grade="2023",
                           current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
        db.add_all([p, q])
        db.flush()
        db.add(InternshipRecord(tenant_id=MAIN, student_id=p.id, enterprise_name="打卡企业",
                                position_name="实习生", status="ONBOARD", risk_level="LOW"))
        m1 = UnifiedMessage(tenant_id=MAIN, receiver_id=p.id, title="给打卡生的通知", status="UNREAD")
        m2 = UnifiedMessage(tenant_id=MAIN, receiver_id=q.id, title="给别人的通知", status="UNREAD")
        db.add_all([m1, m2])
        db.commit()
        db.refresh(m1); db.refresh(m2)
        return {"p": p.id, "m_own": m1.id, "m_other": m2.id}
    finally:
        db.close()


# ═══ 实习打卡 ═══

def test_checkin_success_then_409(client, db_mode):
    _seed(db_mode)
    h = _stu_token("打卡生", "CK0001")
    ok = client.post("/api/v1/mobile/internship/checkin", headers=h,
                     json={"lat": 30.5, "lng": 114.3, "address": "企业园区"}).json()
    assert ok["code"] == 0 and ok["data"]["result"] == "RECORDED"
    dup = client.post("/api/v1/mobile/internship/checkin", headers=h, json={}).json()
    assert dup["code"] == 409001
    # /mobile/internship/my 返回今日已打卡
    my = client.get("/api/v1/mobile/internship/my", headers=h).json()
    assert my["data"]["todayCheckin"]["done"] is True
    assert my["data"]["todayCheckin"]["totalDays"] == 1


def test_checkin_no_location_recorded(client, db_mode):
    _seed(db_mode)
    h = _stu_token("打卡生", "CK0001")
    ok = client.post("/api/v1/mobile/internship/checkin", headers=h, json={}).json()
    assert ok["code"] == 0 and ok["data"]["result"] == "NO_LOCATION"


def test_checkin_without_internship_404(client, db_mode):
    _seed(db_mode)
    r = client.post("/api/v1/mobile/internship/checkin",
                    headers=_stu_token("无实习生", "CK0002"), json={}).json()
    assert r["code"] == 404001


def test_checkin_requires_student(client, db_mode):
    _seed(db_mode)
    from app.core.security import create_access_token
    tea = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-t", "realName": "老师", "userType": "TEACHER", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "COUNSELOR",
        "clientType": "MP"})}
    assert client.post("/api/v1/mobile/internship/checkin", headers=tea,
                       json={}).json()["code"] == 403001


# ═══ 消息已读（严格本人） ═══

def test_message_read_own_and_not_others(client, db_mode):
    ids = _seed(db_mode)
    h = _stu_token("打卡生", "CK0001")
    ok = client.post(f"/api/v1/mobile/me/messages/{ids['m_own']}/read", headers=h).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "READ"
    # 再读幂等
    again = client.post(f"/api/v1/mobile/me/messages/{ids['m_own']}/read", headers=h).json()
    assert again["code"] == 0
    # 别人的消息 → 404（不泄露存在性）
    deny = client.post(f"/api/v1/mobile/me/messages/{ids['m_other']}/read", headers=h).json()
    assert deny["code"] == 404001


# ═══ 令牌 DB 持久化（多 worker / 重启存活） ═══

def test_refresh_token_persisted_in_db(client, db_mode):
    from sqlalchemy import select
    from app.core import token_store
    from app.db.session import get_sessionmaker
    from app.models import AuthRefreshToken
    claims = {"userId": "u-persist", "realName": "持久化", "userType": "STUDENT",
              "tid": "demo", "tenantId": str(MAIN)}
    token = token_store.issue_refresh(claims)
    db = get_sessionmaker()()
    rows = db.scalars(select(AuthRefreshToken)).all()
    db.close()
    assert len(rows) == 1 and rows[0].user_id == "u-persist"
    assert token not in str(rows[0].token_hash)  # 库中只存哈希，不存明文
    # 模拟另一个 worker：清空本进程内存后仍可从 DB 消费
    token_store._refresh.clear()
    got = token_store.consume_refresh(token)
    assert got and got["userId"] == "u-persist"
    # 轮换语义：同一 refresh 第二次消费失败
    assert token_store.consume_refresh(token) is None


def test_jti_blacklist_persisted_in_db(client, db_mode):
    from app.core import token_store
    token_store.block_jti("jti-persist-1", None)
    # 模拟另一个 worker：清掉内存 L1，仍能从 DB 判定已拉黑
    token_store._blocked_jti.clear()
    assert token_store.jti_blocked("jti-persist-1") is True
    assert token_store.jti_blocked("jti-unknown") is False


def test_logout_kills_token_across_workers(client, db_mode):
    """登出后：即使换一个'进程'（清内存），旧 access 也失效。"""
    from app.core import token_store
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "student01", "password": "demo"}).json()["data"]
    h = {"Authorization": "Bearer " + data["accessToken"]}
    assert client.get("/api/v1/mobile/me/overview", headers=h).json()["code"] == 0
    assert client.post("/api/v1/auth/logout", headers=h).json()["code"] == 0
    token_store._blocked_jti.clear()  # 模拟另一 worker
    assert client.get("/api/v1/mobile/me/overview", headers=h).json()["code"] == 401001
