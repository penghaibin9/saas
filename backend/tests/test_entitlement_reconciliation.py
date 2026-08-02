from app.services.entitlement_reconciliation_service import (
    downgrade_impact_preview,
    reconcile_snapshot,
)


def test_school_quota_cannot_silently_exceed_commercial_limit():
    result = reconcile_snapshot({
        "commercialStorageLimitBytes": 20 * 1024**3,
        "schoolGovernanceQuotaBytes": 30 * 1024**3,
        "fileObjectBytes": 1,
        "heldReservationBytes": 0,
    })
    assert result["healthy"] is False
    assert "SCHOOL_QUOTA_EXCEEDS_COMMERCIAL" in {item["code"] for item in result["violations"]}


def test_actual_consumption_includes_file_objects_and_held_reservations():
    result = reconcile_snapshot({
        "commercialStorageLimitBytes": 100,
        "schoolGovernanceQuotaBytes": 100,
        "fileObjectBytes": 70,
        "heldReservationBytes": 40,
    })
    assert result["actualConsumptionBytes"] == 110
    assert "ACTUAL_USAGE_EXCEEDS_COMMERCIAL" in {item["code"] for item in result["violations"]}


def test_unauthorized_module_usage_and_paid_unprovisioned_are_repairable():
    result = reconcile_snapshot({
        "commercialStorageLimitBytes": 1000,
        "schoolGovernanceQuotaBytes": 900,
        "fileObjectBytes": 1,
        "heldReservationBytes": 0,
        "moduleUsage": [{"moduleCode": "internship", "bytes": 10, "entitled": False}],
        "paidOrder": True,
        "provisioned": False,
    })
    codes = {item["code"] for item in result["violations"]}
    assert codes == {"UNAUTHORIZED_MODULE_USAGE", "PAID_ORDER_NOT_PROVISIONED"}
    assert result["repairTaskRequired"] is True


def test_downgrade_preview_never_claims_silent_file_deletion():
    preview = downgrade_impact_preview(current_limit_bytes=100, target_limit_bytes=50, actual_bytes=80)
    assert preview["overageBytes"] == 30
    assert preview["willDeleteFiles"] is False
    assert preview["requiresRepairPlan"] is True
