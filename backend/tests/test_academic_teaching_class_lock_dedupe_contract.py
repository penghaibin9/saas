"""教务教学班名单旧 lock 路径必须保持纯兼容层，不再拥有第二套写事务。"""
from __future__ import annotations

import importlib
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SERVICES = BACKEND / "app/modules/academic_affairs/services"

FORWARDED = (
    "create_roster_version",
    "ensure_teaching_class_for_task",
    "resolve_teaching_task_roster",
    "project_selection_batch_locked",
    "sync_batch_teaching_classes",
)


def test_legacy_lock_path_forwards_to_canonical_function_objects():
    canonical = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_teaching_class_service"
    )
    legacy = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_teaching_class_lock_service"
    )

    assert legacy._base is canonical
    for name in FORWARDED:
        assert getattr(legacy, name) is getattr(canonical, name), (
            f"{name} 必须直接复用正式 teaching_class_service，禁止恢复第二套实现"
        )


def test_legacy_lock_file_contains_no_roster_write_state_machine():
    source = (SERVICES / "academic_affairs_teaching_class_lock_service.py").read_text(encoding="utf-8")
    for forbidden in (
        "AaTeachingClassRosterVersion",
        "AaTeachingClassMember",
        "with_for_update",
        "db.query(",
        "db.begin_nested(",
        "current_roster_version_id =",
        "roster_status =",
    ):
        assert forbidden not in source, f"legacy lock path regained write logic: {forbidden}"


def test_roster_change_scope_guard_uses_canonical_teaching_class_service():
    source = (
        SERVICES / "academic_affairs_teaching_class_change_final_service.py"
    ).read_text(encoding="utf-8")
    assert "academic_affairs_teaching_class_service as _teaching_class" in source
    assert "academic_affairs_teaching_class_lock_service as _teaching_class" not in source
