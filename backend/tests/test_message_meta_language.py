from contextlib import contextmanager
from types import SimpleNamespace

from app.services import message_meta_service as service


def test_channel_hints_preserve_fixed_limits_and_delivery_states(monkeypatch):
    from app.services import notification_preference_service as preferences, message_governance_service as governance
    monkeypatch.setattr(preferences, "get_preferences", lambda user, cats: {"items": [{"key": "SYSTEM", "enabled": False}]})
    monkeypatch.setattr(governance, "is_in_quiet_hours", lambda: True)
    result = service.channel_settings({"userType": "TEACHER"})
    assert result["preferences"] == [{"key": "SYSTEM", "enabled": False}]
    assert {c["key"]: c["status"] for c in result["channels"]} == {
        "IN_APP": "FORCE_ON", "MINIAPP_POPUP": "READY", "SMS": "NOT_CONFIGURED", "WECHAT": "NOT_CONFIGURED",
    }
    assert result["quietHours"]["start"] == "22:00"
    assert result["quietHours"]["end"] == "07:00"
    assert result["quietHours"]["enabled"] is True
    assert result["quietHours"]["inQuietNow"] is True
    assert result["rateLimit"]["maxPerHour"] == 20
    assert "不可关闭" in result["note"]
    assert "紧急提醒照常发送" in result["quietHours"]["hint"]
    assert all("假发送" not in c["hint"] for c in result["channels"])


def test_statistics_explain_repeated_recipients_without_exposing_field_names(monkeypatch):
    rows = [SimpleNamespace(recipient_count=3, delivered_count=2, read_count=1, ack_count=1,
                            failure_count=0, status="PUBLISHED", category="BUSINESS")]
    @contextmanager
    def session():
        yield SimpleNamespace(scalars=lambda query: SimpleNamespace(all=lambda: rows))
    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "has_permission", lambda user, code: True)
    monkeypatch.setattr(service, "_tid", lambda: 1)
    result = service.statistics_summary({})
    assert result["metrics"]["recipientCount"] == 3
    assert result["metrics"]["deliveryRate"] == 66.7
    assert result["metrics"]["readRate"] == 50.0
    assert result["metrics"]["ackRate"] == 33.3
    assert "按每次发布累计" in result["denominatorNote"]
    assert "recipientCount" not in result["denominatorNote"]
    assert len(result["denominatorNote"]) <= 40
    assert result["channels"][1] == {"channel": "SMS", "status": "NOT_CONFIGURED", "label": "短信"}
