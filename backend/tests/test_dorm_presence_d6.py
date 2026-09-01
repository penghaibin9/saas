"""D6 Presence Provider / 归寝（真实 MySQL）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from affairs_contract_test_support import role_headers


TID = 1000000000000000001
PC = "/api/v1/student-affairs"
MOBILE = "/api/v1/mobile"


def _student_headers(user_id: int) -> dict[str, str]:
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services import auth_service_db
    db = get_sessionmaker()()
    try:
        user = db.get(User, int(user_id))
        token = auth_service_db.build_login_result(db, user, client_type="STUDENT_MINI")["accessToken"]
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def test_d6_none_unknown_leave_manual_event_scope_and_four_end_contract(client, db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (CsLeave, DormAccessEvent, DormBed, DormBuilding, DormRoom,
                            DormStay, Role, StudentAccountLink, StudentProfile,
                            User, UserRole)
    from app.services import dorm_presence_service as presence

    admin = role_headers("SCHOOL_ADMIN", login_name="school_admin01", real_name="陈校")
    manager = role_headers("DORM_MANAGER", login_name="dorm01", real_name="宿管·李")
    other_manager = role_headers("DORM_MANAGER", login_name="other", real_name="宿管·王")

    db = get_sessionmaker()()
    try:
        student = db.get(StudentProfile, int(db_mode["student"]))
        student.student_no = "D6-PRESENCE-001"
        student.real_name = "D6归寝学生"
        student.gender = "M"
        student.status = "ACTIVE"
        student_user = User(
            tenant_id=TID, login_name=student.student_no, real_name=student.real_name,
            password_hash="test-only", user_type="STUDENT", status="ACTIVE",
        )
        db.add(student_user)
        db.flush()
        db.add(StudentAccountLink(
            tenant_id=TID, student_id=student.id, user_id=student_user.id,
            link_status="ACTIVE", bound_login_name=student_user.login_name,
            bound_student_no=student.student_no, source="MANUAL", bound_at=datetime.utcnow(),
        ))
        role = db.query(Role).filter_by(tenant_id=TID, role_code="STUDENT").first()
        if role is None:
            role = Role(
                tenant_id=TID, role_code="STUDENT", role_name="学生",
                role_type="SYSTEM", status="ACTIVE",
            )
            db.add(role)
            db.flush()
        db.add(UserRole(tenant_id=TID, user_id=student_user.id, role_id=role.id, status="ACTIVE"))
        db.commit()
        student_id = int(student.id)
        student_user_id = int(student_user.id)
    finally:
        db.close()
    student_mobile = _student_headers(student_user_id)

    created = client.post(f"{PC}/dorm/buildings", headers=admin, json={
        "buildingName": "D6归寝楼", "buildingCode": "D6-PRESENCE",
        "genderLimit": "MALE", "managerTeacherKey": "dorm01",
    })
    assert created.status_code == 200, created.text
    building_id = int(created.json()["data"]["buildingId"])
    assert client.post(
        f"{PC}/dorm/buildings/{building_id}/generate", headers=admin,
        json={"floors": 1, "roomsPerFloor": 1, "bedsPerRoom": 1},
    ).status_code == 200
    room = client.get(f"{PC}/dorm/buildings/{building_id}/rooms", headers=admin).json()["data"]["items"][0]
    bed = client.get(f"{PC}/dorm/rooms/{room['roomId']}/beds", headers=admin).json()["data"]["items"][0]
    assert client.post(
        f"{PC}/dorm/beds/{bed['bedId']}/checkin", headers=admin,
        json={"studentId": str(student_id)},
    ).status_code == 200

    # 默认 NONE：不得声称门禁正常，也不得把没有数据判为未归。
    provider = client.get(f"{PC}/dorm/presence/provider", headers=admin)
    assert provider.status_code == 200, provider.text
    provider_data = provider.json()["data"]
    assert provider_data["provider"] == "NONE"
    assert provider_data["providerLabel"] == "未配置"
    assert provider_data["configured"] is False
    assert provider_data["lastSyncAt"] is None
    assert provider_data["healthStatus"] == "DISABLED"
    listing = client.get(f"{PC}/dorm/presence", headers=manager)
    assert listing.status_code == 200, listing.text
    data = listing.json()["data"]
    assert data["items"][0]["studentId"] == str(student_id)
    assert data["items"][0]["status"] == "UNKNOWN"
    assert data["statusCounts"]["UNKNOWN"] == 1
    assert data["statusCounts"]["NOT_RETURNED"] == 0

    # 学生 PC/小程序复用本人接口，显示 UNKNOWN，不显示未归。
    mine = client.get(f"{MOBILE}/affairs/dorm/my", headers=student_mobile)
    assert mine.status_code == 200, mine.text
    assert mine.json()["data"]["presence"]["status"] == "UNKNOWN"
    assert mine.json()["data"]["presenceProvider"]["healthStatus"] == "DISABLED"

    # 教师“宿舍今日”同一口径；越楼栋宿管看不到名单。
    today = client.get(f"{MOBILE}/teacher/affairs/dorm/pending", headers=manager)
    assert today.status_code == 200, today.text
    summary = today.json()["data"]["presenceSummary"]
    assert summary["unknown"] == 1 and summary["tonightNotReturned"] == 0
    denied_scope = client.get(f"{PC}/dorm/presence", headers=other_manager)
    assert denied_scope.status_code == 200
    assert denied_scope.json()["data"]["items"] == []

    # Canonical CsLeave APPROVED 且在有效窗口：优先 ON_LEAVE，不产生未归结论。
    now = datetime.utcnow().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        leave = CsLeave(
            tenant_id=TID, student_id=student_id, cs_student_id=None,
            leave_type="PERSONAL", start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2), status="APPROVED",
            affairs_status="APPROVED", apply_time=now - timedelta(days=1),
        )
        db.add(leave)
        db.commit()
        leave_id = int(leave.id)
    finally:
        db.close()
    on_leave = client.get(f"{PC}/dorm/presence", headers=manager).json()["data"]
    assert on_leave["items"][0]["status"] == "ON_LEAVE"
    assert on_leave["items"][0]["leaveId"] == str(leave_id)
    assert on_leave["statusCounts"]["NOT_RETURNED"] == 0

    # MANUAL 只用于受控人工/适配器测试：事件必须绑定真实在住学生，幂等且不接受生物原始数据。
    fixed_now = datetime(2026, 9, 1, 23, 45)
    manual_policy = {
        **presence.DEFAULT_POLICY, "provider": "MANUAL", "notReturnTime": "23:30",
        "curfewTime": "22:30", "lateGraceMinutes": 15,
    }
    set_tenant(TID)
    db = get_sessionmaker()()
    try:
        leave = db.get(CsLeave, leave_id)
        leave.affairs_status = "CANCELLED"
        raw = {
            "providerEventId": "D6-MANUAL-OUT-001", "studentId": student_id,
            "buildingId": building_id, "eventType": "OUT",
            "eventTime": (fixed_now - timedelta(hours=1)).isoformat(),
            "deviceRef": "manual-duty-desk", "result": "SUCCESS",
            "rawRefHash": "a" * 64,
        }
        first = presence.store_normalized_event(db, raw, provider_code="MANUAL")
        replay = presence.store_normalized_event(db, raw, provider_code="MANUAL")
        assert first["created"] is True and replay == {"eventId": first["eventId"], "created": False}
        db.commit()
        result = presence.evaluate_presence(
            db, student_id=student_id, building_id=building_id,
            now=fixed_now, policy=manual_policy,
        )
        assert result["status"] == "NOT_RETURNED"
        assert db.query(DormAccessEvent).filter_by(student_id=student_id).count() == 1
        try:
            presence.store_normalized_event(db, {
                **raw, "providerEventId": "D6-BAD-BIOMETRIC", "faceTemplate": "forbidden",
            }, provider_code="MANUAL")
        except Exception as exc:
            assert getattr(exc, "biz_code", None) == "SENSITIVE_DATA_FORBIDDEN" or "禁止" in str(exc)
        else:
            raise AssertionError("biometric payload must be rejected")
        try:
            presence.store_normalized_event(db, {
                **raw, "providerEventId": "D6-ZERO", "studentId": 0,
            }, provider_code="MANUAL")
        except Exception:
            pass
        else:
            raise AssertionError("student_id=0 must be rejected")
    finally:
        db.close()

    class BrokenProvider(presence.DormPresenceProvider):
        code = "THIRD_PARTY_CAMPUS"
        def get_events(self, db, **kwargs):
            raise RuntimeError("provider offline")
        def get_device_health(self, db):
            raise RuntimeError("provider offline")
        def normalize_event(self, raw):
            return raw

    db = get_sessionmaker()()
    try:
        failed = presence.evaluate_presence(
            db, student_id=student_id, building_id=building_id, now=fixed_now,
            policy={**manual_policy, "provider": "THIRD_PARTY_CAMPUS"},
            provider=BrokenProvider(),
        )
        assert failed["status"] == "UNKNOWN"
        assert failed["reason"] == "PROVIDER_UNAVAILABLE"
    finally:
        db.close()
        set_tenant(None)
