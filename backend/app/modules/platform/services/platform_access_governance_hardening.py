"""Final hardening layer for Platform Workforce / PAM.

Keep the canonical runtime service intact and override only two contracts that
must fail closed at the control-plane boundary:

* access-review closure requires an exact, duplicate-free decision set for the
  frozen snapshot; omitted items must never silently become KEEP;
* terminating another operator's support session is an administrative action
  and therefore additionally requires ``access.manage``.
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.platform.services import platform_access_governance_runtime as _runtime


def _review_decisions(payload: dict) -> list[dict]:
    raw = payload.get("decisions") or []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "复核决定必须是逐项列表", http_status=422)
    keys = [str(item.get("itemKey") or "").strip() for item in raw if isinstance(item, dict)]
    if len(keys) != len(raw) or any(not key for key in keys):
        raise AppException("VALIDATION_ERROR", "每条复核决定都必须包含 itemKey", http_status=422)
    if len(set(keys)) != len(keys):
        raise AppException("VALIDATION_ERROR", "复核决定存在重复 itemKey", http_status=422)
    invalid = [
        item for item in raw
        if str(item.get("decision") or "").upper() not in {"KEEP", "REVOKE"}
    ]
    if invalid:
        raise AppException("VALIDATION_ERROR", "复核决定只能是 KEEP / REVOKE", http_status=422)
    return raw


def close_access_review(review_id: str, payload: dict, *, actor: dict) -> dict:
    decisions = _review_decisions(payload)
    rows = [item for item in _runtime.list_records(_runtime.REVIEW) if str(item.get("id")) == str(review_id)]
    if not rows:
        raise AppException("DATA_NOT_FOUND", "访问复核不存在", http_status=404)
    review = rows[0]
    if str(review.get("status") or "").upper() != "OPEN":
        raise AppException("DATA_CONFLICT", "访问复核已关闭", http_status=409)

    snapshot_keys = {str(item.get("itemKey") or "") for item in (review.get("items") or [])}
    decision_keys = {str(item.get("itemKey") or "") for item in decisions}
    if snapshot_keys != decision_keys:
        missing = sorted(snapshot_keys - decision_keys)
        unknown = sorted(decision_keys - snapshot_keys)
        raise AppException(
            "ACCESS_REVIEW_DECISION_SET_MISMATCH",
            "关闭访问复核必须对冻结快照中的每一项明确 KEEP 或 REVOKE",
            http_status=409,
            details={"missingItemKeys": missing, "unknownItemKeys": unknown},
        )
    return _runtime.close_access_review(review_id, payload, actor=actor)


def terminate_record(
    config_type: str,
    record_id: str,
    *,
    tenant_id: int,
    expected_version: int,
    reason: str,
    actor: dict,
) -> dict:
    if config_type == _runtime.SUPPORT:
        rows = [
            item for item in _runtime.list_records(_runtime.SUPPORT, tenant_id=tenant_id)
            if str(item.get("id")) == str(record_id)
        ]
        if not rows:
            raise AppException("DATA_NOT_FOUND", "受控协助会话不存在", http_status=404)
        owner = str(rows[0].get("operatorUserId") or "")
        actor_id = str(actor.get("userId") or "")
        if owner and owner != actor_id:
            _runtime.assert_platform_capability(actor, "access.manage")
    return _runtime.terminate_record(
        config_type,
        record_id,
        tenant_id=tenant_id,
        expected_version=expected_version,
        reason=reason,
        actor=actor,
    )


for _name in dir(_runtime):
    if _name.startswith("_") or _name in globals():
        continue
    globals()[_name] = getattr(_runtime, _name)


def __getattr__(name: str):
    return getattr(_runtime, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_runtime)))
