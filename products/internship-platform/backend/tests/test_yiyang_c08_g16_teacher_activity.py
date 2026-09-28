from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.models import (
    InternshipCheckin,
    InternshipTeacherCheckin,
    InternshipTeacherPeriodReport,
)
from app.modules.internship.services import internship_teacher_activity_service as svc


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, scalar_values=None):
        self.scalar_values = list(scalar_values or [])
        self.added = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, _model, ident):
        return SimpleNamespace(id=int(ident), tenant_id=1, is_deleted=False)

    def scalar(self, _query):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def scalars(self, _query):
        return _ScalarRows([])

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = 55

    def commit(self):
        self.committed = True


def _teacher():
    return {
        "userId": "7",
        "realName": "张老师",
        "currentRoleCode": "INTERN_MENTOR",
        "userType": "TEACHER",
    }


def _admin():
    return {
        "userId": "9",
        "realName": "实习管理员",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "SCHOOL_ADMIN",
    }


def test_g16_teacher_checkin_is_not_student_checkin_fact():
    assert InternshipTeacherCheckin.__tablename__ == "t_internship_teacher_checkin"
    assert InternshipCheckin.__tablename__ == "t_internship_checkin"
    assert InternshipTeacherCheckin.__tablename__ != InternshipCheckin.__tablename__


def test_g16_timezone_and_location_are_server_validated():
    name, zone = svc._zone("Asia/Shanghai")
    assert name == "Asia/Shanghai"
    assert zone.key == "Asia/Shanghai"

    with pytest.raises(AppException):
        svc._zone("Not/A_Real_Zone")
    with pytest.raises(AppException):
        svc._location({"latitude": 28.2})
    with pytest.raises(AppException):
        svc._location({"latitude": 91, "longitude": 112})


def test_g16_schoolwide_notice_is_admin_only(monkeypatch):
    monkeypatch.setattr(svc, "_scope_mode", lambda _user: "SCOPED")
    with pytest.raises(AppException):
        svc._require_school_admin(_teacher())

    monkeypatch.setattr(svc, "_scope_mode", lambda _user: "ADMIN_TENANT")
    svc._require_school_admin(_admin())


def test_g16_teacher_checkin_writes_teacher_audit(monkeypatch):
    db = _FakeDb()
    audits = []
    monkeypatch.setattr(svc, "session", lambda: db)
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "_assert_teacher_batch_scope",
        lambda _db, batch_id, _user: SimpleNamespace(id=int(batch_id)),
    )
    monkeypatch.setattr(
        svc,
        "add_audit",
        lambda _db, **kwargs: audits.append(kwargs) or "evt",
    )

    result = svc.checkin(
        _teacher(),
        {
            "batchId": 12,
            "timezoneName": "Asia/Shanghai",
            "latitude": 28.2282,
            "longitude": 112.9388,
            "accuracyM": 12,
            "address": "益阳职业技术学院",
        },
    )

    assert result["batchId"] == "12"
    assert result["teacherUserId"] == "7"
    assert result["alreadyCheckedIn"] is False
    assert db.committed is True
    assert audits[0]["target_type"] == "TEACHER_CHECKIN"
    assert audits[0]["action"] == "TEACHER_CHECKIN_CREATE"
    assert result["result"] == "NORMAL"
    assert result["evidenceAvailable"] is False


def test_g16_teacher_checkin_photo_generates_trusted_watermark(monkeypatch):
    db = _FakeDb()
    audits = []
    evidence_calls = []
    monkeypatch.setattr(svc, "session", lambda: db)
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "_assert_teacher_batch_scope",
        lambda _db, batch_id, _user: SimpleNamespace(id=int(batch_id)),
    )
    monkeypatch.setattr(
        svc,
        "add_audit",
        lambda _db, **kwargs: audits.append(kwargs) or "evt",
    )
    monkeypatch.setattr(
        svc,
        "watermark_photo",
        lambda **kwargs: evidence_calls.append(kwargs) or {
            "originalFileId": "teacher-photo-1",
            "originalSha256": "a" * 64,
            "watermarkedFileId": "teacher-watermark-1",
            "watermarkedSha256": "b" * 64,
        },
    )

    result = svc.checkin(
        _teacher(),
        {
            "batchId": 12,
            "timezoneName": "Asia/Shanghai",
            "latitude": 28.2282,
            "longitude": 112.9388,
            "accuracyM": 8,
            "address": "益阳职业技术学院",
            "photoFileId": "teacher-photo-1",
            "coordinateSystem": "GCJ02",
            "locationProvider": "UNI_GCJ02",
        },
    )

    assert result["evidenceAvailable"] is True
    assert result["photoFileId"] == "teacher-photo-1"
    assert result["watermarkedFileId"] == "teacher-watermark-1"
    assert result["photoSha256"] == "a" * 64
    assert result["watermarkedSha256"] == "b" * 64
    assert evidence_calls[0]["subject_type"] == "TEACHER"
    assert evidence_calls[0]["subject_id"] == 7
    assert evidence_calls[0]["biz_type"] == "INTERNSHIP_TEACHER_CHECKIN"
    assert "张老师" in evidence_calls[0]["watermark_text"]
    assert audits[0]["detail"]["hasTrustedPhotoEvidence"] is True


