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
