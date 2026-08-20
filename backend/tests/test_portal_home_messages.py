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
    # V3 HomeProjection v2（SP-H01）：不再是 me_overview 原样转发，而是带版本/分区
    # 状态/typed action 的投影 DTO。
    assert d.get("homeVersion") == 2
    assert d.get("asOf")
    assert d["student"]["studentNo"] == "HM-001"
    # 三个独立读取分区各自诚实报告状态，正常路径下应全部 DATA/EMPTY，不是 ERROR。
    sections = d.get("sections") or {}
    for key in ("core", "todo", "message"):
        assert sections.get(key, {}).get("state") in ("DATA", "EMPTY")
    assert isinstance(d.get("quickServices"), list) and len(d["quickServices"]) >= 1
    # 快捷入口每项都带完整 typed action，target.client 固定为 studentPc。
    e = d["quickServices"][0]
    assert e["key"] and e["label"] and e["path"]
    assert e["action"]["target"]["client"] == "studentPc"
    # 成功查询下的计数是真实 0/正整数，不是 unknown（SP-H08）。
    summary = d.get("summary") or {}
    assert summary.get("todoCount") is not None
    assert summary.get("unreadCount") is not None


def test_home_overview_todo_and_message_typed_action(client, db_mode):
    """SP-H03：首页待办/消息卡片必须带 StudentPcActionDescriptor，未知/未落地一律 fail-closed。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import UnifiedMessage

    uid = 930005
    _seed("HM-005", "首页五")
    db = get_sessionmaker()()
    db.add(UnifiedMessage(
        tenant_id=TID, receiver_id=uid, receiver_user_id=uid, receiver_context_key="GLOBAL",
        title="请假审批已退回", message_type="BUSINESS", category="BUSINESS", status="UNREAD",
        source_module="student-affairs", action_key="AFFAIRS_LEAVE",
        action_params_json={"recordId": "9001"}))
    db.commit()
    db.close()

    # message_center_service 按 resolve_message_user_id(userId) 判定本人可见性，
    # 与 StudentProfile.id 无关：token 的 userId 必须能解析成上面写入的 uid。
    h = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{uid}", "realName": "首页五", "studentNo": "HM-005",
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}
    r = client.get(f"{PORTAL}/home/overview", headers=h).json()
    assert r["code"] == 0
    d = r["data"]
    notices = d.get("notices") or []
    assert notices, "AFFAIRS_LEAVE 消息应出现在首页 notices"
    action = notices[0]["action"]
    # 真实落点：/campus-service?tab=leave&recordId=9001（不再是死链 /leave）。
    assert action["target"]["client"] == "studentPc"
    assert action["target"]["path"] == "/campus-service"
    assert action["target"]["query"].get("tab") == "leave"
    assert action["target"]["query"].get("recordId") == "9001"
    assert action["disabledReason"] is None


def test_home_overview_message_failure_is_isolated_error_not_fake_empty(client, db_mode, monkeypatch):
    """SP-H02：单个分区故障必须诚实报 ERROR，不能吞成空数组冒充"暂无消息"，
    也不能拖垮其他分区（core/todo 仍应正常返回真实数据）。"""
    from app.student_portal.services import home_projection_service

    def _boom(*args, **kwargs):
        raise RuntimeError("message center 暂时不可用（模拟故障注入）")

    monkeypatch.setattr(home_projection_service.message_svc, "list_messages", _boom)

    _seed("HM-006", "首页六")
    h = _stu_token("首页六", "HM-006")
    r = client.get(f"{PORTAL}/home/overview", headers=h).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["sections"]["message"]["state"] == "ERROR"
    assert d["sections"]["core"]["state"] in ("DATA", "EMPTY")
    assert d["notices"] == []
    # unreadCount 是 unknown，不能假装真实 0（SP-H08）。
    assert d["summary"]["unreadCount"] is None
    # core 分区没受连累，学生身份信息仍然真实返回。
    assert d["student"]["studentNo"] == "HM-006"


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