def test_g16_teacher_photo_requires_location(monkeypatch):
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    with pytest.raises(AppException):
        svc.checkin(
            _teacher(),
            {
                "batchId": 12,
                "timezoneName": "Asia/Shanghai",
                "photoFileId": "teacher-photo-1",
            },
        )


def test_g16_emergency_notice_is_persisted_and_audited(monkeypatch):
    db = _FakeDb(scalar_values=[3])
    audits = []
    monkeypatch.setattr(svc, "session", lambda: db)
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(svc, "_scope_mode", lambda _user: "ADMIN_TENANT")
    monkeypatch.setattr(
        svc,
        "add_audit",
        lambda _db, **kwargs: audits.append(kwargs) or "evt",
    )

    result = svc.publish_emergency_notice(
        _admin(),
        {"batchId": 8, "title": "暴雨紧急提醒", "content": "今天停止现场实习，请留意后续通知。"},
    )

    assert result["status"] == "PUBLISHED"
    assert result["recipientCount"] == 3
    assert result["title"] == "暴雨紧急提醒"
    assert db.committed is True
    assert audits[0]["target_type"] == "EMERGENCY_NOTICE"
    assert audits[0]["action"] == "EMERGENCY_NOTICE_PUBLISH"
    assert audits[0]["detail"]["delivery"] == "PERSISTED_IN_APP"


def test_g16_mobile_routes_are_exposed():
    from app.api.v1.mobile_internship_student import router as student_router
    from app.api.v1.teacher_mobile_internship import router as teacher_router

    teacher_paths = {route.path for route in teacher_router.routes}
    student_paths = {route.path for route in student_router.routes}

    assert "/internship/activity/checkins" in teacher_paths
    assert "/internship/activity/work-reports" in teacher_paths
    assert "/internship/emergency-notices" in teacher_paths
    assert "/mobile/internship/emergency-notices" in student_paths



def test_g16_teacher_period_reports_are_not_daily_work_logs():
    assert InternshipTeacherPeriodReport.__tablename__ == "t_internship_teacher_period_report"
    assert svc._normalize_period("WEEKLY", "2026-W01") == ("WEEKLY", "2026-W01")
    assert svc._normalize_period("MONTHLY", "2026-01") == ("MONTHLY", "2026-01")
    assert svc._normalize_period("SUMMARY", "FINAL") == ("SUMMARY", "SUMMARY")
    with pytest.raises(AppException):
        svc._normalize_period("MONTHLY", "2026-13")


def test_g16_teacher_can_save_weekly_period_report(monkeypatch):
    db = _FakeDb()
    audits = []
    monkeypatch.setattr(svc, "session", lambda: db)
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "_assert_teacher_batch_scope",
        lambda _db, batch_id, _user: SimpleNamespace(id=int(batch_id)),
    )
    monkeypatch.setattr(
        svc,
        "add_audit",
        lambda _db, **kwargs: audits.append(kwargs) or "evt",
    )
    result = svc.save_period_report(
        _teacher(),
        {
            "batchId": 12,
            "reportType": "WEEKLY",
            "periodKey": "2026-W01",
            "content": "本周完成实习巡访、学生沟通、风险核查与企业协调工作。" * 3,
            "studentCount": 18,
            "attachmentFileIds": [],
        },
    )
    assert result["reportType"] == "WEEKLY"
    assert result["periodKey"] == "2026-W01"
    assert db.committed is True
    assert audits[0]["target_type"] == "TEACHER_PERIOD_REPORT"
    assert audits[0]["detail"]["reportType"] == "WEEKLY"


def test_g16_period_report_routes_are_exposed():
    from app.api.v1.teacher_mobile_internship import router as teacher_router
    paths = {route.path for route in teacher_router.routes}
    assert "/internship/activity/period-reports" in paths
