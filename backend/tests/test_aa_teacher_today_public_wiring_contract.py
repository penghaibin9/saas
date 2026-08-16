from __future__ import annotations

import inspect


def test_mobile_public_teacher_schedule_rewires_to_teacher_today_projection():
    from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as public

    source = inspect.getsource(public.teacher_schedule_my)
    assert "academic_affairs_teacher_today_service" in source
    assert "teacher_today_projection(user)" in source
    assert "_current_term_and_batch" not in source
    assert "teacher_view" not in source


def test_teacher_today_preserves_existing_mobile_schedule_metadata_contract():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    source = inspect.getsource(today.teacher_today_projection)
    assert "_legacy_mobile_meta" in source
    assert '"timeBands"' in inspect.getsource(today._legacy_mobile_meta)
    assert '"timezone"' in inspect.getsource(today._legacy_mobile_meta)
    assert '"currentWeek"' in source
    assert '"todayItems"' in source
    assert '"attendanceRoute"' in source
