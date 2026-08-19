from __future__ import annotations

import inspect


def test_teacher_schedule_public_response_wires_canonical_invigilation_workbench():
    from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as public

    source = inspect.getsource(public.teacher_schedule_my)

    assert "academic_affairs_invigilation_workbench_service" in source
    assert 'enriched["invigilationWorkbench"]' in source
    assert "project_my_invigilations(" in source
    assert 'from_date=str(result.get("todayDate") or "") or None' in source

    # The mobile projection must stay a reader.  Exam assignment/reassignment remains
    # exclusively owned by the mature exam facade and AaExamInvigilator row.
    for forbidden in (
        "assign_invigilator(",
        "change_invigilator(",
        "AaExamInvigilator(",
        "db.add(",
        "db.flush(",
        "db.commit(",
    ):
        assert forbidden not in source
