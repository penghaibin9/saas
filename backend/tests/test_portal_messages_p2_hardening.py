"""PR190 文档 P2-01/P2-02：学生 PC 消息页生产回归（真实 MySQL）。

锁死两条性质：
1. todo tab 是“待办”而不是“待办+历史完成”：25 DONE + 2 PENDING 时 total/badge 必须都为 2；
2. 通知列表拿到可打开 action 后，如果点击前消息变成 expired/withdrawn，详情必须重新投影
   为 target=None，不能把列表旧 action 继续用于导航（TOCTOU fail-closed）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

TID = 1000000000000000001
PORTAL = "/api/v1/portal"
UID = 940021
STUDENT_NO = "P2-MSG-001"


def _headers():
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": f"u_{UID}",
        "loginName": "p2_message_student",
        "realName": "消息回归学生",
        "studentNo": STUDENT_NO,
        "userType": "STUDENT",
        "tid": "demo",
        "tenantId": str(TID),
        "activeContextId": "ctx_student",
        "currentRoleCode": "STUDENT",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_student(db):
    from app.models import StudentProfile

    student = StudentProfile(
        tenant_id=TID,
        student_no=STUDENT_NO,
        real_name="消息回归学生",
        current_stage="ON_CAMPUS",
        student_status="NORMAL",
        status="ACTIVE",
    )
    db.add(student)
    db.flush()
    return student


def test_todo_tab_and_badge_are_both_pending_only(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo

    db = get_sessionmaker()()
    try:
        student = _seed_student(db)
        for i in range(25):
            db.add(UnifiedTodo(
                tenant_id=TID,
                source_module="student-portal",
                source_biz_type="PROFILE",
                source_biz_id=82000 + i,
                todo_type="PROFILE_CONFIRM",
                assignee_id=UID,
                student_id=student.id,
                title=f"历史已完成待办{i}",
                status="DONE",
            ))
        for i in range(2):
            db.add(UnifiedTodo(
                tenant_id=TID,
                source_module="student-portal",
                source_biz_type="PROFILE",
                source_biz_id=83000 + i,
                todo_type="PROFILE_CONFIRM",
                assignee_id=UID,
                student_id=student.id,
                title=f"当前待办{i}",
                status="PENDING",
            ))
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"{PORTAL}/messages",
        headers=_headers(),
        params={"tab": "todo", "page": 1, "pageSize": 20},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["total"] == 2, data
    assert len(data["list"]) == 2
    assert {x["status"] for x in data["list"]} == {"PENDING"}
    todo_tab = next(x for x in data["tabs"] if x["key"] == "todo")
    assert todo_tab["badge"] == 2, data["tabs"]


def _seed_action_message(db, *, title: str):
    from app.models import UnifiedMessage

    row = UnifiedMessage(
        tenant_id=TID,
        receiver_id=UID,
        receiver_user_id=UID,
        receiver_type="STUDENT",
        receiver_context_key="GLOBAL",
        title=title,
        message_type="BUSINESS",
        category="BUSINESS",
        status="UNREAD",
        action_key="AFFAIRS_LEAVE",
        action_params_json={"recordId": "99123"},
        expire_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(row)
    db.flush()
    return row


def _list_notice(client):
    response = client.get(
        f"{PORTAL}/messages",
        headers=_headers(),
        params={"tab": "notice", "page": 1, "pageSize": 20},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    assert body["data"]["list"], body
    return body["data"]["list"][0]


def test_list_action_cannot_survive_expiry_before_detail(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import UnifiedMessage

    db = get_sessionmaker()()
    try:
        _seed_student(db)
        message = _seed_action_message(db, title="即将过期的请假通知")
        message_id = message.id
        db.commit()
    finally:
        db.close()

    listed = _list_notice(client)
    assert listed["messageId"] == str(message_id)
    assert listed["expired"] is False
    assert listed["action"]["target"]["path"] == "/campus-service"

    # 模拟“列表加载后、用户点击前”时钟/业务状态变化。
    db = get_sessionmaker()()
    try:
        row = db.get(UnifiedMessage, message_id)
        row.expire_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    detail_response = client.get(f"{PORTAL}/messages/{message_id}", headers=_headers())
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()["data"]
    assert detail["expired"] is True
    assert detail["action"]["target"] is None
    assert detail["action"]["allowedActions"] == []
    assert detail["action"]["disabledReason"] == "该消息已过期"


def test_list_action_cannot_survive_withdrawal_before_detail(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import UnifiedMessage

    db = get_sessionmaker()()
    try:
        _seed_student(db)
        message = _seed_action_message(db, title="即将撤回的请假通知")
        message_id = message.id
        db.commit()
    finally:
        db.close()

    listed = _list_notice(client)
    assert listed["messageId"] == str(message_id)
    assert listed["withdrawn"] is False
    assert listed["action"]["target"]["path"] == "/campus-service"

    db = get_sessionmaker()()
    try:
        row = db.get(UnifiedMessage, message_id)
        row.withdrawn_at = datetime.utcnow()
        row.withdraw_reason = "通知内容已更正"
        db.commit()
    finally:
        db.close()

    detail_response = client.get(f"{PORTAL}/messages/{message_id}", headers=_headers())
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()["data"]
    assert detail["withdrawn"] is True
    assert detail["action"]["target"] is None
    assert detail["action"]["allowedActions"] == []
    assert detail["action"]["disabledReason"] == "该消息已撤回"
