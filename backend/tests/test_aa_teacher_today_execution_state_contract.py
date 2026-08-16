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


def _work_ctx(tid):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(tid)})
    set_current_user({
        "userId": "u_CW2-WORK",
        "tenantId": str(tid),
        "realName": "C-W2工作台教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx_CW2-WORK",
        "loginName": "CW2-WORK",
        "userType": "STAFF",
    })


def _db_session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def test_teacher_work_cues_read_existing_invigilation_and_grade_todo(db_mode):
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom, UnifiedTodo, User
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work

    tid = 1000000000000007320
    _work_ctx(tid)
    db = _db_session()
    user_row = User(
        tenant_id=tid,
        login_name="CW2-WORK",
        real_name="C-W2工作台教师",
        password_hash="test-only-password-hash",
        user_type="TEACHER",
        status="ACTIVE",
    )
    db.add(user_row)
    db.flush()
    batch = AaExamBatch(tenant_id=tid, batch_name="C-W2监考批次", exam_type="FINAL", status="PUBLISHED")
    db.add(batch)
    db.flush()
    course = AaExamCourse(
        tenant_id=tid,
        batch_id=batch.id,
        teaching_task_id=501,
        course_name="数据库原理",
        class_name="软件2401",
        teacher_key="OTHER-TEACHER",
        exam_date="2026-08-16",
        start_time="09:00",
        end_time="11:00",
        status="CONFIRMED",
    )
    db.add(course)
    db.flush()
    room = AaExamRoom(
        tenant_id=tid,
        exam_course_id=course.id,
        room_seq=1,
        classroom_text="教学楼A301",
        capacity=40,
        planned_count=35,
        status="ACTIVE",
    )
    db.add(room)
    db.flush()
    invigilator = AaExamInvigilator(
        tenant_id=tid,
        exam_room_id=room.id,
        teacher_key="CW2-WORK",
        teacher_name="C-W2工作台教师",
        role="CHIEF",
        confirm_status="CONFIRMED",
    )
    db.add(invigilator)
    todo = UnifiedTodo(
        tenant_id=tid,
        source_module="academic-affairs",
        source_biz_type="AA_GRADE_TASK",
        source_biz_id=601,
        todo_type="AA_GRADE_ENTRY",
        assignee_id=user_row.id,
        title="数据库原理成绩录入",
        status="PENDING",
    )
    db.add(todo)
    db.flush()
    user_id = int(user_row.id)
    invigilator_id = int(invigilator.id)
    room_id = int(room.id)
    course_id = int(course.id)
    db.commit()
    db.close()

    db = _db_session()
    result = work.teacher_work_cues(
        db,
        {"userId": f"db-{user_id}", "loginName": "CW2-WORK", "userType": "STAFF"},
        exam_date="2026-08-16",
    )
    db.close()

    assert result["invigilations"] == [{
        "invigilatorId": str(invigilator_id),
        "examRoomId": str(room_id),
        "examCourseId": str(course_id),
        "courseName": "数据库原理",
        "className": "软件2401",
        "examDate": "2026-08-16",
        "startTime": "09:00",
        "endTime": "11:00",
        "classroom": "教学楼A301",
        "role": "CHIEF",
        "confirmStatus": "CONFIRMED",
    }]
    assert len(result["gradeTodos"]) == 1
    assert result["gradeTodos"][0]["todoType"] == "AA_GRADE_ENTRY"
    assert result["gradeTodos"][0]["gradeTaskId"] == "601"
    assert result["gradeTodos"][0]["route"] == "/pages/teacher/academic-affairs/grade-entry?id=601"


def test_teacher_work_cues_reject_unpublished_exam_and_done_grade_todo(db_mode):
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom, UnifiedTodo, User
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work

    tid = 1000000000000007321
    _work_ctx(tid)
    db = _db_session()
    user_row = User(
        tenant_id=tid,
        login_name="CW2-WORK",
        real_name="C-W2工作台教师",
        password_hash="test-only-password-hash",
        user_type="TEACHER",
        status="ACTIVE",
    )
    db.add(user_row)
    db.flush()
    batch = AaExamBatch(tenant_id=tid, batch_name="未发布监考批次", exam_type="FINAL", status="ARRANGED")
    db.add(batch)
    db.flush()
    course = AaExamCourse(
        tenant_id=tid,
        batch_id=batch.id,
        course_name="离散数学",
        exam_date="2026-08-16",
        start_time="14:00",
        end_time="16:00",
        status="CONFIRMED",
    )
    db.add(course)
    db.flush()
    room = AaExamRoom(
        tenant_id=tid,
        exam_course_id=course.id,
        room_seq=1,
        classroom_text="B201",
        capacity=30,
        planned_count=28,
        status="ACTIVE",
    )
    db.add(room)
    db.flush()
    db.add(AaExamInvigilator(
        tenant_id=tid,
        exam_room_id=room.id,
        teacher_key="CW2-WORK",
        teacher_name="C-W2工作台教师",
        role="ASSISTANT",
        confirm_status="ASSIGNED",
    ))
    db.add(UnifiedTodo(
        tenant_id=tid,
        source_module="academic-affairs",
        source_biz_type="AA_GRADE_TASK",
        source_biz_id=602,
        todo_type="AA_GRADE_ENTRY",
        assignee_id=user_row.id,
        title="已完成成绩录入",
        status="DONE",
    ))
    db.flush()
    user_id = int(user_row.id)
    db.commit()
    db.close()

    db = _db_session()
    result = work.teacher_work_cues(
        db,
        {"userId": f"db-{user_id}", "loginName": "CW2-WORK", "userType": "STAFF"},
        exam_date="2026-08-16",
    )
    db.close()
    assert result == {"invigilations": [], "gradeTodos": []}


def test_teacher_work_cues_are_read_only_and_do_not_create_second_authority():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work

    source = inspect.getsource(work)
    for forbidden in (
        "_push_grade_entry_todo",
        "_todo_done_grade_entry",
        "AaExamInvigilator(",
        "UnifiedTodo(",
        "db.add(",
        "db.flush(",
        "db.commit(",
    ):
        assert forbidden not in source
    assert 'AaExamBatch.status == "PUBLISHED"' in source
    assert 'UnifiedTodo.todo_type == _GRADE_TODO' in source
    assert 'UnifiedTodo.status == "PENDING"' in source
