"""Completed orientation remains readable without reopening student submissions."""
from datetime import datetime, timedelta

import pytest

from test_orientation_o3_self_service import TID, _seed_o3, _token, _upload


def _student_headers(ids, *, other=False):
    return _token(
        user_id=ids["otherUserId" if other else "userId"],
        student_id=ids["otherProfileId" if other else "profileId"],
        student_no=ids["otherNo" if other else "studentNo"],
        name=ids["otherName" if other else "name"],
    )


def _information():
    return {
        "phone": "13800138000", "origin": "湖南长沙",
        "emergencyContactName": "虚构联系人", "emergencyPhone": "13900139000",
        "confirmed": True,
    }


def _arrival():
    return {
        "arrivalMode": "TRAIN",
        "plannedArrivalAt": (datetime.utcnow() + timedelta(days=2)).isoformat(),
        "stationName": "长沙南站", "transportNo": "G100",
        "pickupRequired": True, "companionCount": 1, "expectedVersion": 0,
    }


def _seed_submitted_history(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationMaterial

    ids = _seed_o3(db_mode)
    headers = _student_headers(ids)
    info = client.post("/api/v1/portal/orientation/collect", headers=headers, json=_information())
    assert info.status_code == 200, info.text
    arrival = client.put("/api/v1/portal/orientation/arrival", headers=headers, json=_arrival())
    assert arrival.status_code == 200, arrival.text
    materials = []
    for number in (1, 2):
        file_id = _upload(client, headers, f"history-{number}.txt", f"fictional {number}".encode())
        result = client.post("/api/v1/portal/orientation/materials", headers=headers, json={
            "materialType": "ID_CARD", "fileId": file_id,
            "clientSubmissionId": f"orientation-history-v{number}",
        })
        assert result.status_code == 200, result.text
        materials.append({**result.json()["data"], "fileId": file_id})
        # This fixture prepares prior review facts; this test concerns read access,
        # not the separately tested teacher review command.
        with get_sessionmaker()() as db:
            material = db.get(OrientationMaterial, int(materials[-1]["id"]))
            material.status = "RETURNED" if number == 1 else "APPROVED"
            material.return_reason = "请补充清晰材料" if number == 1 else None
            db.commit()
    return ids, headers, materials


@pytest.mark.parametrize("stage,report_status,batch_status,reason", [
    ("ENROLLED", "PREPARED", "ACTIVE", "已办结"),
    ("ADMITTED", "COLLEGE_CONFIRMED", "ACTIVE", "已办结"),
    ("ENROLLED", "COLLEGE_CONFIRMED", "CLOSED", "已关闭"),
    ("ADMITTED", "PREPARED", "CLOSED", "已关闭"),
])
def test_completed_or_closed_orientation_keeps_history_and_rejects_writes(
    client, db_mode, stage, report_status, batch_status, reason,
):
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationStudent

    ids, headers, materials = _seed_submitted_history(client, db_mode)
    with get_sessionmaker()() as db:
        orientation = db.get(OrientationStudent, ids["orientationId"])
        orientation.stage, orientation.report_status = stage, report_status
        db.get(OrientationBatch, orientation.batch_id).status = batch_status
        db.commit()

    for prefix in ("/api/v1/portal", "/api/v1/mobile"):
        response = client.get(prefix + "/orientation/my", headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["orientationStudentId"] == str(ids["orientationId"])
        own = result["selfService"]
        assert own["available"] is False and own["canSubmitMaterials"] is False
        assert reason in own["reason"]
        assert own["information"]["origin"] == "湖南长沙"
        assert own["information"]["phoneMasked"] == "138****8000"
        assert own["information"]["emergencyContactName"] == "虚构联系人"
        assert own["arrivalPlan"]["stationName"] == "长沙南站"
        assert [row["id"] for row in own["materials"]] == [materials[1]["id"], materials[0]["id"]]
        assert [row["submissionNo"] for row in own["materials"]] == [2, 1]
        assert [row["isCurrent"] for row in own["materials"]] == [True, False]
        assert [row["status"] for row in own["materials"]] == ["APPROVED", "RETURNED"]
        assert own["materials"][1]["returnReason"] == "请补充清晰材料"
        assert [row["fileId"] for row in own["materials"]] == [materials[1]["fileId"], materials[0]["fileId"]]

        denied = client.post(prefix + "/orientation/materials", headers=headers, json={
            "materialType": "PHOTO", "fileId": materials[1]["fileId"],
            "clientSubmissionId": "orientation-history-after-close",
        })
        assert denied.status_code in (404, 409), denied.text
        denied = client.post(prefix + "/orientation/collect", headers=headers, json=_information())
        assert denied.status_code in (404, 409), denied.text
        denied = client.put(prefix + "/orientation/arrival", headers=headers, json=_arrival())
        assert denied.status_code in (404, 409), denied.text

    # Both home entry points continue to acknowledge the same finished record.
    overview = client.get("/api/v1/mobile/me/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    domain = next(row for row in overview.json()["data"]["domains"] if row["key"] == "orientation")
    assert domain["hasData"] is True and domain["status"] == report_status
    if report_status == "COLLEGE_CONFIRMED":
        home = client.get("/api/v1/portal/home/overview", headers=headers)
        assert home.status_code == 200, home.text
        lifecycle = next(row for row in home.json()["data"]["lifecycle"] if row["key"] == "orientation")
        assert lifecycle["status"] == "COMPLETED"


def test_history_rejects_other_student_and_foreign_tenant_rows(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationMaterial, OrientationStudent

    ids, headers, materials = _seed_submitted_history(client, db_mode)
    with get_sessionmaker()() as db:
        orientation = db.get(OrientationStudent, ids["orientationId"])
        orientation.stage, orientation.report_status = "ENROLLED", "COLLEGE_CONFIRMED"
        batch = db.get(OrientationBatch, orientation.batch_id)
        batch.status = "CLOSED"
        # Even inconsistent imported children cannot cross the stable person or
        # tenant predicates used to read a student's own submission history.
        for tenant_id, student_id, name in (
            (TID, ids["otherProfileId"], "other-student-secret.txt"),
            (TID + 1, ids["profileId"], "foreign-tenant-secret.txt"),
        ):
            db.add(OrientationMaterial(
                tenant_id=tenant_id, ori_student_id=orientation.id, student_id=student_id,
                material_type="PHOTO", file_name=name, submission_no=1,
                status="APPROVED", source_type="LEGACY_BACKFILL",
            ))
        # A same-name legacy row must not substitute for the other student's
        # missing stable orientation link, even after a batch closes.
        db.add(OrientationStudent(
            tenant_id=TID, batch_id=batch.id, student_id=None, name=ids["otherName"],
            admission_no="HISTORY-UNLINKED", source_type="MANUAL", source_record_id="HISTORY-UNLINKED",
            identity_status="UNLINKED", record_status="ACTIVE",
        ))
        foreign_batch = OrientationBatch(
            tenant_id=TID + 1, batch_name="foreign-batch", batch_no="HISTORY-FOREIGN",
            status="ACTIVE", flow_version_id=batch.flow_version_id,
        )
        db.add(foreign_batch)
        db.flush()
        db.add(OrientationStudent(
            tenant_id=TID + 1, batch_id=foreign_batch.id, student_id=ids["profileId"], name="foreign-secret",
            admission_no="HISTORY-FOREIGN", source_type="MANUAL", source_record_id="HISTORY-FOREIGN",
            identity_status="LINKED", record_status="ACTIVE",
        ))
        db.commit()

    for prefix in ("/api/v1/portal", "/api/v1/mobile"):
        mine = client.get(prefix + "/orientation/my", headers=headers)
        assert mine.status_code == 200, mine.text
        result = mine.json()["data"]
        assert result["orientationStudentId"] == str(ids["orientationId"])
        assert {row["id"] for row in result["selfService"]["materials"]} == {row["id"] for row in materials}
        assert "secret" not in mine.text
        other = client.get(prefix + "/orientation/my", headers=_student_headers(ids, other=True))
        assert other.status_code == 200, other.text
        assert other.json()["data"]["hasData"] is False
        assert "materials" not in other.json()["data"]


def test_open_batch_is_consistent_between_home_and_material_history(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationStudent
    from app.services.orientation_flow_service import ensure_student_steps

    ids, headers, materials = _seed_submitted_history(client, db_mode)
    with get_sessionmaker()() as db:
        old = db.get(OrientationStudent, ids["orientationId"])
        old.stage, old.report_status = "ENROLLED", "COLLEGE_CONFIRMED"
        old_batch = db.get(OrientationBatch, old.batch_id)
        old_batch.status = "CLOSED"
        now = datetime.utcnow()
        batch = OrientationBatch(
            tenant_id=TID, batch_name="新的开放迎新批次", batch_no="HISTORY-CURRENT",
            status="ACTIVE", flow_version_id=old_batch.flow_version_id,
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=5),
        )
        db.add(batch)
        db.flush()
        current = OrientationStudent(
            tenant_id=TID, batch_id=batch.id, student_id=ids["profileId"], name=ids["name"],
            admission_no="HISTORY-CURRENT", source_type="MANUAL", source_record_id="HISTORY-CURRENT",
            identity_status="LINKED", record_status="ACTIVE", report_status="PREPARED",
        )
        db.add(current)
        db.flush()
        ensure_student_steps(db, current, status_source="PROCESS_FACT")
        current_id = str(current.id)
        db.commit()

    for prefix in ("/api/v1/portal", "/api/v1/mobile"):
        response = client.get(prefix + "/orientation/my", headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["orientationStudentId"] == result["selfService"]["orientationStudentId"] == current_id
        assert result["selfService"]["available"] is True
        assert result["selfService"]["canSubmitMaterials"] is True
        assert result["selfService"]["materials"] == []
    overview = client.get("/api/v1/mobile/me/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    domain = next(row for row in overview.json()["data"]["domains"] if row["key"] == "orientation")
    assert domain["hasData"] is True and domain["status"] == "PREPARED"

    # A second open batch is an ambiguity, never an arbitrary winner or a write
    # permission inferred from the read selection.
    with get_sessionmaker()() as db:
        old = db.get(OrientationStudent, ids["orientationId"])
        db.get(OrientationBatch, old.batch_id).status = "ACTIVE"
        db.commit()
    for prefix in ("/api/v1/portal", "/api/v1/mobile"):
        response = client.get(prefix + "/orientation/my", headers=headers)
        assert response.status_code == 409, response.text
        denied = client.post(prefix + "/orientation/collect", headers=headers, json=_information())
        assert denied.status_code == 409, denied.text
    overview = client.get("/api/v1/mobile/me/overview", headers=headers)
    assert overview.status_code == 409, overview.text
