"""Stage D deterministic academic DecisionTrace foundation.

DecisionTrace explains a business decision that has already been made. It is not a
rule engine and it never changes eligibility, graduation conclusions, numeric values,
or remediation. The first production scope is SELECTION + GRADUATION and intentionally
uses no LLM: business rule -> DecisionTrace JSON -> deterministic zh-CN renderer.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.core.exceptions import AppException

from ..decision_text.zh_CN import GRADUATION_RULE_MESSAGES, RULE_MESSAGES, SELECTION_RULE_MESSAGES

SCHEMA_VERSION = "1.0"
SELECTION_RULE_CODES = frozenset(SELECTION_RULE_MESSAGES)
GRADUATION_RULE_CODES = frozenset(GRADUATION_RULE_MESSAGES)
RULE_CODES_BY_DOMAIN = {
    "SELECTION": SELECTION_RULE_CODES,
    "GRADUATION": GRADUATION_RULE_CODES,
}
_AUDIENCES = {"student", "teacher", "admin"}
_TRACE_NAMESPACE = uuid.UUID("d277fe7d-6722-5a0f-91d7-bfa46befda86")


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _plain(value: Any):
    """Return JSON-safe primitives only; reject opaque application/model objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    raise AppException("DATA_CONFLICT", "DecisionTrace 包含不可序列化的内部对象，已拒绝输出", http_status=409)


def _resolution_list(value) -> list[dict]:
    rows = []
    for item in value or []:
        if not isinstance(item, dict):
            raise AppException("DATA_CONFLICT", "DecisionTrace resolution 必须由业务代码提供结构化对象", http_status=409)
        code = str(item.get("code") or "").strip()
        label = str(item.get("label") or "").strip()
        if not code or not label:
            raise AppException("DATA_CONFLICT", "DecisionTrace resolution 缺少 code/label", http_status=409)
        row = {"code": code, "label": label}
        if item.get("route") not in (None, ""):
            row["route"] = str(item["route"])
        if item.get("params") is not None:
            row["params"] = _plain(item["params"])
        rows.append(row)
    return rows


def build_decision_trace(
    *,
    domain: str,
    action: str,
    decision: str,
    rule_code: str,
    subject: dict | None = None,
    target: dict | None = None,
    failed_nodes: list[dict] | None = None,
    passed_nodes: list[dict] | None = None,
    available_resolutions: list[dict] | None = None,
    evaluated_at: datetime | str | None = None,
    rule_version: str | int | None = None,
) -> dict:
    """Build a stable machine trace for an already-made academic decision.

    ``available_resolutions`` is mandatory-by-origin rather than mandatory-by-count:
    an empty list is valid when business code has no approved next action. The renderer
    must never fabricate one.
    """
    domain = str(domain or "").upper().strip()
    rule_code = str(rule_code or "").upper().strip()
    if domain not in RULE_CODES_BY_DOMAIN or rule_code not in RULE_CODES_BY_DOMAIN[domain]:
        raise AppException("DATA_CONFLICT", f"未注册的 DecisionTrace 规则：{domain}/{rule_code}", http_status=409)
    action = str(action or "").upper().strip()
    decision = str(decision or "").upper().strip()
    if not action or not decision:
        raise AppException("DATA_CONFLICT", "DecisionTrace 缺少 action/decision", http_status=409)

    at = evaluated_at or datetime.utcnow()
    at_text = at.isoformat() if isinstance(at, datetime) else str(at)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "domain": domain,
        "action": action,
        "decision": decision,
        "ruleCode": rule_code,
        "ruleVersion": str(rule_version) if rule_version not in (None, "") else None,
        "subject": _plain(subject or {}),
        "target": _plain(target or {}),
        "failedNodes": _plain(failed_nodes or []),
        "passedNodes": _plain(passed_nodes or []),
        "availableResolutions": _resolution_list(available_resolutions),
        "evaluatedAt": at_text,
    }
    payload["traceId"] = str(uuid.uuid5(_TRACE_NAMESPACE, _json(payload)))
    return payload


def validate_decision_trace(trace: dict) -> dict:
    """Fail closed if an external/loaded trace does not satisfy the Stage D v1 schema."""
    if not isinstance(trace, dict):
        raise AppException("DATA_CONFLICT", "DecisionTrace 必须是对象", http_status=409)
    required = {
        "schemaVersion", "traceId", "domain", "action", "decision", "ruleCode",
        "ruleVersion", "subject", "target", "failedNodes", "passedNodes",
        "availableResolutions", "evaluatedAt",
    }
    missing = sorted(required - set(trace))
    if missing:
        raise AppException("DATA_CONFLICT", f"DecisionTrace 缺少字段：{','.join(missing)}", http_status=409)
    if trace.get("schemaVersion") != SCHEMA_VERSION:
        raise AppException("DATA_CONFLICT", "DecisionTrace schemaVersion 不受支持", http_status=409)
    domain = str(trace.get("domain") or "").upper()
    code = str(trace.get("ruleCode") or "").upper()
    if domain not in RULE_CODES_BY_DOMAIN or code not in RULE_CODES_BY_DOMAIN[domain]:
        raise AppException("DATA_CONFLICT", "DecisionTrace ruleCode/domain 不匹配", http_status=409)
    try:
        uuid.UUID(str(trace.get("traceId")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AppException("DATA_CONFLICT", "DecisionTrace traceId 非法", http_status=409) from exc
    _resolution_list(trace.get("availableResolutions"))
    _plain(trace)
    return trace


def render_zh_cn(trace: dict, *, audience: str = "student") -> dict:
    """Render deterministic human-readable copy without creating new remedies."""
    trace = validate_decision_trace(trace)
    audience = str(audience or "student").lower().strip()
    if audience not in _AUDIENCES:
        raise AppException("VALIDATION_ERROR", "DecisionTrace audience 非法")
    domain = trace["domain"]
    decision = trace["decision"]
    denied = decision in {"DENIED", "BLOCKED", "FAILED", "ABNORMAL"}
    if domain == "SELECTION":
        title = "暂时无法选课" if denied else "选课规则已核验"
    else:
        title = "毕业资格存在待处理项" if denied else "毕业资格规则已核验"
    resolutions = trace.get("availableResolutions") or []
    out = {
        "title": title,
        "reason": RULE_MESSAGES[trace["ruleCode"]],
        "nextStep": resolutions[0]["label"] if resolutions else None,
        "ruleCode": trace["ruleCode"],
    }
    # Student output intentionally hides internal subject/target IDs and trace metadata.
    # Teacher/admin may need them for support and audit troubleshooting.
    if audience in {"teacher", "admin"}:
        out.update({
            "traceId": trace["traceId"],
            "ruleVersion": trace.get("ruleVersion"),
            "evaluatedAt": trace["evaluatedAt"],
            "target": trace.get("target") or {},
        })
    return out
