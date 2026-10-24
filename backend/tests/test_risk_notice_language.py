from types import SimpleNamespace

import pytest

from app.services.message_center_service import _display_content, risk_notice_text


@pytest.mark.parametrize("old, expected", [
    ("风险#1234 处置超时已自动升级至 CRITICAL", "处置超时，风险已自动升级至危急风险"),
    ("风险#1233 已升级至 HIGH：需进一步跟进", "风险已升级至高风险：需进一步跟进"),
    ("有一条MEDIUM风险待你处置", "有一条中风险预警待你处理"),
    ("风险#123 已超时自动分派给你", "一条超时风险已分派给你，请及时处理"),
    ("风险#123 已升级至 NEW_LEVEL", "风险已升级至其他风险等级"),
])
def test_risk_notice_uses_business_text(old, expected):
    assert risk_notice_text(old, "风险升级") == expected
    assert risk_notice_text(expected, "风险升级") == expected


def test_historical_system_notice_is_presented_without_changing_stored_content():
    row = SimpleNamespace(message_type="RISK_ALERT", rendered_content_plain="", content="风险#123 已升级至 HIGH", rendered_title=None, title="风险升级")
    assert _display_content(row) == "风险已升级至高风险"
    assert row.content == "风险#123 已升级至 HIGH"
    row.message_type = "ANNOUNCEMENT"
    assert _display_content(row) == row.content
    row.message_type = "RISK_ALERT"
    row.rendered_content_plain = "请核对 HIGH 风险示例及工号 1234"
    assert _display_content(row) == row.rendered_content_plain
    row.title = "风险转办"
    row.rendered_content_plain = "风险#123 已升级至 HIGH"
    assert _display_content(row) == row.rendered_content_plain


def test_risk_producer_keeps_routing_and_receiver_but_localizes_content(monkeypatch):
    from app.services import affairs_risk_service, message_event_outbox_service
    calls = []
    monkeypatch.setattr(message_event_outbox_service, "emit_receiver_notice", lambda db, **payload: calls.append(payload))
    affairs_risk_service._msg(object(), 17, "风险处置超时升级", "风险#123 已升级至 HIGH", "RISK_ALERT", 123)
    assert calls[0]["content"] == "风险已升级至高风险"
    assert calls[0]["event_code"] == "RISK.ALERT"
    assert calls[0]["source_biz_id"] == 123
    assert calls[0]["receiver_id"] == 17
    assert calls[0]["receiver_as"] == "user"
