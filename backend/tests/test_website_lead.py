from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.v1 import notification as notification_api
from app.core.tenant_context import resolve_tenant_code
from app.services.notification import website_lead as lead_service


def _app():
    app = FastAPI()
    app.include_router(notification_api.router, prefix="/api/v1")
    return app


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("hnyueke.com", 443),
        }
    )


def test_public_website_notification_paths_are_tenant_neutral():
    for path in (
        "/api/v1/notification/website-lead",
        "/api/v1/notification/website-wechat-signature",
    ):
        assert resolve_tenant_code(_request(path)) == ""
        assert resolve_tenant_code(_request(f"{path}/")) == ""


def test_school_notification_router_no_longer_serves_website_endpoints():
    # The active implementation and validation are tested in website/backend/tests/test_integrations.py.
    client = TestClient(_app())
    assert client.post('/api/v1/notification/website-lead', json={}).status_code == 404
    assert client.get('/api/v1/notification/website-wechat-signature', params={'url': 'https://www.hnyueke.com/'}).status_code == 404
    assert {route.path for route in notification_api.router.routes} == {
        '/notification/send-test', '/notification/logs'
    }


def test_school_application_has_no_website_news_or_public_marketing_api():
    from app.main import app
    paths = app.openapi()['paths']
    assert '/api/v1/notification/send-test' in paths
    assert '/api/v1/notification/logs' in paths
    assert not any(path.startswith('/news') or 'website-news' in path for path in paths)
    assert '/api/v1/notification/website-lead' not in paths
    assert '/api/v1/notification/website-wechat-signature' not in paths


def test_send_website_lead_sms_calls_provider_directly_without_persistence(monkeypatch):
    sent = {}

    class FakeProvider:
        name = "tencent"

        def send(self, phone, template_id, params):
            sent["phone"] = phone
            sent["template_id"] = template_id
            sent["params"] = params
            return SimpleNamespace(success=True, retryable=False, provider_code="Ok")

    monkeypatch.setenv("SMS_TEMPLATE_WEBSITE_LEAD", "1234567")
    monkeypatch.setenv("WEBSITE_LEAD_NOTIFY_PHONE", "13549666867")
    monkeypatch.setattr(lead_service, "_sms_enabled", lambda: True)
    monkeypatch.setattr(lead_service, "get_provider", lambda: FakeProvider())

    payload = lead_service.WebsiteLeadRequest(
        school_name="湖南某职业学院",
        contact_name="李老师",
        phone="13900139000",
        interest="毕业设计",
        message="希望预约产品演示",
    )
    result = lead_service.send_website_lead_sms(payload)

    assert result == {"status": "SENT"}
    assert sent["phone"] == "13549666867"
    assert sent["template_id"] == "1234567"
    assert sent["params"] == {
        "school": "湖南某职业学院",
        "contact": "李老师",
        "phone": "13900139000",
        "interest": "毕业设计",
        "message": "希望预约产品演示",
    }
