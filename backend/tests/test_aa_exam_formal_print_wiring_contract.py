from __future__ import annotations

import inspect


def test_formal_print_route_is_distinct_from_arrangement_seat_read():
    from app.modules.academic_affairs.routers import exam_core_router
    from app.modules.academic_affairs.routers import exam_incident_closure_router as extension

    route_shapes = {
        (route.path, tuple(sorted(route.methods or ())))
        for route in extension.router.routes
    }
    assert (
        "/academic-affairs/exam/rooms/{roomId}/formal-print",
        ("GET",),
    ) in route_shapes

    formal_source = inspect.getsource(extension.formal_exam_room_print)
    assert "print_service.formal_room_print(user, roomId)" in formal_source
    assert 'require_permission("academicAffairs.exam.view")' in inspect.getsource(extension)

    # The mature arrangement workspace must remain a separate endpoint.  It is allowed
    # to show unpublished seat planning, while official documents are fail-closed.
    ordinary_source = inspect.getsource(exam_core_router.exam_seats)
    assert "exam_svc.room_seats(user, roomId)" in ordinary_source
    assert "formal_room_print" not in ordinary_source
