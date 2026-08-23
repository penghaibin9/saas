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


def test_website_lead_public_endpoint_forwards_expected_fields_without_db(monkeypatch):
    seen = {}

    monkeypatch.setattr(notification_api, "allow_website_lead", lambda _ip: (True, "OK"))

    def fake_send(body):
        seen.update(body.model_dump())
        return {"status": "SENT"}

    monkeypatch.setattr(notification_api, "send_website_lead_sms", fake_send)

    response = TestClient(_app()).post(
        "/api/v1/notification/website-lead",
        json={
            "school_name": "湖南某职业学院",
            "contact_name": "张老师",
            "phone": "13800138000",
            "interest": "岗位实习",
            "message": "想了解部署和报价",
            "website": "",
            "source_path": "/contact",
        },
    )

    assert response.status_code == 200
    assert seen["school_name"] == "湖南某职业学院"
    assert seen["contact_name"] == "张老师"
    assert seen["phone"] == "13800138000"
    assert seen["interest"] == "岗位实习"
    assert seen["message"] == "想了解部署和报价"


def test_website_lead_honeypot_returns_success_without_sending(monkeypatch):
    called = {"send": 0}
    monkeypatch.setattr(
        notification_api,
        "send_website_lead_sms",
        lambda _body: called.__setitem__("send", called["send"] + 1),
    )

    response = TestClient(_app()).post(
        "/api/v1/notification/website-lead",
        json={
            "school_name": "湖南某职业学院",
            "contact_name": "张老师",
            "phone": "13800138000",
            "interest": "教务系统",
            "message": "",
            "website": "https://spam.example",
        },
    )

    assert response.status_code == 200
    assert called["send"] == 0


def test_website_lead_rejects_invalid_mobile_number(monkeypatch):
    response = TestClient(_app()).post(
        "/api/v1/notification/website-lead",
        json={
            "school_name": "湖南某职业学院",
            "contact_name": "张老师",
            "phone": "12345",
            "interest": "学工中心",
        },
    )
    assert response.status_code == 422


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
