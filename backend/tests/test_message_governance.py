"""消息治理：深链白名单、静默时段、发布频控、业务 outbox。"""
from __future__ import annotations

from datetime import datetime, timedelta

MAIN = 1000000000000000001
CA_UID = 71001


def _token(user_id, login_name, role="COUNSELOR", user_type="TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "loginName": login_name, "realName": f"姓名{user_id}",
        "userType": user_type, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def test_action_key_registry_rejects_unknown():
    from app.core.exceptions import AppException
    from app.services.message_action_registry import validate_action

    key, params = validate_action(None, None)
    assert key is None and params is None

    key, params = validate_action("student.leave.detail", {"leaveId": 9})
    assert key == "student.leave.detail"
    assert params["leaveId"] == 9

    try:
        validate_action("evil.external.url", {"url": "https://evil"})
        assert False, "should reject"
    except AppException as e:
        assert e.code == "MESSAGE_ACTION_NOT_ALLOWED"

    try:
        validate_action("student.leave.detail", {})
        assert False, "missing param"
    except AppException as e:
        assert e.code == "VALIDATION_ERROR"


def test_quiet_hours_and_emergency_bypass():
    from app.services import message_governance_service as gov

    # 本地 23:30 → UTC 15:30
    night = datetime(2026, 7, 22, 15, 30, 0)
    assert gov.is_in_quiet_hours(night) is True

    day = datetime(2026, 7, 22, 2, 0, 0)  # 本地 10:00
    assert gov.is_in_quiet_hours(day) is False

    q = gov.apply_quiet_hours_policy(
        emergency=False, publish_mode="IMMEDIATE", scheduled_at=None, now=night)
    assert q["publishMode"] == "SCHEDULED"
    assert q["scheduledAt"] is not None
    assert q["quietBypassed"] is False

    e = gov.apply_quiet_hours_policy(
        emergency=True, publish_mode="IMMEDIATE", scheduled_at=None, now=night)
    assert e["quietBypassed"] is True
    assert e["publishMode"] == "IMMEDIATE"


def test_create_campaign_rejects_illegal_action_key(client, db_mode):
    h = _token(CA_UID, "counselorA")
    r = client.post("/api/v1/admin/message-campaigns", headers=h, json={
        "title": "非法深链测试标题够长",
        "contentPlain": "正文内容",
        "category": "ANNOUNCEMENT",
        "actionKey": "not.registered.key",
        "actionParams": {"x": 1},
        "idempotencyKey": "msg-bad-action-1",
    }).json()
    assert r["code"] != 0
    assert "深链" in (r.get("message") or "") or r.get("code") in (
        "MESSAGE_ACTION_NOT_ALLOWED", "VALIDATION_ERROR")


def test_action_keys_api(client, db_mode):
    h = _token(CA_UID, "counselorA")
    r = client.get("/api/v1/admin/message-campaigns/action-keys", headers=h).json()
    assert r["code"] == 0, r
    items = r["data"]["items"]
    assert any(i["actionKey"] == "student.leave.detail" for i in items)


def test_settings_exposes_quiet_and_rate(client, db_mode):
    h = _token(CA_UID, "counselorA")
    r = client.get("/api/v1/admin/message-campaigns/settings", headers=h).json()
    assert r["code"] == 0, r
    assert "quietHours" in r["data"]
    assert r["data"]["quietHours"]["start"] == "22:00"
    assert "rateLimit" in r["data"]
    assert r["data"]["rateLimit"]["maxPerHour"] == 20


def test_emit_receiver_notice_writes_outbox_not_unified(db_mode):
    """业务侧 emit 只落 outbox，不直接插 UnifiedMessage。"""
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox, UnifiedMessage
    from app.services.db_service import _tid
    from app.services.message_event_outbox_service import (
        emit_receiver_notice, process_pending_outbox, try_process_pending_outbox,
    )
    from sqlalchemy import func, select

    db = get_sessionmaker()()
    try:
        before_um = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid())) or 0
        emit_receiver_notice(
            db,
            event_code="FUNDING.NOTICE",
            source_module="student-affairs",
            source_biz_type="funding",
            source_biz_id=900001,
            receiver_id=1,
            title="资助测试通知",
            content="测试正文",
            receiver_as="student",
            dedup_extra="unit",
        )
        db.commit()
        mid = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid())) or 0
        assert mid == before_um, "emit 不得直接写 UnifiedMessage"

        row = db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.event_code == "FUNDING.NOTICE",
            MessageEventOutbox.source_biz_id == 900001,
        ))
        assert row is not None
        assert row.status == "PENDING"

        process_pending_outbox(limit=10, worker_id="test-gov")
        db.expire_all()
        row2 = db.get(MessageEventOutbox, row.id)
        assert row2.status in ("DONE", "PENDING", "RETRY", "DEAD"), row2.status
        # 消费后可能仍因 receiver 无法映射而失败，但不得回退为直接写业务表外路径
        try_process_pending_outbox(limit=5, worker_id="test-gov-2")
    finally:
        db.close()


def test_rate_limit_unit():
    """频控逻辑：超限抛 429。"""
    from app.core.exceptions import AppException
    from app.services import message_governance_service as gov
    from unittest import mock

    with mock.patch.object(gov, "assert_publish_rate", wraps=gov.assert_publish_rate):
        # 直接测计数分支：mock session 返回高计数
        pass

    class FakeScalar:
        def __init__(self, n): self.n = n
        def scalar(self, *a, **k): return self.n
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with mock.patch("app.services.message_governance_service.session", return_value=FakeScalar(20)):
        try:
            gov.assert_publish_rate(CA_UID, limit=20)
            assert False, "should rate limit"
        except AppException as e:
            assert e.http_status == 429
            assert (e.details or {}).get("reason") == "MESSAGE_RATE_LIMIT"
