"""V3 §9.2–§9.4：受限搜索范围与微信订阅 fail-closed。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.services import mobile_student_search_service as search
from app.services.notification import wechat_subscribe_service as wechat

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "mobile_student_search_service.py"
DELIVERY_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "message_channel_delivery_service.py"


# ── §9.2 受限搜索 ──

def test_short_keywords_never_reach_the_database():
    for keyword in ("", " ", "a", " x "):
        result = search.search({"userType": "STUDENT"}, keyword=keyword)
        assert result["items"] == []
        assert result["hasData"] is False


def test_overlong_keyword_is_rejected():
    with pytest.raises(AppException):
        search._normalize_keyword("x" * (search.MAX_KEYWORD_LENGTH + 1))


def test_like_metacharacters_are_escaped_so_users_cannot_widen_the_scan():
    assert search._escape_like("100%") == "100\\%"
    assert search._escape_like("a_b") == "a\\_b"
    assert search._escape_like("a\\b") == "a\\\\b"


def test_search_is_bounded_and_self_scoped():
    snapshot = search.search_contract_snapshot()
    assert snapshot["scope"] == "self-only"
    assert snapshot["pageSizeMax"] <= 20
    assert snapshot["minKeywordLength"] >= 2
    assert snapshot["windowDays"] <= 365

    source = SEARCH_SOURCE.read_text(encoding="utf-8")
    # 可见性必须复用 message_center 的 Authority，不另建 receiver 判定
    assert "message_svc.visibility_condition(current)" in source
    assert "receiver_user_id" not in source
    # 只查本人办理
    assert "CsLeave.student_id == student.id" in source
    # 必须有时间窗，不是无边界回溯
    assert "UnifiedMessage.created_at >= since" in source
    # 不得出现任何全校/跨人检索
    assert "StudentProfile" not in source


def test_search_results_carry_typed_actions_only():
    source = SEARCH_SOURCE.read_text(encoding="utf-8")
    assert "action_svc.build_message_action(" in source
    # 不允许在这里拼客户端路由
    assert "/pages/" not in source


# ── §9.3 微信订阅 fail-closed ──

def test_unregistered_scene_is_refused():
    result = wechat.send_subscribe_message(tenant_id=1, openid="o1", scene="ANYTHING")
    assert result["status"] == "SKIPPED"
    assert result["reasonCode"] == "SCENE_NOT_ALLOWED"
    assert result["retryable"] is False


def test_missing_provider_config_is_skipped_not_retried(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "WX_APPID", "", raising=False)
    monkeypatch.setattr(settings, "WX_SECRET", "", raising=False)
    result = wechat.send_subscribe_message(tenant_id=1, openid="o1", scene="CASE_RESULT")
    assert result["status"] == "SKIPPED"
    assert result["reasonCode"] == "WECHAT_NOT_CONFIGURED"
    assert result["retryable"] is False, "配置缺失重试多少次都一样，不该消耗重试预算"

    status = wechat.provider_status()
    assert status["configured"] is False
    assert set(status["missing"]) == {"WX_APPID", "WX_SECRET"}


def test_missing_openid_is_not_a_send_failure(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "WX_APPID", "wx0000000000000000", raising=False)
    monkeypatch.setattr(settings, "WX_SECRET", "secret", raising=False)
    monkeypatch.setattr(settings, "WX_SUBSCRIBE_TEMPLATE_CASE_RESULT", "tmpl-1", raising=False)
    result = wechat.send_subscribe_message(tenant_id=1, openid="", scene="CASE_RESULT")
    assert result["status"] == "SKIPPED"
    assert result["reasonCode"] == "OPENID_UNAVAILABLE"
    assert result["retryable"] is False


def test_missing_template_is_reported_per_scene(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "WX_APPID", "wx0000000000000000", raising=False)
    monkeypatch.setattr(settings, "WX_SECRET", "secret", raising=False)
    result = wechat.send_subscribe_message(tenant_id=1, openid="o1", scene="EXAM_UPCOMING")
    assert result["reasonCode"] == "TEMPLATE_NOT_CONFIGURED"
    assert result["retryable"] is False


def test_provider_exceptions_are_retryable_but_never_reported_as_sent(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "WX_APPID", "wx0000000000000000", raising=False)
    monkeypatch.setattr(settings, "WX_SECRET", "secret", raising=False)
    monkeypatch.setattr(settings, "WX_SUBSCRIBE_TEMPLATE_CASE_RESULT", "tmpl-1", raising=False)

    def boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(wechat, "_call_provider", boom)
    result = wechat.send_subscribe_message(tenant_id=1, openid="o1", scene="CASE_RESULT")
    assert result["status"] == "FAILED"
    assert result["retryable"] is True
    assert result["status"] != "SENT"


def test_delivery_queue_keeps_lease_backoff_and_dead_semantics_for_wechat():
    source = DELIVERY_SOURCE.read_text(encoding="utf-8")
    branch = source[source.index("if row.channel=='WECHAT':"):source.index("def claim_and_process_channel_deliveries")]
    # 不再无条件跳过
    assert "wechat.send_subscribe_message(" in branch
    # 保留既有 lease / backoff / DEAD
    assert "_MAX_ATTEMPTS" in branch
    assert "_backoff(" in branch
    assert "row.status='DEAD'" in branch
    assert "row.status='RETRY_WAIT'" in branch
    # 不可重试的原因不消耗重试预算
    assert "row.status='SKIPPED'" in branch


def test_student_facing_status_never_claims_enabled_without_both_sides():
    source = (REPO_ROOT / "backend" / "app" / "services" / "mobile_student_service.py").read_text(encoding="utf-8")
    block = source[source.index("def wechat_subscribe_status("):source.index("_SUBSCRIBE_SCENE_LABELS = {")]
    assert '"effective": bool(status["configured"]) and authorized' in block
    assert '"configured"' in block and '"authorized"' in block
