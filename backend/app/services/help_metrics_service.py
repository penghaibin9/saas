"""Help Center V3-08 质量/自助率指标。

复用既有 append-only ``t_security_audit_log``，不新增迁移：
- 搜索仅保存不可逆指纹、长度与命中数，不保存用户自由文本；
- 文章浏览与“已解决/未解决”反馈只保存 help id 和低敏维度；
- 真正“无需人工解决率”在未打通工单/人工升级链前明确不可用，不用反馈率冒充；
- 小程序 WebView 使用 10 分钟、仅 Help Metrics 可验证的 HMAC capability，不把主登录 token 放进 URL。
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
from hashlib import sha256
import hmac
import json
import re
import time

from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import get_current_user_ctx, set_current_user, set_tenant
from app.core.exceptions import AppException, unauthorized
from app.db.session import db_enabled, get_sessionmaker
from app.models import SecurityAuditLog
from app.services import db_service

HELP_METRIC_RESOURCE = "HELP_CENTER"
HELP_METRIC_ACTIONS = {
    "SEARCH_HIT": "HELP_SEARCH_HIT",
    "SEARCH_NO_RESULT": "HELP_SEARCH_NO_RESULT",
    "ARTICLE_VIEW": "HELP_ARTICLE_VIEW",
    "HELPFUL": "HELP_FEEDBACK_HELPFUL",
    "NOT_HELPFUL": "HELP_FEEDBACK_NOT_HELPFUL",
}
_SEARCH_ACTIONS = {HELP_METRIC_ACTIONS["SEARCH_HIT"], HELP_METRIC_ACTIONS["SEARCH_NO_RESULT"]}
_FEEDBACK_ACTIONS = {HELP_METRIC_ACTIONS["HELPFUL"], HELP_METRIC_ACTIONS["NOT_HELPFUL"]}
_ALL_ACTIONS = set(HELP_METRIC_ACTIONS.values())
_SAFE_TOKEN = re.compile(r"[^0-9A-Za-z_.:\-\u4e00-\u9fff]+")
_PUBLIC_METRIC_TOKEN_VERSION = "hm1"
PUBLIC_METRIC_TOKEN_TTL_SECONDS = 600

# 这些是跃科 Help Center 的运营目标，不是拿来伪造当前达标率的静态数字。
QUALITY_TARGETS = {
    "searchHitRate": 0.80,
    "explicitResolutionRate": 0.70,
    "minSearchSample": 20,
    "minFeedbackSample": 10,
}


def _safe_token(value: object, *, max_length: int = 80) -> str:
    text = _SAFE_TOKEN.sub("", str(value or "").strip())
    return text[:max_length]


def _query_fingerprint(value: object) -> tuple[str, int]:
    normalized = " ".join(str(value or "").strip().lower().split())[:200]
    if not normalized:
        return "", 0
    digest = sha256(("help-search:v1:" + normalized).encode("utf-8")).hexdigest()
    return digest, len(normalized)


def _actor_db_id() -> int | None:
    user = get_current_user_ctx() or {}
    raw = str(user.get("userId") or "")
    if raw.startswith("db-") and raw[3:].isdigit():
        return int(raw[3:])
    if raw.isdigit():
        return int(raw)
    return None


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _status(value: float | None, sample: int, *, minimum: int, target: float) -> str:
    if sample < minimum or value is None:
        return "INSUFFICIENT_DATA"
    return "HEALTHY" if value >= target else "NEEDS_ATTENTION"


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _public_metric_signature(encoded_payload: str) -> str:
    signing_input = f"{_PUBLIC_METRIC_TOKEN_VERSION}.{encoded_payload}".encode("utf-8")
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, sha256).digest()
    return _b64url_encode(digest)


def issue_public_metric_session(user: dict | None = None) -> dict:
    """签发短时、最小权限 capability，供已登录小程序把租户上下文带入公开帮助页。"""
    actor = user or get_current_user_ctx() or {}
    tenant_id = str(actor.get("tenantId") or "").strip()
    user_id = str(actor.get("userId") or "").strip()
    if not tenant_id or not tenant_id.isdigit() or not user_id:
        raise AppException("VALIDATION_ERROR", "当前登录上下文缺少可用的学校或用户标识")

    payload = {
        "purpose": "HELP_METRICS_PUBLIC",
        "tenantId": tenant_id,
        "tenantCode": _safe_token(actor.get("tenantCode"), max_length=60),
        "userId": _safe_token(user_id, max_length=80),
        "exp": int(time.time()) + PUBLIC_METRIC_TOKEN_TTL_SECONDS,
    }
    encoded = _b64url_encode(json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
    token = f"{_PUBLIC_METRIC_TOKEN_VERSION}.{encoded}.{_public_metric_signature(encoded)}"
    return {"metricToken": token, "expiresIn": PUBLIC_METRIC_TOKEN_TTL_SECONDS}


def bind_public_metric_session(token: str) -> dict:
    """校验 capability 并只为当前 Help Metrics 请求绑定租户/操作者上下文。"""
    parts = str(token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != _PUBLIC_METRIC_TOKEN_VERSION:
        raise unauthorized("帮助指标会话无效或已失效")
    encoded, signature = parts[1], parts[2]
    expected = _public_metric_signature(encoded)
    if not hmac.compare_digest(signature, expected):
        raise unauthorized("帮助指标会话无效或已失效")
    try:
        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise unauthorized("帮助指标会话无效或已失效") from exc

    if payload.get("purpose") != "HELP_METRICS_PUBLIC":
        raise unauthorized("帮助指标会话用途无效")
    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError) as exc:
        raise unauthorized("帮助指标会话无效或已失效") from exc
    if expires_at <= int(time.time()):
        raise unauthorized("帮助指标会话已过期，请重新打开帮助中心")

    tenant_id = str(payload.get("tenantId") or "").strip()
    tenant_code = _safe_token(payload.get("tenantCode"), max_length=60)
    user_id = _safe_token(payload.get("userId"), max_length=80)
    if not tenant_id.isdigit() or not user_id:
        raise unauthorized("帮助指标会话缺少学校或用户上下文")

    user = {
        "userId": user_id,
        "tenantId": tenant_id,
        "tenantCode": tenant_code,
        "helpMetricCapability": True,
    }
    set_current_user(user)
    set_tenant({
        "tenantId": tenant_id,
        "tenantCode": tenant_code,
        "tenantName": "",
        "status": "ACTIVE",
    })
    return user


def record_event(*, event_type: str, article_id: str = "", query: str = "",
                 result_count: int | None = None, source: str = "", category: str = "",
                 role_group: str = "") -> dict:
    """持久化一条低敏帮助质量事件；数据库不可用时拒绝假装记录成功。"""
    if not db_enabled():
        raise AppException("SERVER_ERROR", "帮助质量统计存储不可用")

    kind = str(event_type or "").strip().upper()
    article = _safe_token(article_id, max_length=100)
    detail = {
        "schemaVersion": 1,
        "source": _safe_token(source, max_length=40) or "unknown",
        "category": _safe_token(category, max_length=80),
        "roleGroup": _safe_token(role_group, max_length=60),
    }

    if kind == "SEARCH":
        count = max(0, min(int(result_count or 0), 1000))
        fingerprint, query_length = _query_fingerprint(query)
        if not fingerprint:
            raise AppException("VALIDATION_ERROR", "搜索指标必须包含非空查询")
        detail.update({
            "queryFingerprint": fingerprint,
            "queryLength": query_length,
            "resultCount": count,
        })
        action = HELP_METRIC_ACTIONS["SEARCH_HIT"] if count > 0 else HELP_METRIC_ACTIONS["SEARCH_NO_RESULT"]
        resource_id = None
    elif kind == "ARTICLE_VIEW":
        if not article:
            raise AppException("VALIDATION_ERROR", "文章浏览指标缺少 helpId")
        action = HELP_METRIC_ACTIONS["ARTICLE_VIEW"]
        resource_id = article
    elif kind in {"HELPFUL", "NOT_HELPFUL"}:
        if not article:
            raise AppException("VALIDATION_ERROR", "文章反馈指标缺少 helpId")
        action = HELP_METRIC_ACTIONS[kind]
        resource_id = article
    else:
        raise AppException("VALIDATION_ERROR", "不支持的帮助质量事件")

    Session = get_sessionmaker()
    with Session() as db:
        # 同一登录用户对同一文章每天只计一次明确反馈，避免连续点击污染分母。
        if action in _FEEDBACK_ACTIONS:
            actor_id = _actor_db_id()
            if actor_id is not None:
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                exists = db.scalar(select(func.count(SecurityAuditLog.id)).where(
                    SecurityAuditLog.tenant_id == db_service._tid(),
                    SecurityAuditLog.operator_id == actor_id,
                    SecurityAuditLog.resource == HELP_METRIC_RESOURCE,
                    SecurityAuditLog.resource_id == article,
                    SecurityAuditLog.action.in_(_FEEDBACK_ACTIONS),
                    SecurityAuditLog.created_at >= today,
                )) or 0
                if exists:
                    return {"recorded": False, "reason": "ALREADY_RECORDED"}

        db_service.audit_insert_in_session(
            db, action, HELP_METRIC_RESOURCE, detail, "SUCCESS", resource_id=resource_id
        )
        db.commit()
    return {"recorded": True, "action": action}


def summary(*, window_days: int = 30) -> dict:
    """返回当前租户真实事件汇总；无样本时返回 null 比率，不伪造 0%/100%。"""
    if not db_enabled():
        raise AppException("SERVER_ERROR", "帮助质量统计存储不可用")
    days = max(1, min(int(window_days or 30), 90))
    start = datetime.utcnow() - timedelta(days=days)
    Session = get_sessionmaker()
    with Session() as db:
        rows = db.execute(select(
            SecurityAuditLog.action,
            func.count(SecurityAuditLog.id),
        ).where(
            SecurityAuditLog.tenant_id == db_service._tid(),
            SecurityAuditLog.resource == HELP_METRIC_RESOURCE,
            SecurityAuditLog.action.in_(_ALL_ACTIONS),
            SecurityAuditLog.created_at >= start,
        ).group_by(SecurityAuditLog.action)).all()

    counts = {str(action): int(count or 0) for action, count in rows}
    search_hits = counts.get(HELP_METRIC_ACTIONS["SEARCH_HIT"], 0)
    search_misses = counts.get(HELP_METRIC_ACTIONS["SEARCH_NO_RESULT"], 0)
    article_views = counts.get(HELP_METRIC_ACTIONS["ARTICLE_VIEW"], 0)
    helpful = counts.get(HELP_METRIC_ACTIONS["HELPFUL"], 0)
    not_helpful = counts.get(HELP_METRIC_ACTIONS["NOT_HELPFUL"], 0)
    searches = search_hits + search_misses
    feedback = helpful + not_helpful
    hit_rate = _ratio(search_hits, searches)
    resolution_rate = _ratio(helpful, feedback)

    return {
        "windowDays": days,
        "asOf": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "searches": searches,
        "searchHits": search_hits,
        "searchNoResults": search_misses,
        "searchHitRate": hit_rate,
        "articleViews": article_views,
        "helpfulVotes": helpful,
        "notHelpfulVotes": not_helpful,
        "feedbackVotes": feedback,
        "explicitResolutionRate": resolution_rate,
        "trueSelfServiceResolutionRate": None,
        "metricScope": "FEEDBACK_ONLY",
        "quality": {
            "search": _status(hit_rate, searches,
                              minimum=QUALITY_TARGETS["minSearchSample"],
                              target=QUALITY_TARGETS["searchHitRate"]),
            "resolution": _status(resolution_rate, feedback,
                                  minimum=QUALITY_TARGETS["minFeedbackSample"],
                                  target=QUALITY_TARGETS["explicitResolutionRate"]),
        },
        "targets": QUALITY_TARGETS,
        "definitions": {
            "searchHitRate": "有至少 1 条 verified-only 结果的搜索 / 全部搜索",
            "explicitResolutionRate": "用户明确点击“已解决” / 全部已解决+未解决反馈",
            "trueSelfServiceResolutionRate": "需打通真实人工升级/工单闭环后才能计算，当前不提供假值",
        },
    }