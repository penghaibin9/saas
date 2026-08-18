from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_c_attendance_has_one_command_transaction_owner():
    public = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py"
    )
    command = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_teacher_relation_guard.py"
    )
    read_guard = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_teacher_relation_read_guard.py"
    )

    # Public service is a stable facade, not a second transaction implementation.
    assert "AaAttendanceSession(" not in public
    assert "_guard_no_duplicate_formal_session" not in public
    assert "return relation_guard.create_session(user, body)" in public
    assert "return relation_guard.get_session(session_id, user)" in public
    assert "return relation_guard.mark_attendance(session_id, user, body)" in public
    assert "return relation_guard.submit_session(session_id, user)" in public
    assert "return read_guard.list_sessions(" in public
    assert "return read_guard.attendance_stats(" in public

    # The facade must not eagerly import the mature base service during package init;
    # doing so closes a TeachingRoster -> TeachingClass -> TeachingRoster import cycle.
    assert "def _canonical_service():" in public
    assert "_canonical = importlib.import_module(" not in public
    assert 'return _canonical_service().session()' in public
    assert 'return _canonical_service().attendance_task_executable(status)' in public

    # The sole command owner persists formal occurrence/source provenance.
    assert "AaAttendanceSession(" in command
    for needle in (
        "teaching_task_id=int(task.id) if task else None",
        "occurrence_identity=occurrence_identity",
        "source_type=source_type",
        "source_reason=special_reason if is_admin_special else None",
        "source_evidence=source_evidence",
        "teacher_authority.require_teacher",
        "_guard_no_duplicate_occurrence",
    ):
        assert needle in command

    # Relation-aware reads remain bounded and separate from command mutation.
    assert "yield_per=500" in read_guard
    assert "select(func.count())" in read_guard
    assert "TEACHING_CLASS_TEACHER_BY_OCCURRENCE_WEEK" in read_guard


def test_c_w5_executable_evidence_assets_cover_the_full_teacher_chain():
    live = _read("scripts/e2e_academic_affairs_live_flow.py")
    round3 = _read("scripts/e2e_academic_affairs_round3.py")

    # One live-flow execution orders schedule/attendance, exam and grade domains.
    order = (
        "chain3_schedule_attendance()",
        "chain4_selection_exam()",
        "chain5_grades_warning()",
    )
    positions = [live.index(marker) for marker in order]
    assert positions == sorted(positions)

    # Schedule/change + invigilation + return/resubmit/publish are executable facts,
    # not merely a checklist in the C task document.
    for marker in (
        'C3.schedule_publish',
        'C3.schedule_four_end_read',
        'C3.schedule_change_apply',
        'C4.exam_invigilator',
        'C5.grade_draft',
        'C5.grade_submit',
        'C5.grade_college_return',
        'C5.grade_publish',
        'C5.transcript_four_end',
        'C0.multi_login',
        'C0.logout_invalidates_token',
    ):
        assert marker in live

    # Round3 owns the strict formal occurrence -> mark -> submit evidence.  The broad
    # live-flow script intentionally remains a cross-domain smoke harness.
    assert 'R3.att_submit' in round3
    assert '/attendance/sessions/{sid}/mark' in round3
    assert '/attendance/sessions/{sid}/submit' in round3
    assert 'no ScopeHead-active formal attendance occurrence accepted' in round3

    # Grade resubmission must be a real second command after college RETURN.
    return_pos = live.index('C5.grade_college_return')
    publish_pos = live.index('C5.grade_publish')
    between = live[return_pos:publish_pos]
    assert between.count('/grade-tasks/{gtid}/submit') >= 1
    assert 'college-review' in between and '"APPROVE"' in between
