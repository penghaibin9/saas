"""O5 signed check-in and enrollment finalize golden path (run in final gate)."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from test_orientation_o4_qualification import TID, _seed, _student_headers


def test_o5_imported_candidate_activates_identity_before_signed_checkin(
    client, db_mode, auth_headers,
):
    from app.db.session import get_sessionmaker
    from app.models import OrientationPaymentAccount, OrientationStudent, StudentAccountLink

    ids = _seed(db_mode)
    db = get_sessionmaker()()
    try:
        orientation = db.get(OrientationStudent, ids["orientation"])
        payment = db.query(OrientationPaymentAccount).filter_by(
            tenant_id=TID, orientation_student_id=orientation.id,
        ).first()
        payment.status = "PAID"
        payment.paid_amount = payment.payable_amount
        link = db.query(StudentAccountLink).filter_by(
            tenant_id=TID, student_id=ids["profile"], link_status="ACTIVE",
        ).first()
        db.delete(link)
        orientation.student_id = None
        orientation.identity_status = "UNLINKED"
        expected_version = int(orientation.version or 0)
        db.commit()
    finally:
        db.close()

    blocked = client.get(
        f"/api/v1/orientation/qualifications/{ids['orientation']}", headers=auth_headers,
    )
    assert blocked.status_code == 200, blocked.text
    assert any(
        item["code"] == "IDENTITY_NOT_LINKED"
        for item in blocked.json()["data"]["blockers"]
    )

    body = {
        "expectedVersion": expected_version,
        "studentNo": ids["studentNo"],
        "clientRequestId": "o5-activate-imported-0001",
    }
    activated = client.post(
        f"/api/v1/orientation/students/{ids['orientation']}/activate",
        headers=auth_headers, json=body,
    )
    assert activated.status_code == 200, activated.text
    activated_data = activated.json()["data"]
    assert activated_data["identityStatus"] == "LINKED"
    assert activated_data["studentId"] == str(ids["profile"])

    replay = client.post(
        f"/api/v1/orientation/students/{ids['orientation']}/activate",
        headers=auth_headers, json=body,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["idempotent"] is True

    qualified = client.post(
        f"/api/v1/orientation/qualifications/{ids['orientation']}/recalculate",
        headers=auth_headers,
    )
    assert qualified.status_code == 200, qualified.text
    assert qualified.json()["data"]["verdict"] == "QUALIFIED"

    student_headers = _student_headers(
        ids["user"], ids["profile"], ids["studentNo"], ids["name"],
    )
    issued = client.post("/api/v1/mobile/orientation/checkin-token", headers=student_headers)
    assert issued.status_code == 200, issued.text
    assert issued.json()["data"]["token"].startswith("oci1.")


def test_o5_signed_preflight_one_time_confirm_and_finalize(client, db_mode, auth_headers, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import (
        OrientationCheckinPoint, OrientationEnrollmentFinalize,
        OrientationFlowStep, OrientationPaymentAccount, OrientationStudent,
        StudentProfile, StudentStageEvent, UnifiedMessage,
    )
    from app.services.orientation_flow_service import ensure_student_steps

    ids = _seed(db_mode)
    db = get_sessionmaker()()
    orientation = db.get(OrientationStudent, ids["orientation"])
    profile = db.get(StudentProfile, ids["profile"])
    profile.current_stage = "ADMITTED"
    payment = db.query(OrientationPaymentAccount).filter_by(
        tenant_id=TID, orientation_student_id=orientation.id,
    ).first()
    payment.status = "PAID"
    payment.paid_amount = payment.payable_amount
    from app.models import OrientationBatch
    batch = db.get(OrientationBatch, orientation.batch_id)
    existing_keys = {row.step_key for row in db.query(OrientationFlowStep).filter_by(
        tenant_id=TID, flow_version_id=batch.flow_version_id,
    ).all()}
    for order, (key, name) in enumerate((("CHECKIN", "现场报到"), ("CONFIRM", "学院确认")), start=20):
        if key not in existing_keys:
            db.add(OrientationFlowStep(
                tenant_id=TID, flow_version_id=batch.flow_version_id,
                step_key=key, step_name=name, enabled=True, required=True, sort_order=order,
            ))
    db.flush()
    ensure_student_steps(db, orientation, status_source="PROCESS_FACT")
    point = OrientationCheckinPoint(
        tenant_id=TID, name="O5学院现场报到点", location="综合楼一层",
        capacity=500, status="ENABLED",
    )
    db.add(point)
    db.commit()
    point_id = int(point.id)
    db.close()

    student_headers = _student_headers(ids["user"], ids["profile"], ids["studentNo"], ids["name"])
    issued = client.post("/api/v1/mobile/orientation/checkin-token", headers=student_headers)
    assert issued.status_code == 200, issued.text
    token_data = issued.json()["data"]
    token = token_data["token"]
    assert token.startswith("oci1.")
    assert token_data["ttlSeconds"] == 600

    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    rejected = client.post(
        "/api/v1/mobile/teacher/orientation/checkin/preflight",
        headers=auth_headers, json={"token": tampered},
    )
    assert rejected.status_code == 400

    preflight = client.post(
        "/api/v1/mobile/teacher/orientation/checkin/preflight",
        headers=auth_headers, json={"token": token},
    )
    assert preflight.status_code == 200, preflight.text
    preview = preflight.json()["data"]
    assert preview["student"]["name"] == ids["name"]
    assert preview["qualification"]["verdict"] == "QUALIFIED"
    assert preview["dorm"]["status"] == "RESERVED"

    confirmed = client.post(
        "/api/v1/mobile/teacher/orientation/checkin/confirm",
        headers=auth_headers, json={"token": token, "checkinPointId": str(point_id)},
    )
    assert confirmed.status_code == 200, confirmed.text
    checkin = confirmed.json()["data"]
    assert checkin["reportStatus"] == "CHECKED_IN"
    replay = client.post(
        "/api/v1/mobile/teacher/orientation/checkin/confirm",
        headers=auth_headers, json={"token": token, "checkinPointId": str(point_id)},
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["idempotent"] is True

    # A lost response may be retried after the original ten-minute credential
    # expires.  Consumption remains one-time, but the existing receipt must still
    # be returned idempotently instead of turning into a false expiry failure.
    from app.services import orientation_checkin_service as checkin_service
    real_datetime = checkin_service.datetime

    class AfterTokenExpiry(real_datetime):
        @classmethod
        def utcnow(cls):
            return real_datetime.utcnow() + timedelta(minutes=11)

    monkeypatch.setattr(checkin_service, "datetime", AfterTokenExpiry)
    delayed_replay = client.post(
        "/api/v1/mobile/teacher/orientation/checkin/confirm",
        headers=auth_headers, json={"token": token, "checkinPointId": str(point_id)},
    )
    assert delayed_replay.status_code == 200, delayed_replay.text
    assert delayed_replay.json()["data"]["idempotent"] is True
    monkeypatch.setattr(checkin_service, "datetime", real_datetime)
    legacy = client.post(
        "/api/v1/mobile/teacher/orientation/checkin",
        headers=auth_headers, json={"admissionNo": "O4-ADMISSION-001"},
    )
    assert legacy.status_code == 410

    db = get_sessionmaker()()
    orientation = db.get(OrientationStudent, ids["orientation"])
    expected_version = int(orientation.version)
    db.close()
    finalized = client.post(
        f"/api/v1/orientation/students/{ids['orientation']}/finalize",
        headers=auth_headers,
        json={
            "expectedVersion": expected_version,
            "studentNo": ids["studentNo"],
            "clientRequestId": "o5-finalize-request-0001",
        },
    )
    assert finalized.status_code == 200, finalized.text
    result = finalized.json()["data"]
    assert result["stage"] == "ENROLLED"
    assert result["studentId"] == str(ids["profile"])
    finalized_replay = client.post(
        f"/api/v1/orientation/students/{ids['orientation']}/finalize",
        headers=auth_headers,
        json={
            "expectedVersion": expected_version,
            "studentNo": ids["studentNo"],
            "clientRequestId": "o5-finalize-request-0001",
        },
    )
    assert finalized_replay.status_code == 200
    assert finalized_replay.json()["data"]["idempotent"] is True

    db = get_sessionmaker()()
    orientation = db.get(OrientationStudent, ids["orientation"])
    profile = db.get(StudentProfile, ids["profile"])
    assert orientation.report_status == "COLLEGE_CONFIRMED"
    assert orientation.stage == "ENROLLED" and profile.current_stage == "ENROLLED"
    assert db.query(OrientationEnrollmentFinalize).filter_by(
        tenant_id=TID, orientation_student_id=orientation.id,
    ).count() == 1
    assert db.query(StudentStageEvent).filter_by(
        tenant_id=TID, student_id=profile.id, source_module="orientation", to_stage="ENROLLED",
    ).count() == 1
    assert db.query(UnifiedMessage).filter_by(
        tenant_id=TID, receiver_id=profile.id, source_module="orientation",
        title="入学确认已完成",
    ).count() == 1
    db.close()

    mine = client.get("/api/v1/mobile/orientation/my", headers=student_headers)
    assert mine.status_code == 200, mine.text
    mine_data = mine.json()["data"]
    assert mine_data["batchName"] == "O4资格批次"
    assert mine_data["dorm"]["label"] == "O4资格楼 / 401 / 1床"
    assert mine_data["checkin"]["pointName"] == "O5学院现场报到点"

    cannot_reissue = client.post("/api/v1/mobile/orientation/checkin-token", headers=student_headers)
    assert cannot_reissue.status_code == 409


def test_o5_migration_is_serial_and_downgrade_safe():
    source = (
        Path(__file__).parents[1] / "alembic" / "versions"
        / "20260901_orientation_checkin_o5.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20260901_dorm_presence_d6"' in source
    assert "O5 preflight failed before DDL" in source
    assert source.index("_preflight()") < source.index("op.create_table(")
    assert "O5 downgrade blocked" in source
    assert "t_orientation_checkin_token" in source
    assert "t_orientation_checkin_record" in source
    assert "t_orientation_enrollment_finalize" in source
