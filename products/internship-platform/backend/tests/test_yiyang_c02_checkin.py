"""Yiyang C02 / G05-G08 targeted acceptance.

These tests deliberately avoid the monolith pytest fixtures. They exercise the Standalone
authority with a small isolated schema and keep external file providers mocked only where
the test is about image derivation rather than storage transport.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from PIL import Image

TID = 1000000000000000001
STUDENT = {
    "tenantId": str(TID),
    "studentNo": "YIYANG-C02-001",
    "realName": "益阳签到学生",
    "userType": "STUDENT",
    "currentRoleCode": "STUDENT",
}
ADMIN = {
    "tenantId": str(TID),
    "realName": "益阳签到审核员",
    "userType": "SCHOOL_ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def c02_db(tmp_path, monkeypatch):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        AttendanceException,
        AuditOutbox,
        EmpCompany,
        InternshipAuditTrail,
        InternshipBatch,
        InternshipCheckin,
        InternshipCheckinExemption,
        InternshipLeave,
        InternshipMakeup,
        InternshipPosition,
        InternshipRecord,
        StudentProfile,
    )

    old_url = settings.DATABASE_URL
    old_secret = settings.JWT_SECRET
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'c02.db').as_posix()}"
    settings.JWT_SECRET = "c02-test-secret-not-for-production"
    db_session._engine = None
    db_session._factory = None
    engine = db_session.get_engine()

    for table in (
        InternshipBatch.__table__,
        StudentProfile.__table__,
        EmpCompany.__table__,
        InternshipPosition.__table__,
        InternshipRecord.__table__,
        InternshipCheckin.__table__,
        AttendanceException.__table__,
        InternshipLeave.__table__,
        InternshipMakeup.__table__,
        InternshipCheckinExemption.__table__,
        InternshipAuditTrail.__table__,
        AuditOutbox.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    fixed = datetime(2026, 9, 27, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    def fixed_clock(name=None):
        zone = ZoneInfo(str(name or "Asia/Shanghai"))
        local = fixed.astimezone(zone)
        offset = int((local.utcoffset() or timedelta()).total_seconds() // 60)
        return zone, local, offset

    from app.modules.internship.services import internship_student_checkin_service as service
    monkeypatch.setattr(service, "_local_clock", fixed_clock)

    try:
        yield {"tmp": tmp_path, "fixed_clock": fixed_clock}
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        settings.JWT_SECRET = old_secret
        db_session._engine = None
        db_session._factory = None


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import EmpCompany, InternshipBatch, InternshipPosition, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="益阳C02签到验收",
            batch_no="YIYANG-C02",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2026, 9, 30),
            planned_count=1,
            status="RUNNING",
            rules_config={"checkin": {"maxAccuracyM": 100}},
        )
        student = StudentProfile(
            tenant_id=TID,
            student_no=STUDENT["studentNo"],
            real_name=STUDENT["realName"],
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        company = EmpCompany(
            tenant_id=TID,
            name="益阳签到验收企业",
            coop_status="ACTIVE",
        )
        db.add_all([batch, student, company])
        db.flush()
        position = InternshipPosition(
            tenant_id=TID,
            company_id=company.id,
            company_name=company.name,
            batch_id=batch.id,
            title="签到验收岗位",
            work_location="湖南省益阳市赫山区产业园",
            work_address="湖南省益阳市赫山区产业园A1",
            status="PUBLISHED",
            headcount=10,
            geofence_lat=28.5800,
            geofence_lng=112.3600,
            geofence_radius_m=300,
        )
        db.add(position)
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=batch.id,
            enterprise_name=company.name,
            position_name=position.title,
            advisor_name="",
            position_id=position.id,
            eligibility_status="QUALIFIED",
            destination_type="ASSIGNED",
            status="ONBOARD",
            risk_level="NONE",
            intern_start_date=datetime(2026, 9, 1),
            intern_end_date=datetime(2026, 9, 30),
        )
        db.add(record)
        db.commit()
        return batch.id, student.id, record.id
    finally:
        db.close()


def test_g05_server_watermark_keeps_original_hash_and_creates_derived_hash(tmp_path, monkeypatch):
    from app.config import settings
    from app.modules.internship.services import internship_checkin_evidence_service as evidence

    original_path = tmp_path / "original.jpg"
    image = Image.new("RGB", (800, 600), (240, 240, 240))
    image.save(original_path, format="JPEG", quality=95)
    original_bytes = original_path.read_bytes()
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    captured = {}

    monkeypatch.setattr(
        evidence.file_access_service,
        "require_file_access",
        lambda file_id, user=None, action="meta": SimpleNamespace(
            id=int(file_id), file_name="original.jpg", mime_type="image/jpeg", sha256=original_sha
        ),
    )
    monkeypatch.setattr(
        evidence.file_service,
        "resolve_download",
        lambda file_id, user=None: (original_path, "original.jpg"),
    )

    def store_bytes(data, filename, **kwargs):
        captured["derived"] = bytes(data)
        captured["filename"] = filename
        return {
            "fileId": "9002",
            "sha256": hashlib.sha256(data).hexdigest(),
            "fileName": filename,
        }

    monkeypatch.setattr(evidence.file_service, "store_bytes", store_bytes)
    monkeypatch.setattr(
        evidence.file_business_binding_service,
        "bind_file_to_business",
        lambda db, **kwargs: captured.setdefault("binding", kwargs),
    )
    old_font = settings.CHECKIN_WATERMARK_FONT_PATH
    settings.CHECKIN_WATERMARK_FONT_PATH = ""
    try:
        result = evidence.watermark_photo(
            original_file_id="9001",
            checkin_id=77,
            watermark_text="2026-09-27 10:30:00 Asia/Shanghai | Yiyang Industrial Park | 28.580000,112.360000",
            actor=STUDENT,
            student_id=88,
            batch_id="99",
            db=object(),
        )
    finally:
        settings.CHECKIN_WATERMARK_FONT_PATH = old_font

    derived_sha = hashlib.sha256(captured["derived"]).hexdigest()
    assert result["originalSha256"] == original_sha
    assert result["watermarkedSha256"] == derived_sha
    assert derived_sha != original_sha
    assert result["watermarkedFileId"] == "9002"
    assert captured["binding"]["subject_type"] == "STUDENT"
    assert captured["binding"]["subject_id"] == 88
    assert captured["binding"]["batch_id"] == "99"
    with Image.open(BytesIO(captured["derived"])) as derived:
        assert derived.size == (800, 600)


def test_g06_g07_overseas_coordinate_system_is_human_review_and_local_date(c02_db):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AttendanceException, InternshipCheckin
    from app.modules.internship.services import internship_student_checkin_service as service

    set_tenant({"tenantId": str(TID)})
    set_current_user(STUDENT)
    batch_id, _student_id, record_id = _seed()

    preflight = service.preflight(
        STUDENT,
        batch_id=str(batch_id),
        timezone_name="Asia/Tokyo",
    )
    assert preflight["date"] == "2026-09-28"
    assert preflight["timezoneName"] == "Asia/Tokyo"
    assert preflight["timezoneOffsetMinutes"] == 540

    result = service.checkin(
        STUDENT,
        {
            "checkinToken": preflight["token"],
            "idempotencyKey": "g07-overseas-1",
            "lat": 35.681236,
            "lng": 139.767125,
            "gpsAccuracy": 12,
            "address": "Tokyo Station",
            "countryRegion": "Japan",
            "coordinateSystem": "WGS84",
            "timezoneName": "Asia/Tokyo",
            "locationProvider": "UNI_WGS84",
        },
        batch_id=str(batch_id),
    )
    assert result["date"] == "2026-09-28"
    assert result["timezoneName"] == "Asia/Tokyo"
    assert result["result"] == "LOCATION_UNCERTAIN"
    assert result["distanceM"] is None

    db = get_sessionmaker()()
    try:
        row = db.query(InternshipCheckin).filter_by(
            tenant_id=TID, internship_id=record_id
        ).one()
        assert row.coordinate_system == "WGS84"
        assert row.timezone_name == "Asia/Tokyo"
        assert row.timezone_offset_minutes == 540
        assert row.country_region == "Japan"
        exc = db.query(AttendanceException).filter_by(
            tenant_id=TID, internship_id=record_id
        ).one()
        assert exc.exception_type == "LOCATION_UNCERTAIN"
    finally:
        db.close()


def test_g08_exemption_review_and_full_calendar_truth(c02_db):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import InternshipCheckin, InternshipLeave, InternshipMakeup
    from app.modules.internship.services import internship_checkin_exemption_service as exemptions
    from app.modules.internship.services import internship_student_checkin_service as checkins

    set_tenant({"tenantId": str(TID)})
    set_current_user(STUDENT)
    batch_id, student_id, record_id = _seed()

    applied = exemptions.apply(STUDENT, {
        "batchId": str(batch_id),
        "internshipId": str(record_id),
        "startDate": "2026-09-24",
        "endDate": "2026-09-24",
        "reason": "参加学校统一活动，当日无需企业现场签到",
    })
    assert applied["status"] == "PENDING"

    set_current_user(ADMIN)
    reviewed = exemptions.review(applied["id"], {
        "action": "APPROVE",
        "comment": "情况核实无误",
        "expectedVersion": applied["version"],
    }, ADMIN)
    assert reviewed["status"] == "APPROVED"

    db = get_sessionmaker()()
    try:
        db.add(InternshipCheckin(
            tenant_id=TID,
            internship_id=record_id,
            checkin_date="2026-09-22",
            checkin_at=datetime(2026, 9, 22, 1, 0),
            result="NORMAL",
        ))
        db.add(InternshipLeave(
            tenant_id=TID,
            internship_id=record_id,
            student_id=student_id,
            leave_type="PERSONAL",
            start_date="2026-09-23",
            end_date="2026-09-23",
            days=1,
            reason="学校集中办理事项",
            status="APPROVED",
        ))
        db.add(InternshipMakeup(
            tenant_id=TID,
            internship_id=record_id,
            student_id=student_id,
            checkin_date="2026-09-25",
            makeup_type="MISSING",
            reason="补录签到",
            status="APPROVED",
        ))
        db.add(InternshipCheckin(
            tenant_id=TID,
            internship_id=record_id,
            checkin_date="2026-09-25",
            checkin_at=datetime(2026, 9, 25, 1, 0),
            result="RECORDED",
        ))
        db.commit()
    finally:
        db.close()

    set_current_user(STUDENT)
    calendar = checkins.calendar(
        STUDENT,
        month="2026-09",
        batch_id=str(batch_id),
        timezone_name="Asia/Shanghai",
    )
    by_date = {item["date"]: item for item in calendar["days"]}
    assert by_date["2026-09-22"]["status"] == "CHECKIN"
    assert by_date["2026-09-23"]["status"] == "LEAVE"
    assert by_date["2026-09-24"]["status"] == "EXEMPT"
    assert by_date["2026-09-25"]["status"] == "MAKEUP"
    assert by_date["2026-09-26"]["status"] == "ABSENT"
    assert by_date["2026-09-27"]["status"] == "PENDING"
    assert by_date["2026-09-26"]["canApplyMakeup"] is True
    assert calendar["summary"]["EXEMPT"] == 1
    assert calendar["summary"]["LEAVE"] == 1
    assert calendar["summary"]["MAKEUP"] == 1


def test_c02_routes_are_registered():
    from app.main import app

    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/mobile/internship/checkin/preflight" in paths
    assert "/api/v1/mobile/internship/checkin" in paths
    assert "/api/v1/mobile/internship/checkin/calendar" in paths
    assert "/api/v1/mobile/internship/context/checkin-exemptions" in paths
    assert "/api/v1/mobile/teacher/internship/context/checkin-exemptions" in paths
