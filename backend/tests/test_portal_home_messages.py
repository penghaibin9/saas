"""学生 PC 门户 · 首页聚合 + 消息 PC 视图测试（MySQL 真库 via db_mode）：

首页聚合(本人真实聚合+快捷入口) / 消息分页视图 / 标记已读守卫(非法id·不存在) /
通知偏好(读+非法key拒绝) / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2023",
                          current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_home_overview(client, db_mode):
    _seed("HM-001", "首页一")
    h = _stu_token("首页一", "HM-001")
    r = client.get(f"{PORTAL}/home/overview", headers=h).json()
    assert r["code"] == 0
    d = r["data"]
    assert d.get("hasData") is True
    assert d["student"]["studentNo"] == "HM-001"
    assert isinstance(d.get("quickEntries"), list) and len(d["quickEntries"]) >= 1
    # 快捷入口每项结构完整
    e = d["quickEntries"][0]
    assert e["key"] and e["label"] and e["path"]


def test_messages_inbox_paged(client, db_mode):
    _seed("HM-002", "首页二")
    h = _stu_token("首页二", "HM-002")
    r = client.get(f"{PORTAL}/messages?page=1&pageSize=10", headers=h).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["page"] == 1 and d["pageSize"] == 10 and "total" in d and isinstance(d["list"], list)


def test_message_read_guards(client, db_mode):
    _seed("HM-003", "首页三")
    h = _stu_token("首页三", "HM-003")
    assert client.post(f"{PORTAL}/messages/abc/read", headers=h).json()["code"] != 0        # 非法id
    assert client.post(f"{PORTAL}/messages/999999/read", headers=h).json()["code"] == 404001  # 不存在→404


def test_preferences(client, db_mode):
    _seed("HM-004", "首页四")
    h = _stu_token("首页四", "HM-004")
    assert client.get(f"{PORTAL}/messages/preferences", headers=h).json()["code"] == 0
    # 非法分类 key 拒绝
    assert client.post(f"{PORTAL}/messages/preferences", headers=h,
                       json={"key": "__nope__", "enabled": True}).json()["code"] != 0


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/home/overview", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/messages", headers=admin).json()["code"] == 403001
