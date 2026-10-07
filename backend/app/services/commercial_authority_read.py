"""Strict read adapter for the installed commercial authority, not another ledger.

Keep explicit business denials distinct from infrastructure failures. Read the
full authority envelope because the M2 compatibility projection deliberately
collapses outages to an all-false feature map. Neither an exception nor an
unverified/faulted envelope may grant access or populate a request snapshot.
"""
from __future__ import annotations

import logging

from app.core.exceptions import AppException

_LOG = logging.getLogger("platform.commercial-authority-read")
_VERIFIED_SOURCES = frozenset({
    "TRIAL", "CONTROLLED_EXCEPTION", "PAID_ORDER", "LEGACY_PAID_ORDER", "MODULE_V2",
})
_DENIED_SOURCES = frozenset({
    "PACKAGE_NOT_FOUND", "COMMERCIAL_ORDER_REQUIRED",
    "CONTROLLED_EXCEPTION_TENANT_INACTIVE", "CONTROLLED_EXCEPTION_EVIDENCE_MISSING",
    "PAID_ORDER_EVIDENCE_MISMATCH", "PAID_ORDER_ACTIVATION_REPAIR_REQUIRED",
    "PAID_ORDER_SERVICE_NOT_STARTED", "PAID_ORDER_SERVICE_EXPIRED",
    "MODULE_V2_TENANT_INACTIVE",
})


def _unavailable(tenant_id: int, error_type: str) -> AppException:
    # Never log SQL, connection strings or underlying exception messages here.
    _LOG.error("commercial_authority_unavailable tenant=%s error_type=%s", tenant_id, error_type)
    return AppException(
        "AUTHORITY_UNAVAILABLE",
        "商业授权服务暂时不可用，操作未执行，请稍后重试",
        details={"authority": "commercialEntitlement", "retryable": True},
        http_status=503,
    )


def effective_features(tenant_id: int) -> dict[str, bool]:
    """Read once from the canonical authority; no fallback, cache or mutation."""
    try:
        if isinstance(tenant_id, bool):
            raise ValueError("boolean tenant")
        tid = int(tenant_id)
        if tid <= 0 or str(tid) != str(tenant_id):
            raise ValueError("invalid tenant")
    except (TypeError, ValueError, OverflowError):
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少有效租户上下文，已拒绝操作", http_status=400) from None
    try:
        # app.services installs the shared adapter for HTTP, workers and CLI.
        # Reading only effective_features would hide M2's UNAVAILABLE envelope.
        from app.services.commercial_entitlement_authority_service import commercial_state

        state = commercial_state(tid)
    except AppException as exc:
        if exc.http_status < 500:
            raise
        raise _unavailable(tid, type(exc).__name__) from exc
    except Exception as exc:
        raise _unavailable(tid, type(exc).__name__) from exc
    if not isinstance(state, dict) or type(state.get("verified")) is not bool:
        raise _unavailable(tid, "InvalidAuthoritySnapshot")
    source = state.get("authoritySource")
    features = state.get("features")
    if not isinstance(source, str) or not isinstance(features, dict) or any(
        not isinstance(key, str) or type(value) is not bool for key, value in features.items()
    ):
        raise _unavailable(tid, "InvalidFeatureSnapshot")
    if state["verified"]:
        if source not in _VERIFIED_SOURCES:
            raise _unavailable(tid, "UnknownVerifiedAuthority")
    elif source not in _DENIED_SOURCES or any(features.values()):
        # Includes COMMERCIAL_READER_UNAVAILABLE, MODULE_V2_UNAVAILABLE, unknown
        # versions, and contradictory grants in an unverified response.
        raise _unavailable(tid, "UnverifiedAuthoritySnapshot")
    return dict(features)


def feature_enabled(tenant_id: int, key: str) -> bool:
    """Unknown/unpurchased remains False; unavailable authority raises 503."""
    from app.core.module_registry import resolve_feature_key
    from app.services.platform_defaults import FEATURE_KEYS

    feature = resolve_feature_key(key) or (key if key in FEATURE_KEYS else None)
    if feature is None or feature not in FEATURE_KEYS:
        return False
    return effective_features(tenant_id).get(feature, False)
