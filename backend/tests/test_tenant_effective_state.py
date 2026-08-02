from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services.tenant_effective_state_service import effective_state_from_records


def test_hard_suspension_wins_and_mismatch_is_visible():
    result = effective_state_from_records(
        row_status="SUSPENDED",
        meta={"status": "active"},
    )
    assert result["effectiveStatus"] == "disabled"
    assert result["mismatch"] is True
    assert result["writable"] is False


def test_expiration_is_derived_fail_closed():
    result = effective_state_from_records(
        row_status="ACTIVE",
        meta={"status": "active", "expireAt": (datetime.utcnow() - timedelta(seconds=1)).isoformat()},
    )
    assert result["effectiveStatus"] == "expired"
    assert result["readonly"] is True
    with pytest.raises(AppException) as exc:
        effective_state_from_records(row_status="ACTIVE", meta={"status": "active", "expireAt": "bad"})
    assert exc.value.code == "TENANT_STATE_UNRESOLVED"


def test_unknown_state_never_defaults_to_active():
    with pytest.raises(AppException) as exc:
        effective_state_from_records(row_status="MYSTERY", meta={"status": "active"})
    assert exc.value.code == "TENANT_STATE_UNRESOLVED"
