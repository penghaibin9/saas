from app.services.todo_route_registry import resolve_todo_route


def test_shared_teacher_review_routes_keep_business_type_with_overlapping_ids():
    for kind in ('FUNDING_APPROVAL', 'AID_APPROVAL', 'AID_ADJUST', 'DISCIPLINE_APPROVAL', 'DISCIPLINE_REMOVE'):
        route = resolve_todo_route(kind, 1, client='teacherMini')
        assert route['path'] == '/pages/teacher/affairs-review/index'
        assert route['query'] == {'recordId': '1', 'type': kind}
        # This route currently opens the authorized queue, not an exact funding detail.
        assert route['exact'] is False
    student = resolve_todo_route('FUNDING_APPROVAL', 1, client='studentMini')
    assert student['path'] == '/pages/student/affairs/funding'
    assert student['query'] == {'recordId': '1'}


def test_reduction_todos_have_role_safe_exact_routes_and_cannot_be_completed_as_ack():
    from app.services.workbench_todo_service import _completion_mode
    from app.services.mobile_performance_service import _group_value
    for kind in ("FEE_REDUCTION_REVIEW", "FEE_REDUCTION_FULFILL"):
        for client, prefix in (("pc", "/admin/student-affairs/"), ("teacherMini", "/pages/teacher/")):
            target = resolve_todo_route(kind, "9007199254740993", client=client)
            assert target["path"].startswith(prefix)
            assert target["query"]["recordId"] == "9007199254740993"
            assert target["exact"] is True
        assert resolve_todo_route(kind, "1", client="studentMini") is None
        assert _completion_mode(kind) == "DOMAIN_COMMAND"
    assert _group_value("FEE_REDUCTION_REVIEW") == "review"
    assert _group_value("FEE_REDUCTION_FULFILL") == "confirm"


def test_dorm_rectification_routes_keep_original_object_and_recipient():
    from app.services.message_action_registry import resolve_route
    teacher = resolve_todo_route('DORM_RECTIFICATION_RECHECK', '9007199254740993', client='teacherMini')
    assert teacher['query'] == {'recordId': '9007199254740993', 'tab': 'recheck'}
    assert teacher['exact'] is True
    student = resolve_todo_route('DORM_RECTIFICATION', '9007199254740993', client='studentMini')
    assert student['query'] == {'rectificationId': '9007199254740993'}
    assert student['exact'] is True
    assert resolve_todo_route('DORM_RECTIFICATION_RECHECK', '1', client='studentMini') is None
    notice = resolve_route('STUDENT_AFFAIRS_DORM_RECTIFICATION', client='studentMini')
    assert notice['exact'] is True
    assert notice['focusParam'] == 'rectificationId'
    assert resolve_route('STUDENT_AFFAIRS_DORM_RECTIFICATION', client='teacherMini')['ok'] is False


def test_rectification_message_focus_does_not_reinterpret_general_dorm_messages():
    from app.services.mobile_action_service import build_message_action
    action = build_message_action('STUDENT_AFFAIRS_DORM_RECTIFICATION', {'rectificationId': '9007199254740993'})
    assert action['target']['query'] == {'rectificationId': '9007199254740993'}
    assert action['target']['routeExact'] is True
    general = build_message_action('AFFAIRS_DORM', {'recordId': '1'})
    assert general['target']['query'] == {'recordId': '1'}
    assert general['target']['routeExact'] is False


def test_room_rectification_todo_has_teacher_original_record_target():
    target = resolve_todo_route('DORM_RECTIFICATION', '9007199254740993', client='teacherMini')
    assert target['path'] == '/pages/teacher/dorm-review/index'
    assert target['query'] == {'recordId': '9007199254740993', 'tab': 'recheck'}
    assert target['exact'] is True
