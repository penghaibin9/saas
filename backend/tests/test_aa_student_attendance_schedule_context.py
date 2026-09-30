from types import SimpleNamespace


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
