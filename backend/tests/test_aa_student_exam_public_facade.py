"""P0-07/P0-12：学生PC与微信公共入口必须使用学校时区和FINISHED可见安全服务。"""
from __future__ import annotations

import inspect


def test_public_mobile_exam_facade_uses_safe_read_service():
    """Verify the stable owner/delegation contract without import-order monkeypatching."""
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as facade
    from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as public_service

    # 对外 canonical 始终是 public_service；实际 exam facade 必须委托安全只读服务。
    assert services.mobile_academic_affairs_service is public_service

    exam_source = inspect.getsource(facade.exam_my)
    options_source = inspect.getsource(facade.exam_defer_options_my)
    apply_source = inspect.getsource(facade.exam_defer_apply_my)
    for source in (exam_source, options_source, apply_source):
        assert "student_exam_read_service as safe_exam" in source
    assert "safe_exam.exam_my(user)" in exam_source
    assert "safe_exam.deferrable_courses(user)" in options_source
    assert "safe_exam.defer_apply(user, body or {})" in apply_source
    assert 'if not isinstance(body, dict)' in apply_source


def test_finished_status_is_in_safe_student_visibility_contract():
    from app.modules.academic_affairs.services import student_exam_read_service as service

    assert "FINISHED" in service._VISIBLE_BATCH_STATUSES
    assert "PUBLISHED" in service._VISIBLE_BATCH_STATUSES
