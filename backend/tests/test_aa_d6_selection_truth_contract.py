"""D6：Selection Final → TeachingRoster 唯一真链合同。

本合同不创造新的选课事实，只锁住现有生产真链：
course_selection_router → package-level Selection Final → TeachingRoster production owner →
LOCKED AaSelectionRecord 到教学班名单版本的 projection。
"""
from __future__ import annotations

import inspect
from pathlib import Path

from app.modules.academic_affairs.routers import course_selection_router as selection_router
from app.modules.academic_affairs.services import (
    academic_affairs_selection_service as selection,
)


_SERVICES = Path(__file__).resolve().parents[1] / "app/modules/academic_affairs/services"


def _source(name: str) -> str:
    return (_SERVICES / name).read_text(encoding="utf-8")


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
    # package 兼容层会在运行时重绑定同名函数；真值合同必须检查 production owner 文件，
    # 不能把兼容 wrapper 的函数对象误当成 TeachingRoster 本体。
    roster_source = _source("academic_affairs_teaching_roster_service.py")
    projection_source = _source("academic_affairs_selection_roster_projection_service.py")

    assert "def apply_locked_roster_projection(db, validation: dict)" in roster_source
    assert "_core.apply_locked_roster_projection(db, validation)" in roster_source
    assert "selection_projection.project_selection_batch_locked(db, int(batch_id))" in roster_source

    assert "def project_selection_course_locked" in projection_source
    assert "AaSelectionRecord" in projection_source
    assert 'AaSelectionRecord.status == "LOCKED"' in projection_source
    assert "create_roster_version(" in projection_source
    assert "AaSelectionRecord(" not in projection_source
    assert "db.add(AaSelectionRecord" not in projection_source
