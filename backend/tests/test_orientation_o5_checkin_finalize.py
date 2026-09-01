"""O5 signed check-in and enrollment finalize golden path (run in final gate)."""
from __future__ import annotations

from pathlib import Path

from test_orientation_o4_qualification import TID, _seed, _student_headers


def test_o5_signed_preflight_one_time_confirm_and_finalize(client, db_mode, auth_headers):
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
