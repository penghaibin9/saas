"""D6：Selection Final → TeachingRoster 唯一真链合同。

本合同不创造新的选课事实，只锁住现有生产真链：
course_selection_router → package-level Selection Final → TeachingRoster →
LOCKED AaSelectionRecord 到教学班名单版本的 projection。
"""
from __future__ import annotations

import inspect

from app.modules.academic_affairs.routers import course_selection_router as selection_router
from app.modules.academic_affairs.services import (
    academic_affairs_selection_service as selection,
)
from app.modules.academic_affairs.services import (
    academic_affairs_selection_roster_projection_service as selection_projection,
)
from app.modules.academic_affairs.services import (
    academic_affairs_teaching_roster_service as teaching_roster,
)


def test_d6_router_uses_package_level_selection_final_service():
    assert selection.__name__.endswith("academic_affairs_selection_final_service")
    assert selection_router.selection_svc is selection
    assert selection_router.selection_svc.lock_batch is selection.lock_batch
    assert selection.lock_batch.__module__.endswith("academic_affairs_selection_final_service")


def test_d6_lock_chain_validates_then_calls_teaching_roster_projection():
    source = inspect.getsource(selection.lock_batch)

    validate = "validation = validate_selection_lock(db, batch)"
    project = "apply_locked_roster_projection(db, validation)"
    assert validate in source
    assert project in source
    assert source.index(validate) < source.index(project)
    assert "batch.status = _base._BATCH_LOCKED" in source


def test_d6_teaching_roster_projects_existing_locked_selection_records_only():
    roster_source = inspect.getsource(teaching_roster.apply_locked_roster_projection)
    projection_source = inspect.getsource(selection_projection.project_selection_course_locked)

    assert "_core.apply_locked_roster_projection(db, validation)" in roster_source
    assert "selection_projection.project_selection_batch_locked(db, int(batch_id))" in roster_source

    assert "AaSelectionRecord" in projection_source
    assert 'AaSelectionRecord.status == "LOCKED"' in projection_source
    assert "create_roster_version(" in projection_source
    assert "AaSelectionRecord(" not in projection_source
    assert "db.add(AaSelectionRecord" not in projection_source
