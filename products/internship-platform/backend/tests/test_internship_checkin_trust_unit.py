import inspect

from app.api.v1 import mobile
from app.core.exceptions import AppException
from app.modules.internship.services import internship_checkin_trust_service as trust
from app.services import mobile_student_service


def test_checkin_token_is_bound_to_student_record_and_day(monkeypatch):
    monkeypatch.setattr(trust.time, "time", lambda: 1_000)
    issued = trust.issue_token(tenant_id=7, student_id=8, internship_id=9,
                               checkin_date="2026-09-07")
    trust.verify_token(issued["token"], tenant_id=7, student_id=8, internship_id=9,
                       checkin_date="2026-09-07")
    try:
        trust.verify_token(issued["token"], tenant_id=7, student_id=18, internship_id=9,
                           checkin_date="2026-09-07")
    except AppException as exc:
        assert exc.code == "INVALID_CHECKIN_TOKEN"
    else:
        raise AssertionError("cross-student token must be rejected")


def test_checkin_token_rejects_tampering_and_expiry(monkeypatch):
    monkeypatch.setattr(trust.time, "time", lambda: 2_000)
    issued = trust.issue_token(tenant_id=7, student_id=8, internship_id=9,
                               checkin_date="2026-09-08")
    tampered = issued["token"][:-1] + ("A" if issued["token"][-1] != "A" else "B")
    for token, now, expected in (
        (tampered, 2_000, "INVALID_CHECKIN_TOKEN"),
        (issued["token"], 2_301, "CHECKIN_TOKEN_EXPIRED"),
    ):
        monkeypatch.setattr(trust.time, "time", lambda value=now: value)
        try:
            trust.verify_token(token, tenant_id=7, student_id=8, internship_id=9,
                               checkin_date="2026-09-08")
        except AppException as exc:
            assert exc.code == expected
        else:
            raise AssertionError(f"{expected} must be raised")


def test_location_quality_never_turns_low_accuracy_into_normal():
    rule = {"configured": True, "radiusM": 500, "maxAccuracyM": 200}
    assert trust.classify_location(lat=1, lng=1, accuracy=350, rule=rule, distance_m=20) == (
        "LOW_ACCURACY", "LOW_ACCURACY")
    assert trust.classify_location(lat=1, lng=1, accuracy=40, rule=rule, distance_m=490) == (
        "LOCATION_UNCERTAIN", "LOCATION_UNCERTAIN")
    assert trust.classify_location(lat=1, lng=1, accuracy=30, rule=rule, distance_m=100) == (
        "NORMAL", None)


def test_location_classification_covers_all_operational_branches():
    rule = {"configured": True, "radiusM": 500, "maxAccuracyM": 200}
    assert trust.classify_location(lat=1, lng=1, accuracy=20, rule=rule, distance_m=650) == (
        "OUT_OF_RANGE", "OUT_OF_RANGE")
    assert trust.classify_location(lat=None, lng=None, accuracy=None, rule=rule, distance_m=None) == (
        "NO_LOCATION", "MISSING")
    assert trust.classify_location(
        lat=1, lng=1, accuracy=20,
        rule={**rule, "configured": False}, distance_m=None,
    ) == ("RECORDED", None)


def test_frozen_placement_rule_wins_over_later_position_changes(monkeypatch):
    from types import SimpleNamespace

    record = SimpleNamespace(batch_id=1, current_placement_snapshot_id=44)
    position = SimpleNamespace(geofence_lat=10.0, geofence_lng=11.0, geofence_radius_m=900)
    batch = SimpleNamespace(rules_config={"checkin": {"maxAccuracyM": 300}})
    snapshot = SimpleNamespace(snapshot_json={"checkinRule": {
        "coordinateSystem": "GCJ02", "centerLat": 20.0, "centerLng": 21.0,
        "radiusM": 500, "maxAccuracyM": 120,
    }})

    def fake_tenant_get(_db, model, entity_id):
        if model is trust.InternshipBatch and entity_id == 1:
            return batch
        if model is trust.InternshipPlacementSnapshot and entity_id == 44:
            return snapshot
        return None

    monkeypatch.setattr(trust, "tenant_get", fake_tenant_get)
    resolved = trust.resolve_rule(object(), record, position)
    assert resolved == {
        "configured": True, "centerLat": 20.0, "centerLng": 21.0,
        "radiusM": 500, "maxAccuracyM": 120,
        "coordinateSystem": "GCJ02", "source": "PLACEMENT_SNAPSHOT",
    }


def test_checkin_routes_forward_selected_batch_context():
    large_batch_id = "9007199254740993"
    assert mobile._selected_internship_batch_id(
        header_value=large_batch_id, explicit=None
    ) == large_batch_id
    assert mobile._selected_internship_batch_id(
        header_value=large_batch_id, explicit=7
    ) == "7"

    for endpoint in (
        mobile.internship_checkin,
        mobile.internship_checkin_preflight,
        mobile.internship_checkin_week,
    ):
        source = inspect.getsource(endpoint)
        assert "batch_id=Depends(_selected_internship_batch_id)" in source
        assert "batch_id=batch_id" in source

    for service in (
        mobile_student_service.internship_checkin,
        mobile_student_service.internship_checkin_preflight,
        mobile_student_service.internship_checkin_week,
    ):
        assert "batch_id" in inspect.signature(service).parameters
        assert "_internship_record(db, u, batch_id=batch_id" in inspect.getsource(service)
