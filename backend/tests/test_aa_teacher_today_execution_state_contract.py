import inspect
from types import SimpleNamespace


def test_roster_state_requires_locked_current_version_and_hash_match():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_execution_state_service as state

    teaching_class = SimpleNamespace(
        id=101,
        status="ACTIVE",
        roster_status="LOCKED",
        current_roster_version_id=201,
        current_roster_version_no=3,
    )
    version = SimpleNamespace(
        id=201,
        teaching_class_id=101,
        status="LOCKED",
        version_no=3,
        member_count=2,
        roster_hash=state.roster_hash([11, 12]),
    )
    ready = state._roster_state(teaching_class, version, [12, 11])
    assert ready["rosterReady"] is True
    assert ready["rosterVersionId"] == "201"
    assert ready["rosterMemberCount"] == 2

    version.roster_hash = "bad"
    invalid = state._roster_state(teaching_class, version, [11, 12])
    assert invalid["rosterReady"] is False
    assert "完整性" in invalid["rosterIssue"]


def test_attendance_state_never_picks_one_of_duplicate_formal_sessions():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_execution_state_service as state

    assert state._attendance_state([]) == {
        "attendanceState": "NOT_STARTED",
        "attendanceSessionId": None,
        "attendanceIssue": "",
    }
    one = state._attendance_state([SimpleNamespace(id=301, status="DRAFT")])
    assert one["attendanceState"] == "DRAFT"
    assert one["attendanceSessionId"] == "301"

    conflict = state._attendance_state([
        SimpleNamespace(id=301, status="DRAFT"),
        SimpleNamespace(id=302, status="SUBMITTED"),
    ])
    assert conflict["attendanceState"] == "CONFLICT"
    assert conflict["attendanceSessionId"] is None


def test_action_state_uses_exact_existing_session_route_and_never_recreates_it():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_execution_state_service as state

    row = {
        "attendanceExecutable": True,
        "attendanceRoute": "/pages/teacher/academic-affairs/attendance?teachingTaskId=1&sessionDate=2026-03-02&slotNo=2&scheduleItemId=9",
        "attendanceBlockReason": "",
    }
    ready = {"rosterReady": True, "rosterIssue": ""}

    create = state._action_state(
        row,
        ready,
        {"attendanceState": "NOT_STARTED", "attendanceSessionId": None, "attendanceIssue": ""},
    )
    assert create["attendanceAction"] == "CREATE"
    assert create["attendanceActionLabel"] == "去点名"
    assert create["attendanceRoute"] == row["attendanceRoute"]

    draft = state._action_state(
        row,
        ready,
        {"attendanceState": "DRAFT", "attendanceSessionId": "301", "attendanceIssue": ""},
    )
    assert draft["attendanceAction"] == "OPEN_EXISTING"
    assert draft["attendanceActionLabel"] == "继续点名"
    assert draft["attendanceRoute"] == "/pages/teacher/academic-affairs/attendance?sessionId=301"
    assert draft["attendanceBlockReason"] == ""

    submitted = state._action_state(
        row,
        ready,
        {"attendanceState": "SUBMITTED", "attendanceSessionId": "302", "attendanceIssue": ""},
    )
    assert submitted["attendanceAction"] == "OPEN_EXISTING"
    assert submitted["attendanceActionLabel"] == "查看考勤"
    assert submitted["attendanceRoute"] == "/pages/teacher/academic-affairs/attendance?sessionId=302"

    blocked_roster = state._action_state(
        row,
        {"rosterReady": False, "rosterIssue": "正式教学名单尚未锁定"},
        {"attendanceState": "NOT_STARTED", "attendanceSessionId": None, "attendanceIssue": ""},
    )
    assert blocked_roster["attendanceAction"] == "BLOCKED_ROSTER"
    assert blocked_roster["attendanceRoute"] is None
    assert blocked_roster["attendanceActionLabel"] == "名单未就绪"

    conflict = state._action_state(
        row,
        ready,
        {"attendanceState": "CONFLICT", "attendanceSessionId": None, "attendanceIssue": "重复场次"},
    )
    assert conflict["attendanceAction"] == "CONFLICT"
    assert conflict["attendanceRoute"] is None
    assert conflict["attendanceBlockReason"] == "重复场次"


def test_execution_state_projection_is_strictly_read_only_and_batched():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_execution_state_service as state

    source = inspect.getsource(state.enrich_today_execution_state)
    for forbidden in (
        "ensure_teaching_class_for_task",
        "resolve_versioned_roster",
        "freeze_consumer_snapshot",
        "db.add(",
        "db.flush(",
        "db.commit(",
    ):
        assert forbidden not in source
    assert "AaTeachingClass.teaching_task_id.in_" in source
    assert "AaTeachingClassRosterVersion.id.in_" in source
    assert "AaTeachingClassMember.roster_version_id.in_" in source
    assert "AaAttendanceSession.session_date.in_" in source
