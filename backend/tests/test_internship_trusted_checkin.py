"""Production checks for geofenced, retry-safe mobile internship check-ins."""
from __future__ import annotations

TID = 1000000000000000001


def _student(sno):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "student", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mentor(name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER", "tid": "x",
        "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _seed_geofenced_record(student_no="CHECKIN-A", advisor="mentor-a"):
    from app.db.session import get_sessionmaker
    from app.models import EmpCompany, InternshipPosition, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        student = StudentProfile(tenant_id=TID, student_no=student_no, real_name="checkin student",
                                 current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        company = EmpCompany(tenant_id=TID, name="Checkin Co", coop_status="ACTIVE")
        db.add_all([student, company]); db.flush()
        position = InternshipPosition(tenant_id=TID, company_id=company.id, company_name=company.name,
                                      title="operator", status="PUBLISHED", headcount=10,
                                      geofence_lat=30.5000, geofence_lng=114.3000, geofence_radius_m=100)
        db.add(position); db.flush()
        record = InternshipRecord(tenant_id=TID, student_id=student.id, advisor_name=advisor,
                                  enterprise_name=company.name, position_name=position.title,
                                  position_id=position.id, status="ONBOARD")
        db.add(record); db.commit()
        return record.id
    finally:
        db.close()


def test_geofenced_checkin_is_idempotent_and_records_distance(client, db_mode):
    _seed_geofenced_record()
    headers = _student("CHECKIN-A")
    payload = {"lat": 30.5001, "lng": 114.3001, "gpsAccuracy": 8,
               "deviceRiskFlag": "normal", "idempotencyKey": "mobile-retry-001"}
    first = client.post("/api/v1/mobile/internship/checkin", json=payload, headers=headers)
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["result"] == "NORMAL" and data["distanceM"] < 100
    assert data["geofenceConfigured"] is True
    replay = client.post("/api/v1/mobile/internship/checkin", json=payload, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == data["id"]
    assert replay.json()["data"]["idempotentReplay"] is True


def test_mock_location_exception_can_be_appealed_and_teacher_decided(client, db_mode):
    _seed_geofenced_record("CHECKIN-B", "mentor-b")
    headers = _student("CHECKIN-B")
    checked = client.post("/api/v1/mobile/internship/checkin", json={
        "lat": 30.5000, "lng": 114.3000, "deviceRiskFlag": "mock", "note": "GPS signal issue"},
        headers=headers)
    assert checked.status_code == 200 and checked.json()["data"]["result"] == "MOCK_LOCATION"

    from app.db.session import get_sessionmaker
    from app.models import AttendanceException, FileObject
    db = get_sessionmaker()()
    try:
        exc = db.query(AttendanceException).filter_by(tenant_id=TID).one()
        file_obj = FileObject(tenant_id=TID, file_key="checkin/evidence.pdf", file_name="evidence.pdf",
                              ext="pdf", size_bytes=12, biz_type="INTERNSHIP", status="STORED")
        db.add(file_obj); db.flush(); file_id, exception_id = str(file_obj.id), str(exc.id); db.commit()
    finally:
        db.close()
    appeal = client.post(f"/api/v1/mobile/internship/exceptions/{exception_id}/appeal",
                         json={"note": "I was on site and attach the attendance proof.", "fileId": file_id},
                         headers=headers)
    assert appeal.status_code == 200 and appeal.json()["data"]["appealStatus"] == "PENDING"
    reviewed = client.post(f"/api/v1/internship/exceptions/{exception_id}/handle",
                           json={"action": "REASONABLE", "comment": "Evidence checked and accepted."},
                           headers=_mentor("mentor-b"))
    assert reviewed.status_code == 200
    db = get_sessionmaker()()
    try:
        assert db.get(AttendanceException, int(exception_id)).appeal_status == "ACCEPTED"
    finally:
        db.close()
