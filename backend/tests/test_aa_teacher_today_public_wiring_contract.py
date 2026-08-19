from __future__ import annotations

import inspect


def test_mobile_public_teacher_schedule_rewires_to_teacher_today_projection():
    from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as public

    source = inspect.getsource(public.teacher_schedule_my)
    assert "academic_affairs_teacher_today_service" in source
    assert "teacher_today_projection(user)" in source
    assert "_current_term_and_batch" not in source
    assert "teacher_view" not in source


def test_mobile_public_teacher_schedule_pure_reads_execution_state_after_formal_projection():
    from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as public

    source = inspect.getsource(public.teacher_schedule_my)
    assert "academic_affairs_teacher_today_execution_state_service" in source
    assert "enrich_today_execution_state" in source
    assert 'result.get("todayItems") or []' in source
    assert "db.add(" not in source
    assert "db.flush(" not in source
    assert "db.commit(" not in source


def test_mobile_public_teacher_schedule_reuses_mature_invigilation_and_grade_todo_truth():
    from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as public

    source = inspect.getsource(public.teacher_schedule_my)
    assert "academic_affairs_teacher_today_work_service" in source
    assert "teacher_work_cues" in source
    assert 'exam_date=str(result.get("todayDate") or "")' in source
    assert "enriched.update(work_cues)" in source
    assert "_push_grade_entry_todo" not in source
    assert "AaExamInvigilator(" not in source
    assert "UnifiedTodo(" not in source
    assert "db.add(" not in source
    assert "db.flush(" not in source
    assert "db.commit(" not in source


def test_teacher_today_preserves_existing_mobile_schedule_metadata_contract():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    source = inspect.getsource(today.teacher_today_projection)
    assert "_legacy_mobile_meta" in source
    assert '"timeBands"' in inspect.getsource(today._legacy_mobile_meta)
    assert '"timezone"' in inspect.getsource(today._legacy_mobile_meta)
    assert '"currentWeek"' in source
    assert '"todayItems"' in source
    assert '"attendanceRoute"' in source
