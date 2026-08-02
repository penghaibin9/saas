from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AppException
from app.services.tenant_effective_state_service import effective_state_from_records


def test_archived_row_is_hard_stop_even_when_meta_is_active():
    result = effective_state_from_records(
        row_status="ARCHIVED",
        meta={"status": "active"},
    )

    assert result["effectiveStatus"] == "archived"
    assert result["readonly"] is True
    assert result["writable"] is False
    assert result["mismatch"] is True


def test_provisioning_row_cannot_be_used_as_active_tenant():
    result = effective_state_from_records(
        row_status="PROVISIONING",
        meta={"status": "active"},
    )

    assert result["effectiveStatus"] == "provisioning"
    assert result["writable"] is False
    assert result["mismatch"] is True


def test_disabled_metadata_never_becomes_writable_under_active_row():
    result = effective_state_from_records(
        row_status="ACTIVE",
        meta={"status": "disabled"},
    )

    assert result["effectiveStatus"] == "disabled"
    assert result["writable"] is False
    assert result["mismatch"] is True


def test_timezone_aware_expiration_is_evaluated_in_utc():
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    result = effective_state_from_records(
        row_status="ACTIVE",
        meta={"status": "active", "expireAt": expired_at.isoformat()},
    )

    assert result["effectiveStatus"] == "expired"
    assert result["readonly"] is True


def test_unknown_metadata_state_is_rejected_in_strict_mode():
    with pytest.raises(AppException) as exc:
        effective_state_from_records(
            row_status="ACTIVE",
            meta={"status": "unknown-commercial-state"},
        )

    assert exc.value.code == "TENANT_STATE_UNRESOLVED"
