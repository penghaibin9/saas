"""考务结束、异常闭环与归档门禁回归。"""


def test_closure_error_lists_all_unfinished_exam_dimensions():
    from app.modules.academic_affairs.services.academic_affairs_exam_facade import _closure_error

    error = _closure_error({
        "activeCourseCount": 2,
        "pendingCourses": 1,
        "notStartedSeats": 3,
        "activeDefers": 2,
        "unresolvedIncidents": 4,
    })

    assert error is not None
    assert error.http_status == 409
    assert "待确认考试课程 1 门" in error.message
    assert "未登记到考状态考生 3 人" in error.message
    assert "在途缓考申请 2 条" in error.message
    assert "未闭环考场异常 4 条" in error.message


def test_closure_error_passes_only_when_exam_has_courses_and_all_work_is_closed():
    from app.modules.academic_affairs.services.academic_affairs_exam_facade import _closure_error

    assert _closure_error({
        "activeCourseCount": 2,
        "pendingCourses": 0,
        "notStartedSeats": 0,
        "activeDefers": 0,
        "unresolvedIncidents": 0,
    }) is None


def test_empty_exam_batch_cannot_be_finished_or_archived():
    from app.modules.academic_affairs.services.academic_affairs_exam_facade import _closure_error

    error = _closure_error({
        "activeCourseCount": 0,
        "pendingCourses": 0,
        "notStartedSeats": 0,
        "activeDefers": 0,
        "unresolvedIncidents": 0,
    })

    assert error is not None
    assert "没有有效考试课程" in error.message


def test_public_exam_service_points_to_closure_facade():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_exam_service.finish_batch.__module__.endswith(
        "academic_affairs_exam_facade"
    )
    assert services.academic_affairs_exam_service.archive_batch.__module__.endswith(
        "academic_affairs_exam_facade"
    )
    assert callable(services.academic_affairs_exam_service.resolve_incident)
