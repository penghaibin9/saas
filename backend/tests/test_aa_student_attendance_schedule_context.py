from types import SimpleNamespace
import json


def _historical_source():
    evidence = {
        "sourceType": "FORMAL_TEACHING", "termId": "52", "activeBatchId": "41",
        "scheduleItemId": "9007199254740993", "teachingTaskId": "14922",
        "classId": "4666", "teacherKey": "teacher-history", "sessionDate": "2026-09-14",
        "logicalDate": "2026-09-14", "weekNo": 2, "weekday": 1, "slotNo": 1,
        "weekParity": "ALL", "scopeHeadVersion": 3, "publishedAt": "2026-09-01T08:00:00",
        "occurrenceIdentity": "41:9007199254740993:2026-09-14:1",
    }
    attendance = SimpleNamespace(
        id=6171, tenant_id=7, source_type="FORMAL_TEACHING", source_evidence=json.dumps(evidence),
        occurrence_identity=evidence["occurrenceIdentity"], teaching_task_id=14922,
        class_id=4666, teacher_key="teacher-history", session_date="2026-09-14", slot_no=1,
        course_name="历史课程", term_code="2026-2027-1",
    )
    item = SimpleNamespace(
        id=9007199254740993, tenant_id=7, is_deleted=False, batch_id=41, task_id=14922,
        class_id=4666, teacher_key="teacher-history", weekday=1, slot_no=1,
        start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE",
        teacher_name="历史教师", class_name="历史班级", classroom_text="历史教室",
    )
    batch = SimpleNamespace(id=41, tenant_id=7, is_deleted=False, term_id=52, status="SUPERSEDED")
    return attendance, item, batch


def test_historical_source_detail_survives_replaced_batch_and_bigint_identity():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_source_detail
    attendance, item, batch = _historical_source()
    detail = _attendance_source_detail(attendance, item, batch, tenant_id=7)
    assert detail == {
        "verified": True, "reason": "", "sessionId": "6171", "scheduleItemId": "9007199254740993",
        "batchId": "41", "termId": "52", "termCode": "2026-2027-1", "courseName": "历史课程",
        "sessionDate": "2026-09-14", "weekNo": 2, "weekday": 1, "slotNo": 1,
        "scopeHeadVersion": 3, "publishedAt": "2026-09-01T08:00:00",
        "teacherName": "历史教师", "className": "历史班级", "classroom": "历史教室",
    }


def test_historical_source_detail_fails_closed_without_disclosing_source_fields():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_source_detail
    for target, field, value in (
        (0, "source_evidence", "not-json"), (0, "occurrence_identity", "different"),
        (0, "teacher_key", "another"), (1, "tenant_id", 8), (2, "tenant_id", 8),
        (1, "is_deleted", True), (2, "is_deleted", True), (1, "task_id", 999),
        (1, "class_id", 999), (1, "weekday", 2), (1, "slot_no", 2),
        (1, "start_week", 3), (1, "week_parity", "ODD"), (2, "term_id", 999),
        (2, "status", "DRAFT"), (0, "source_type", "ADMIN_SPECIAL"),
    ):
        objects = _historical_source()
        setattr(objects[target], field, value)
        detail = _attendance_source_detail(*objects, tenant_id=7)
        assert detail["verified"] is False
        assert detail["reason"]
        assert set(detail) == {"verified", "reason"}


def test_historical_source_detail_uses_frozen_logical_day_and_never_invents_clock():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_source_detail
    attendance, item, batch = _historical_source()
    evidence = json.loads(attendance.source_evidence)
    evidence.update(sessionDate="2026-09-15", publishedAt=None)
    evidence["occurrenceIdentity"] = "41:9007199254740993:2026-09-15:1"
    attendance.session_date = "2026-09-15"
    attendance.occurrence_identity = evidence["occurrenceIdentity"]
    attendance.source_evidence = json.dumps(evidence)
    item.status = "CHANGED"
    batch.status = "ARCHIVED"
    result = _attendance_source_detail(attendance, item, batch, tenant_id=7)
    assert result["verified"] is True
    assert result["weekday"] == 1
    assert result["publishedAt"] is None
    assert "startTime" not in result and "endTime" not in result


def test_historical_source_detail_rejects_fractional_boolean_and_wrong_evidence_identities():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_source_detail
    for field, value in (
        ("weekNo", True), ("slotNo", 1.5), ("scopeHeadVersion", 0),
        ("scheduleItemId", "0"), ("classId", "900"), ("teachingTaskId", "900"),
        ("teacherKey", "other"), ("sessionDate", "2026-09-13"),
        ("occurrenceIdentity", "other"), ("publishedAt", "not-a-date"),
    ):
        attendance, item, batch = _historical_source()
        evidence = json.loads(attendance.source_evidence)
        evidence[field] = value
        attendance.source_evidence = json.dumps(evidence)
        assert _attendance_source_detail(attendance, item, batch, tenant_id=7)["verified"] is False


def test_historical_source_detail_accepts_retained_states_and_requires_both_sources():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_source_detail
    for batch_status in ("PUBLISHED", "SUPERSEDED", "ARCHIVED"):
        for item_status in ("EFFECTIVE", "CHANGED", "CANCELLED"):
            attendance, item, batch = _historical_source()
            item.status = item_status
            batch.status = batch_status
            assert _attendance_source_detail(attendance, item, batch, tenant_id=7)["verified"] is True
    attendance, item, batch = _historical_source()
    for source_item, source_batch in ((None, batch), (item, None)):
        result = _attendance_source_detail(attendance, source_item, source_batch, tenant_id=7)
        assert result["verified"] is False
        assert set(result) == {"verified", "reason"}


def _session(**overrides):
    values = {
        "source_type": "FORMAL_TEACHING",
        "source_evidence": '{"scheduleItemId":"33071","sessionDate":"2026-09-18","weekNo":3,"slotNo":1}',
        "session_date": "2026-09-18",
        "slot_no": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_student_attendance_exposes_only_matching_formal_occurrence_backlink():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_schedule_context

    assert _attendance_schedule_context(_session()) == {
        "scheduleItemId": "33071",
        "weekNo": 3,
        "occurrenceDate": "2026-09-18",
    }


def test_student_attendance_never_invents_link_for_legacy_or_mismatched_evidence():
    from app.modules.academic_affairs.services.mobile_academic_gaps_service import _attendance_schedule_context

    assert _attendance_schedule_context(_session(source_type="ADMIN_SPECIAL")) == {}
    assert _attendance_schedule_context(_session(source_evidence="not-json")) == {}
    assert _attendance_schedule_context(_session(source_evidence='{"scheduleItemId":"33071","sessionDate":"2026-09-17","weekNo":3,"slotNo":1}')) == {}
    assert _attendance_schedule_context(_session(source_evidence='{"scheduleItemId":"33071","sessionDate":"2026-09-18","weekNo":3,"slotNo":2}')) == {}
