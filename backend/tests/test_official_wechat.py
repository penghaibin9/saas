from __future__ import annotations

import hashlib

import pytest

from app.services.notification import official_wechat


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    official_wechat._reset_local_cache_for_tests()
    monkeypatch.setenv("WECHAT_OFFICIAL_JS_SDK_ENABLED", "true")
    monkeypatch.setenv("WECHAT_OFFICIAL_APP_ID", "wx-official-test")
    monkeypatch.setenv("WECHAT_OFFICIAL_APP_SECRET", "secret-not-for-browser")
    monkeypatch.setenv("WECHAT_OFFICIAL_ALLOWED_HOSTS", "hnyueke.com,www.hnyueke.com")
    monkeypatch.setattr(official_wechat, "cache_get_json", lambda _key: None)
    monkeypatch.setattr(official_wechat, "cache_set_json", lambda _key, _value, _ttl: False)


def test_sign_url_only_accepts_configured_https_official_hosts():
    assert (
        official_wechat.normalize_signable_url("https://hnyueke.com/products/internship?from=wx#screens")
        == "https://hnyueke.com/products/internship?from=wx"
    )
    with pytest.raises(ValueError):
        official_wechat.normalize_signable_url("http://hnyueke.com/")
    with pytest.raises(ValueError):
        official_wechat.normalize_signable_url("https://evil.example/")


def test_signature_matches_wechat_jssdk_algorithm(monkeypatch):
    monkeypatch.setattr(official_wechat, "get_jsapi_ticket", lambda: "ticket-123")
    result = official_wechat.build_js_sdk_signature(
        "https://hnyueke.com/products/graduation#screens",
        timestamp=1787358000,
        nonce_str="nonce-abc",
    )
    source = (
        "jsapi_ticket=ticket-123&noncestr=nonce-abc&timestamp=1787358000"
        "&url=https://hnyueke.com/products/graduation"
    )
    assert result == {
        "appId": "wx-official-test",
        "timestamp": 1787358000,
        "nonceStr": "nonce-abc",
        "signature": hashlib.sha1(source.encode("utf-8")).hexdigest(),
        "url": "https://hnyueke.com/products/graduation",
    }


def test_access_token_and_ticket_use_short_lived_cache(monkeypatch):
    calls = []

    def fake_fetch(url, *, params):
        calls.append((url, params))
        if url == official_wechat.ACCESS_TOKEN_URL:
            return {"access_token": "token-1", "expires_in": 7200}
        return {"errcode": 0, "errmsg": "ok", "ticket": "ticket-1", "expires_in": 7200}

    monkeypatch.setattr(official_wechat, "_fetch_json", fake_fetch)
    assert official_wechat.get_jsapi_ticket() == "ticket-1"
    assert official_wechat.get_jsapi_ticket() == "ticket-1"
    assert len(calls) == 2
    assert calls[0][1]["appid"] == "wx-official-test"
    assert calls[1][1]["type"] == "jsapi"
