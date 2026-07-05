"""短信通知测试（P13-B）：mock 成功 / 关闭跳过 / 缺号跳过 / 脱敏 / 频率 / 重试 /
失败不影响业务 / 租户隔离。测试环境永不真实发送。"""
from __future__ import annotations

import pytest

MAIN = 1000000000000000001
DEMO = 1000000000000000003


@pytest.fixture()
def sms_on():
    """打开 SMS 开关（用 mock provider），测试后还原。"""
    from app.core.config import settings
    old = settings.SMS_ENABLED
    settings.SMS_ENABLED = "true"
    yield
    settings.SMS_ENABLED = old


def _logs_count(tenant_id, result=None):
    from sqlalchemy import func, select
    from app.db.session import get_sessionmaker
    from app.models import NotificationLog
    db = get_sessionmaker()()
    try:
        q = select(func.count()).select_from(NotificationLog).where(NotificationLog.tenant_id == tenant_id)
        if result:
            q = q.where(NotificationLog.result == result)
        return db.scalar(q) or 0
    finally:
        db.close()


def test_mock_send_success(db_mode, sms_on):
    from app.services.notification import sms_service
    r = sms_service.send_sms(MAIN, "13800001234", "TODO", {"name": "张三"}, "TODO", "张三")
    assert r["status"] == "SENT" and r["requestId"].startswith("mock-")
    assert _logs_count(MAIN, "SUCCESS") == 1


def test_disabled_skips_no_send(db_mode):
    from app.core.config import settings
    assert (settings.SMS_ENABLED or "").lower() != "true"  # 默认关闭
    from app.services.notification import sms_service
    r = sms_service.send_sms(MAIN, "13800001234", "TODO", {}, "TODO")
    assert r["status"] == "SKIPPED" and "SMS_ENABLED" in r["reason"]
    assert _logs_count(MAIN, "SKIPPED") == 1 and _logs_count(MAIN, "SUCCESS") == 0


def test_missing_phone_skipped(db_mode, sms_on):
    from app.services.notification import sms_service
    r = sms_service.send_sms(MAIN, "", "TODO", {}, "TODO")
    assert r["status"] == "SKIPPED" and r["reason"] == "缺手机号"


def test_phone_masked_in_log(db_mode, sms_on):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import NotificationLog
    from app.services.notification import sms_service
    sms_service.send_sms(MAIN, "13812345678", "TODO", {}, "TODO")
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(NotificationLog).where(NotificationLog.tenant_id == MAIN)).first()
        assert row.phone_masked and "****" in row.phone_masked
        assert "13812345678" != row.phone_masked and "12345" not in row.phone_masked
    finally:
        db.close()


def test_rate_limit(db_mode, sms_on):
    from app.core.config import settings
    from app.services.notification import sms_service
    old = settings.SMS_RATE_LIMIT_PER_MINUTE
    settings.SMS_RATE_LIMIT_PER_MINUTE = 2
    sms_service._RATE.clear()  # 清空跨用例累计的计数，隔离本用例
    try:
        r1 = sms_service.send_sms(MAIN, "13800000001", "TODO", {}, "TODO")
        r2 = sms_service.send_sms(MAIN, "13800000002", "TODO", {}, "TODO")
        r3 = sms_service.send_sms(MAIN, "13800000003", "TODO", {}, "TODO")
        assert r1["status"] == "SENT" and r2["status"] == "SENT"
        assert r3["status"] == "SKIPPED" and "频率" in r3["reason"]
    finally:
        settings.SMS_RATE_LIMIT_PER_MINUTE = old


def test_retry_then_success(db_mode, sms_on):
    from app.services.notification import sms_service
    from app.services.notification.providers.mock_sms_provider import MockSmsProvider
    p = MockSmsProvider(fail_times=1)  # 第1次失败，重试后成功
    r = sms_service.send_sms(MAIN, "13800000009", "TODO", {}, "TODO", provider=p)
    assert r["status"] == "SENT" and r["retries"] == 1


def test_failure_does_not_break_business(db_mode, sms_on):
    from app.services.notification import sms_service
    from app.services.notification.providers.mock_sms_provider import MockSmsProvider
    p = MockSmsProvider(fail=True)  # 恒失败
    r = sms_service.send_sms(MAIN, "13800000010", "TODO", {}, "TODO", provider=p)
    # 不抛异常，返回 FAILED，业务可继续
    assert r["status"] == "FAILED"
    assert _logs_count(MAIN, "FAIL") >= 1


def test_tenant_isolation(db_mode, sms_on):
    from app.services.notification import sms_service
    sms_service.send_sms(MAIN, "13800000011", "TODO", {}, "TODO")
    sms_service.send_sms(DEMO, "13800000012", "WARNING", {}, "WARNING")
    assert _logs_count(MAIN) >= 1 and _logs_count(DEMO) >= 1
    # 各租户日志互不串
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import NotificationLog
    db = get_sessionmaker()()
    try:
        main_rows = db.scalars(select(NotificationLog).where(NotificationLog.tenant_id == MAIN)).all()
        assert all(r.tenant_id == MAIN for r in main_rows)
    finally:
        db.close()


def test_api_send_test_and_logs(client, db_mode):
    from app.core.security import create_access_token
    hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-staff", "realName": "李管理", "userType": "SCHOOL_ADMIN",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})}
    # 默认关闭：send-test 返回 SKIPPED，不真实发送
    r = client.post("/api/v1/notification/send-test", headers=hdr,
                    json={"phone": "13800000013", "templateCode": "TODO"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "SKIPPED"
    lg = client.get("/api/v1/notification/logs", headers=hdr).json()
    assert lg["code"] == 0 and isinstance(lg["data"]["list"], list)
