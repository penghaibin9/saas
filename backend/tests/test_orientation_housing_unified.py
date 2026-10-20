"""Real commands and canonical reads on the isolated MySQL test schema."""
from test_dorm_d3_allocation import _admin, _seed_authorities, _create, BASE


def test_orientation_housing_follows_reservation_checkin_checkout(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DormBed, OrientationStudent
    seeded = _seed_authorities(students=2, beds=3, unlinked=1)
    from app.core.security import create_access_token
    from app.models import User
    with get_sessionmaker()() as db:
        admin = User(tenant_id=1000000000000000001, login_name="housing-admin", real_name="住宿管理员", password_hash="unused", user_type="TEACHER", status="ACTIVE")
        db.add(admin); db.commit(); admin_id = admin.id
    headers = {"Authorization": "Bearer " + create_access_token({"userId": f"u_{admin_id}", "realName": "住宿管理员", "userType": "TEACHER", "tenantId": "1000000000000000001", "tid": "x", "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})}
    sid = seeded["students"][0][0]
    ori_id = seeded["orientationStudents"][0]
    # Historical text must not masquerade as actual occupancy, even during filtering.
    with get_sessionmaker()() as db:
        ori = db.get(OrientationStudent, ori_id)
        ori.dorm_status, ori.building, ori.room = "CHECKED_IN", "旧文本楼栋", "旧床位"
        db.commit()
    def dorms(**params):
        res = client.get("/api/v1/orientation/dorms", headers=headers, params=params)
        assert res.status_code == 200, res.text
        return res.json()["data"]
    assert dorms(dormStatus="CHECKED_IN")["total"] == 0
    rows = dorms(dormStatus="UNASSIGNED", pageSize=1)
    assert rows["total"] == 3 and len(rows["items"]) == 1
    assert rows["items"][0]["building"] == ""
    rejected = client.put(f"/api/v1/orientation/dorms/{ori_id}", headers=headers,
                          json={"building": "伪造楼栋", "dormStatus": "CHECKED_IN"})
    assert rejected.status_code == 400
    assert client.post("/api/v1/orientation/dorms/confirm", headers=headers,
                       json={"ids": [str(ori_id)]}).status_code == 400

    batch_id = _create(client, headers, seeded, "ADMIN_AUTO", "UNIFIED")
    assert client.post(f"{BASE}/{batch_id}/dry-run", headers=headers).status_code == 200
    assert client.post(f"{BASE}/{batch_id}/publish", headers=headers).status_code == 200
    assigned = dorms(dormStatus="ASSIGNED")
    assert assigned["total"] == 2
    row = next(r for r in assigned["items"] if r["id"] == str(ori_id))
    assert row["housingStatus"] == "RESERVED" and row["checkinTime"] == ""
    assert row["profileStudentId"] == str(sid)
    bed_id = row["bedId"]
    room_beds = client.get(f"/api/v1/student-affairs/dorm/rooms/{seeded['roomId']}/beds", headers=headers).json()["data"]["items"]
    reserved_bed = next(b for b in room_beds if b["bedId"] == bed_id)
    assert reserved_bed["reservedStudentId"] == str(sid)
    assert reserved_bed["reservedStudentName"] == seeded["students"][0][1]
    assert not reserved_bed["studentId"]  # reservation is not occupancy
    actual = client.post(f"/api/v1/student-affairs/dorm/beds/{bed_id}/checkin",
                         headers=headers, json={"studentId": str(sid)})
    assert actual.status_code == 200, actual.text
    row = dorms(dormStatus="CHECKED_IN")["items"][0]
    assert row["housingStatus"] == "ACTIVE" and row["checkinTime"]
    detail = client.get(f"{BASE}/{batch_id}", headers=headers).json()["data"]
    item = next(i for i in detail["items"] if i["studentId"] == str(sid))
    assert item["housing"]["housingStatus"] == "ACTIVE"
    # An exception is a separate issue, never a replacement for occupancy truth.
    assert client.post(f"/api/v1/orientation/dorms/{ori_id}/exception", headers=headers,
                       json={"note": "住宿设施需要核查处理"}).status_code == 200
    assert dorms(dormStatus="CHECKED_IN")["total"] == 1
    with get_sessionmaker()() as db:
        assert db.get(OrientationStudent, ori_id).dorm_status == "CHECKED_IN"
        version = db.get(DormBed, int(bed_id)).version
    request = client.post("/api/v1/student-affairs/dorm/checkout-requests", headers=headers, json={
        "bedId": int(bed_id), "expectedBedVersion": version, "requestType": "DAY_STUDENT",
        "reason": "学生转为走读办理正式退宿", "clientRequestId": "unified-checkout-1",
    })
    assert request.status_code == 200, request.text
    data = request.json()["data"]
    # Newer completed/cancelled history must not hide an older actionable request.
    from app.models import DormCheckoutRequest
    from datetime import datetime
    with get_sessionmaker()() as db:
        pending = db.get(DormCheckoutRequest, int(data["requestId"]))
        for index in range(101):
            db.add(DormCheckoutRequest(
                tenant_id=pending.tenant_id, student_id=pending.student_id,
                stay_id=pending.stay_id, bed_id=pending.bed_id,
                building_id=pending.building_id, room_id=pending.room_id,
                request_type="DAY_STUDENT", source_type="MANUAL",
                reason="历史取消退宿申请", status="CANCELLED",
                client_request_id=f"history-cancelled-{index}",
                requested_at=datetime.utcnow(), requested_by=admin_id,
                cancelled_at=datetime.utcnow(), cancelled_by=admin_id,
            ))
        db.commit()
    queue = client.get("/api/v1/student-affairs/dorm/checkout-requests", headers=headers,
                       params={"status": "PENDING", "page": 1, "pageSize": 20})
    assert queue.status_code == 200, queue.text
    assert queue.json()["data"]["total"] == 1
    assert queue.json()["data"]["items"][0]["requestId"] == data["requestId"]
    confirmed = client.post(f"/api/v1/student-affairs/dorm/checkout-requests/{data['requestId']}/confirm",
                            headers=headers, json={"version": data["version"]})
    assert confirmed.status_code == 200, confirmed.text
    assert dorms(dormStatus="CHECKED_IN")["total"] == 0
    row = next(r for r in dorms()["items"] if r["id"] == str(ori_id))
    assert row["housingStatus"] == "ENDED" and not row["bedId"] and not row["checkinTime"]
    with get_sessionmaker()() as db:
        assert db.get(OrientationStudent, ori_id).dorm_status == "UNASSIGNED"


def test_non_arrival_releases_reservation_and_blocks_early_archive(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DormBed, OrientationStudent
    seeded = _seed_authorities(students=2, beds=3)
    headers = _admin(client)
    batch_id = _create(client, headers, seeded, "ADMIN_AUTO", "NO-SHOW")
    assert client.post(f"{BASE}/{batch_id}/dry-run", headers=headers).status_code == 200
    assert client.post(f"{BASE}/{batch_id}/publish", headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        student = db.get(OrientationStudent, seeded["orientationStudents"][0])
        orientation_batch = student.batch_id
    assert client.post(f"/api/v1/orientation/batches/{orientation_batch}/close", headers=headers).status_code == 400
    first_id = seeded["orientationStudents"][0]
    def disposition(sid, status):
        row = client.get(f"/api/v1/orientation/students/{sid}", headers=headers).json()["data"]["student"]
        result = client.post(f"/api/v1/orientation/students/{sid}/disposition", headers=headers,
            json={"status": status, "reason": "学生已联系学校调整报到安排", "expectedVersion": row["version"]})
        assert result.status_code == 200, result.text
        return client.get(f"/api/v1/orientation/students/{sid}", headers=headers).json()["data"]["student"]
    delayed = disposition(first_id, "DEFERRED")
    assert delayed["housingStatus"] == "RESERVED" and delayed["reportStatus"] == "DELAYED"
    reserved_bed = delayed["bedId"]
    resumed = disposition(first_id, "RESUME")
    assert resumed["housingStatus"] == "RESERVED" and resumed["bedId"] == reserved_bed
    cancelled = disposition(first_id, "CANCELLED")
    assert cancelled["housingStatus"] == "CANCELLED" and not cancelled["bedId"]
    resumed = disposition(first_id, "RESUME")
    assert resumed["housingStatus"] == "CANCELLED" and not resumed["bedId"]
    with get_sessionmaker()() as db:
        assert db.get(DormBed, int(reserved_bed)).status == "VACANT"
    for ori_id in seeded["orientationStudents"]:
        row = client.get(f"/api/v1/orientation/students/{ori_id}", headers=headers).json()["data"]["student"]
        result = client.post(f"/api/v1/orientation/students/{ori_id}/disposition", headers=headers,
            json={"status": "NO_SHOW", "reason": "已联系确认本次不来报到", "expectedVersion": row["version"]})
        assert result.status_code == 200, result.text
        stale = client.post(f"/api/v1/orientation/students/{ori_id}/disposition", headers=headers,
            json={"status": "RESUME", "reason": "学生要求重新办理报到", "expectedVersion": row["version"]})
        assert stale.status_code == 409
    data = client.get(f"{BASE}/{batch_id}", headers=headers).json()["data"]
    assert all(i["status"] == "CANCELLED" for i in data["items"])
    with get_sessionmaker()() as db:
        assert all(db.get(DormBed, bid).status == "VACANT" for bid in seeded["bedIds"])
    assert client.post(f"/api/v1/orientation/batches/{orientation_batch}/close", headers=headers).status_code == 200


def test_checked_in_student_can_supply_materials_but_cannot_rewrite_arrival(client, db_mode):
    from test_orientation_o3_self_service import _seed_o3, _token, _upload
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent
    ids = _seed_o3(db_mode)
    headers = _token(user_id=ids["userId"], student_id=ids["profileId"], student_no=ids["studentNo"], name=ids["name"])
    with get_sessionmaker()() as db:
        row = db.get(OrientationStudent, ids["orientationId"])
        row.report_status, row.stage = "CHECKED_IN", "REGISTERED_PENDING_ENROLLMENT"
        db.commit()
    for path in ("/api/v1/mobile/orientation/my", "/api/v1/portal/orientation/my"):
        mine = client.get(path, headers=headers).json()["data"]["selfService"]
        assert mine["available"] is False and mine["canSubmitMaterials"] is True
    file_id = _upload(client, headers, "after-checkin.txt", b"material supplied after checkin")
    submitted = client.post("/api/v1/portal/orientation/materials", headers=headers,
        json={"materialType": "PHOTO", "fileId": file_id, "clientSubmissionId": "after-checkin-material-1"})
    assert submitted.status_code == 200, submitted.text
    mine = client.get("/api/v1/mobile/orientation/my", headers=headers).json()["data"]
    assert mine["selfService"]["materials"][0]["fileId"] == file_id
    rejected = client.post("/api/v1/portal/orientation/collect", headers=headers, json={"phone": "13800138000", "origin": "湖南长沙", "emergencyContactName": "家长", "emergencyPhone": "13900139000", "confirmed": True})
    assert rejected.status_code == 409, rejected.text


def test_pending_arrival_queue_includes_prepared_before_pagination(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent
    seeded = _seed_authorities(students=6, beds=6)
    headers = _admin(client)
    states = [("ADMITTED", "PREPARED"), ("DEFERRED", "DELAYED"),
              ("NO_SHOW", "NO_SHOW"), ("CANCELLED", "NO_SHOW"),
              ("REGISTERED_PENDING_ENROLLMENT", "CHECKED_IN"), ("ENROLLED", "COLLEGE_CONFIRMED")]
    with get_sessionmaker()() as db:
        for sid, (stage, report) in zip(seeded["orientationStudents"], states):
            row = db.get(OrientationStudent, sid)
            row.stage, row.report_status = stage, report
        db.commit()
    response = client.get("/api/v1/orientation/students", headers=headers,
        params={"pendingArrival": True, "pageSize": 1})
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["total"] == 3 and len(result["items"]) == 1
    response = client.get("/api/v1/orientation/students", headers=headers,
        params={"pendingArrival": True, "reportStatus": "PREPARED", "pageSize": 1})
    result = response.json()["data"]
    assert result["total"] == 1
    assert result["items"][0]["id"] == str(seeded["orientationStudents"][0])
