from __future__ import annotations


def _ensure_active_tenant(tenant_id: int) -> int:
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import platform_service
    from app.services.tenant_effective_state_service import get_effective_state

    db = get_sessionmaker()()
    try:
        row = db.get(Tenant, tenant_id)
        if row is None:
            db.add(Tenant(id=tenant_id, tenant_code="w3-cache", school_name="W3缓存学校", status="ACTIVE"))
        else:
            row.status = "ACTIVE"
        db.commit()
    finally:
        db.close()
    existing = platform_service.get_config_json(tenant_id, "TENANT_META") or {}
    platform_service.put_config_json(tenant_id, "TENANT_META", "-", {
        **existing,
        "status": "active",
        "packageCode": existing.get("packageCode") or "trial",
    })
    return int(get_effective_state(tenant_id, strict=True)["version"])


def test_w3_post_commit_cache_failure_returns_recovery_receipt(db_mode, monkeypatch):
    from app.services import auth_service_db
    from app.services.platform_transition_receipt_service import (
        apply_transition_with_receipt,
        recover_tenant_auth_cache,
    )
    from app.services.tenant_effective_state_service import get_effective_state

    tenant_id = 1000000000000096301
    expected_version = _ensure_active_tenant(tenant_id)
    original = auth_service_db.invalidate_tenant_subject_caches

    def fail_cache(_tenant_id):
        raise RuntimeError("redis unavailable for W3 test")

    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches", fail_cache)
    receipt = apply_transition_with_receipt(
        tenant_id,
        "disable",
        reason="W3验证提交后缓存失败",
        expected_version=expected_version,
        audit_action="PLATFORM_TENANT_DISABLE",
    )
    assert receipt["runtimeMaterialized"] is True
    assert receipt["cacheInvalidated"] is False
    assert receipt["cacheRecoveryRequired"] is True
    assert receipt["after"]["effectiveStatus"] == "disabled"
    committed_version = int(receipt["version"])
    assert committed_version > expected_version
    assert get_effective_state(tenant_id, strict=True)["effectiveStatus"] == "disabled"

    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches", original)
    recovered = recover_tenant_auth_cache(tenant_id)
    assert recovered["cacheInvalidated"] is True
    assert recovered["cacheRecoveryRequired"] is False
    assert int(recovered["version"]) == committed_version
    assert get_effective_state(tenant_id, strict=True)["effectiveStatus"] == "disabled"


def test_w3_success_receipt_is_explicit(db_mode):
    from app.services.platform_transition_receipt_service import apply_transition_with_receipt

    tenant_id = 1000000000000096302
    expected_version = _ensure_active_tenant(tenant_id)
    receipt = apply_transition_with_receipt(
        tenant_id,
        "disable",
        reason="W3验证正常缓存回执",
        expected_version=expected_version,
        audit_action="PLATFORM_TENANT_DISABLE",
    )
    assert receipt["runtimeMaterialized"] is True
    assert receipt["cacheInvalidated"] is True
    assert receipt["cacheRecoveryRequired"] is False
