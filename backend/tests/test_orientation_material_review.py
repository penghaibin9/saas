"""Real MySQL coverage for material review serialization and enrollment freeze."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

from test_orientation_o3_self_service import PORTAL, TID, _seed_o3, _token, _upload


def test_material_projection_keeps_business_status_and_version_separate_from_file():
    from app.models import OrientationMaterial
    from app.services.orientation_service import _mat_row

    material = OrientationMaterial(
        id=1, ori_student_id=2, material_type="ID_CARD", file_name="身份证明.txt",
        status="UPLOADED", version=3, is_current=True, submission_no=1,
    )
    row = _mat_row(material, file_data={"status": "AVAILABLE", "version": 99, "fileId": "7"})
    assert row["status"] == "UPLOADED" and row["statusLabel"] == "待审核"
    assert row["version"] == 3
    assert row["fileStatus"] == "AVAILABLE" and row["fileId"] == "7"


def _student_headers(ids):
    return _token(user_id=ids["userId"], student_id=ids["profileId"],
                  student_no=ids["studentNo"], name=ids["name"])


def _submit(client, headers, material_type, request_id):
    file_id = _upload(client, headers, f"{request_id}.txt", request_id.encode())
    response = client.post(f"{PORTAL}/materials", headers=headers, json={
        "materialType": material_type, "fileId": file_id, "clientSubmissionId": request_id,
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _review_row(client, headers, ids, material_id):
    response = client.get("/api/v1/orientation/materials", headers=headers, params={
        "orientationStudentId": str(ids["orientationId"]),
    })
    assert response.status_code == 200, response.text
    return next(row for row in response.json()["data"]["items"] if row["id"] == material_id)


def test_material_competing_reviews_require_current_version_and_commit_once(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationAuditTrail, OrientationMaterial, OrientationStudent
    from app.models.file import FileVersion

    ids = _seed_o3(db_mode)
    student_headers = _student_headers(ids)
    material = _submit(client, student_headers, "ID_CARD", "review-concurrent-material-0001")
    row = _review_row(client, auth_headers, ids, material["id"])
    path = f"/api/v1/orientation/materials/{material['id']}"
    for payload in ({}, {"expectedVersion": -1}):
        missing = client.post(f"{path}/approve", headers=auth_headers, json=payload)
        assert missing.status_code == 400 and missing.json()["code"] == 422001, missing.text
    stale = client.post(f"{path}/approve", headers=auth_headers,
                        json={"expectedVersion": row["version"] + 1})
    assert stale.status_code == 409, stale.text
    denied = client.post(f"{path}/approve", headers=student_headers,
                         json={"expectedVersion": row["version"]})
    assert denied.status_code == 403, denied.text
    with get_sessionmaker()() as db:
        parent_version = db.get(OrientationStudent, ids["orientationId"]).version

    start = Barrier(2)

    def review(action):
        start.wait(timeout=10)
        return client.post(f"{path}/{action}", headers=auth_headers, json={
            "expectedVersion": row["version"], "reason": "身份证明图片模糊，请重新提交",
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(review, ("approve", "return")))
    assert sorted(response.status_code for response in responses) == [200, 409], [
        response.text for response in responses
    ]
    winner = next(response.json()["data"] for response in responses if response.status_code == 200)
    assert winner["version"] == row["version"] + 1
    with get_sessionmaker()() as db:
        current = db.get(OrientationMaterial, int(material["id"]))
        file_version = db.get(FileVersion, current.file_version_id)
        assert current.status == winner["status"]
        assert current.version == row["version"] + 1
        assert file_version.status == ("APPROVED" if current.status == "APPROVED" else "REJECTED")
        assert db.get(OrientationStudent, ids["orientationId"]).version == parent_version + 1
        assert db.query(OrientationAuditTrail).filter_by(
            tenant_id=TID, biz_type="MATERIAL", biz_id=material["id"],
        ).filter(OrientationAuditTrail.action.in_(("审核通过", "退回材料"))).count() == 1

    # Even a refreshed version cannot review a completed decision again.
    for action in ("approve", "return"):
        repeated = client.post(f"{path}/{action}", headers=auth_headers, json={
            "expectedVersion": winner["version"], "reason": "旧页面仍然尝试退回这份材料",
        })
        assert repeated.status_code == 409, repeated.text


def test_material_return_resubmit_approve_finalize_close_archive_freezes_review(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (OrientationBatch, OrientationFlowStep, OrientationMaterial,
                            OrientationMaterialRequirement, OrientationStudent)
    from app.models.file import FileVersion
    from app.services.orientation_flow_service import ensure_student_steps

    ids = _seed_o3(db_mode)
    # Only prepare the school's rules and reporting window. Every student and
    # teacher transition below uses its authenticated business endpoint.
    with get_sessionmaker()() as db:
        student = db.get(OrientationStudent, ids["orientationId"])
        batch = db.get(OrientationBatch, student.batch_id)
        batch.report_start_date = datetime.utcnow() - timedelta(days=1)
        batch_id, batch_no = batch.id, batch.batch_no
        db.add(OrientationFlowStep(
            tenant_id=TID, flow_version_id=batch.flow_version_id, step_key="CONFIRM",
            step_name="学院确认", enabled=True, required=True, sort_order=10,
        ))
        for material_type in ("ID_CARD", "ADMISSION_LETTER"):
            db.add(OrientationMaterialRequirement(
                tenant_id=TID, flow_version_id=batch.flow_version_id,
                material_type=material_type, material_name=material_type, required=True,
                requires_scan_clean=True, allowed_exts_json=["txt"],
                max_size_bytes=1024, source_type="MANUAL",
            ))
        db.flush()
        ensure_student_steps(db, student, status_source="PROCESS_FACT")
        db.commit()

    student_headers = _student_headers(ids)
    collected = client.post(f"{PORTAL}/collect", headers=student_headers, json={
        "phone": "13800138000", "origin": "湖南长沙",
        "emergencyContactName": "家长甲", "emergencyPhone": "13900139000", "confirmed": True,
    })
    assert collected.status_code == 200, collected.text
    initial = _submit(client, student_headers, "ID_CARD", "material-finalize-identity-v1")
    initial_row = _review_row(client, auth_headers, ids, initial["id"])
    returned = client.post(f"/api/v1/orientation/materials/{initial['id']}/return",
                           headers=auth_headers, json={"expectedVersion": initial_row["version"],
                                                       "reason": "身份证明图片模糊，请重新上传"})
    assert returned.status_code == 200, returned.text
    revised = _submit(client, student_headers, "ID_CARD", "material-finalize-identity-v2")
    letter = _submit(client, student_headers, "ADMISSION_LETTER", "material-finalize-letter-v1")
    for material in (revised, letter):
        row = _review_row(client, auth_headers, ids, material["id"])
        approved = client.post(f"/api/v1/orientation/materials/{material['id']}/approve",
                               headers=auth_headers, json={"expectedVersion": row["version"]})
        assert approved.status_code == 200, approved.text
    # An optional pending material proves the enrollment gate independently of
    # the per-material APPROVED/RETURNED guards.
    optional = _submit(client, student_headers, "PHOTO", "material-finalize-optional-v1")
    optional_row = _review_row(client, auth_headers, ids, optional["id"])
    point = client.post("/api/v1/orientation/checkin-points", headers=auth_headers,
                        json={"name": "材料闭环报到点", "location": "综合楼一层", "capacity": 100})
    assert point.status_code == 200, point.text
    token = client.post(f"{PORTAL}/checkin-token", headers=student_headers)
    assert token.status_code == 200, token.text
    checked_in = client.post("/api/v1/mobile/teacher/orientation/checkin/confirm", headers=auth_headers,
                             json={"token": token.json()["data"]["token"],
                                   "checkinPointId": point.json()["data"]["id"]})
    assert checked_in.status_code == 200, checked_in.text
    detail = client.get(f"/api/v1/orientation/students/{ids['orientationId']}", headers=auth_headers)
    finalized = client.post(f"/api/v1/orientation/students/{ids['orientationId']}/finalize",
                            headers=auth_headers, json={
                                "expectedVersion": detail.json()["data"]["student"]["version"],
                                "studentNo": ids["studentNo"], "clientRequestId": "material-review-finalize-0001",
                            })
    assert finalized.status_code == 200, finalized.text

    for material in (revised, optional):
        row = _review_row(client, auth_headers, ids, material["id"])
        for action in ("approve", "return"):
            frozen = client.post(f"/api/v1/orientation/materials/{material['id']}/{action}",
                                 headers=auth_headers, json={"expectedVersion": row["version"],
                                                             "reason": "学院确认后旧页面尝试继续修改"})
            assert frozen.status_code == 409 and "已结束或暂停" in frozen.json()["message"], frozen.text

    closed = client.post(f"/api/v1/orientation/batches/{batch_id}/close", headers=auth_headers)
    assert closed.status_code == 200, closed.text
    closed_review = client.post(f"/api/v1/orientation/materials/{optional['id']}/approve",
                                headers=auth_headers, json={"expectedVersion": optional_row["version"]})
    assert closed_review.status_code == 409 and "批次已关闭" in closed_review.json()["message"]
    archive = client.post("/api/v1/orientation/archives", headers=auth_headers,
                          json={"archiveName": "材料退回重交至入学归档", "batchNo": batch_no})
    assert archive.status_code == 200, archive.text
    archive_id = archive.json()["data"]["id"]
    archived = client.post(f"/api/v1/orientation/archives/{archive_id}/run", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["itemCount"] == 1
    snapshots = client.get(f"/api/v1/orientation/archives/{archive_id}/items", headers=auth_headers)
    assert snapshots.json()["data"]["items"][0]["reportStatus"] == "COLLEGE_CONFIRMED"
    with get_sessionmaker()() as db:
        assert db.get(OrientationMaterial, int(initial["id"])).status == "RETURNED"
        current = db.get(OrientationMaterial, int(revised["id"]))
        assert current.status == "APPROVED"
        assert db.get(FileVersion, current.file_version_id).status == "APPROVED"
        pending = db.get(OrientationMaterial, int(optional["id"]))
        assert pending.status == "UPLOADED" and pending.version == optional_row["version"]
