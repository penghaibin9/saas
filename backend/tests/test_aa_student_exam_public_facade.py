"""P0-07/P0-12：学生PC与微信公共入口必须使用学校时区和FINISHED可见安全服务。"""


def test_public_mobile_exam_facade_uses_safe_read_service(monkeypatch):
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import mobile_academic_exam_safety_facade as facade

    seen = []
    monkeypatch.setattr(facade._safe_exam, "exam_my", lambda user: seen.append(("exam", user)) or {"items": []})
    monkeypatch.setattr(
        facade._safe_exam,
        "deferrable_courses",
        lambda user: seen.append(("options", user)) or {"items": []},
    )
    monkeypatch.setattr(
        facade._safe_exam,
        "defer_apply",
        lambda user, body: seen.append(("apply", user, body)) or {"status": "COUNSELOR_REVIEW"},
    )

    user = {"userType": "STUDENT", "studentId": "1"}
    assert services.mobile_academic_affairs_service is facade
    assert services.mobile_academic_affairs_service.exam_my(user) == {"items": []}
    assert services.mobile_academic_affairs_service.exam_defer_options_my(user) == {"items": []}
    assert services.mobile_academic_affairs_service.exam_defer_apply_my(user, {"examCourseId": "9"}) == {
        "status": "COUNSELOR_REVIEW"
    }
    assert [row[0] for row in seen] == ["exam", "options", "apply"]


def test_finished_status_is_in_safe_student_visibility_contract():
    from app.modules.academic_affairs.services import student_exam_read_service as service

    assert "FINISHED" in service._VISIBLE_BATCH_STATUSES
    assert "PUBLISHED" in service._VISIBLE_BATCH_STATUSES
