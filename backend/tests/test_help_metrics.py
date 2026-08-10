"""Help Center V3-08 真实指标 API / MySQL 回归。"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import SecurityAuditLog


TENANT_ID = 1000000000000000001


def _data(response):
    payload = response.json()
    assert payload["code"] == 0, payload
    return payload["data"]


def test_help_search_metric_real_mysql_roundtrip(client, auth_headers, db_mode):
    query = "成绩为什么提交不了 409"
    response = client.post(
        "/api/v1/help/metrics/events",
        headers=auth_headers,
        json={
            "eventType": "SEARCH",
            "query": query,
            "resultCount": 3,
            "source": "pytest",
            "category": "教务",
            "roleGroup": "school-admin",
        },
    )
    assert response.status_code == 200, response.text
    data = _data(response)
    assert data == {"recorded": True, "action": "HELP_SEARCH_HIT"}

    db = get_sessionmaker()()
    try:
        row = db.scalars(
            select(SecurityAuditLog)
            .where(
                SecurityAuditLog.tenant_id == TENANT_ID,
                SecurityAuditLog.resource == "HELP_CENTER",
                SecurityAuditLog.action == "HELP_SEARCH_HIT",
            )
            .order_by(SecurityAuditLog.id.desc())
            .limit(1)
        ).first()
        assert row is not None
        detail = row.detail_json or {}
        assert detail["resultCount"] == 3
        assert detail["queryLength"] == len(query)
        assert len(detail["queryFingerprint"]) == 64
        # 自由文本不得进入 append-only 审计明文。
        assert query not in json.dumps(detail, ensure_ascii=False)
        assert "query" not in detail
    finally:
        db.close()

    summary = client.get("/api/v1/help/metrics/summary?days=30", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    metrics = _data(summary)
    assert metrics["searches"] == 1
    assert metrics["searchHits"] == 1
    assert metrics["searchNoResults"] == 0
    assert metrics["searchHitRate"] == 1.0
    assert metrics["trueSelfServiceResolutionRate"] is None
    assert metrics["metricScope"] == "FEEDBACK_ONLY"


def test_help_metric_feedback_is_real_but_not_true_self_service_rate(client, auth_headers, db_mode):
    article_id = "tr-v3-version-conflict-409"
    for event_type in ("ARTICLE_VIEW", "HELPFUL"):
        response = client.post(
            "/api/v1/help/metrics/events",
            headers=auth_headers,
            json={
                "eventType": event_type,
                "articleId": article_id,
                "source": "pytest",
                "category": "高频故障",
                "roleGroup": "school-admin",
            },
        )
        assert response.status_code == 200, response.text
        assert _data(response)["recorded"] is True

    summary = client.get("/api/v1/help/metrics/summary?days=30", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    metrics = _data(summary)
    assert metrics["articleViews"] == 1
    assert metrics["helpfulVotes"] == 1
    assert metrics["notHelpfulVotes"] == 0
    assert metrics["feedbackVotes"] == 1
    assert metrics["explicitResolutionRate"] == 1.0
    assert metrics["trueSelfServiceResolutionRate"] is None


def test_public_help_metric_capability_records_without_exposing_main_login_token(client, auth_headers, db_mode):
    issued = client.post("/api/v1/help/metrics/public-session", headers=auth_headers)
    assert issued.status_code == 200, issued.text
    session = _data(issued)
    token = session["metricToken"]
    assert token.startswith("hm1.")
    assert session["expiresIn"] == 600

    public_headers = {"Authorization": f"Bearer {token}"}
    recorded = client.post(
        "/api/v1/help/metrics/public/events",
        headers=public_headers,
        json={
            "eventType": "SEARCH",
            "query": "成绩 409",
            "resultCount": 2,
            "source": "miniapp",
            "category": "教务",
            "roleGroup": "student",
        },
    )
    assert recorded.status_code == 200, recorded.text
    assert _data(recorded) == {"recorded": True, "action": "HELP_SEARCH_HIT"}

    db = get_sessionmaker()()
    try:
        row = db.scalars(
            select(SecurityAuditLog)
            .where(
                SecurityAuditLog.tenant_id == TENANT_ID,
                SecurityAuditLog.resource == "HELP_CENTER",
                SecurityAuditLog.action == "HELP_SEARCH_HIT",
            )
            .order_by(SecurityAuditLog.id.desc())
            .limit(1)
        ).first()
        assert row is not None
        assert (row.detail_json or {}).get("source") == "miniapp"
    finally:
        db.close()

    # capability 不是 JWT 主登录令牌，不能拿去读学校级汇总或访问其它 authenticated API。
    denied = client.get("/api/v1/help/metrics/summary?days=30", headers=public_headers)
    assert denied.status_code == 401, denied.text

    prefix, payload, signature = token.split(".")
    tampered = f"{prefix}.{payload}.{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}"
    rejected = client.post(
        "/api/v1/help/metrics/public/events",
        headers={"Authorization": f"Bearer {tampered}"},
        json={"eventType": "ARTICLE_VIEW", "articleId": "aa-card-grade-entry"},
    )
    assert rejected.status_code == 401, rejected.text


def test_help_metric_api_fails_closed_on_invalid_or_unauthorized_requests(client, auth_headers, db_mode):
    blank = client.post(
        "/api/v1/help/metrics/events",
        headers=auth_headers,
        json={"eventType": "SEARCH", "query": "   ", "resultCount": 0},
    )
    assert blank.status_code == 400, blank.text

    counselor = _data(client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "counselor01", "password": "x"},
    ))
    counselor_headers = {"Authorization": f"Bearer {counselor['accessToken']}"}
    denied = client.get("/api/v1/help/metrics/summary?days=30", headers=counselor_headers)
    assert denied.status_code == 403, denied.text