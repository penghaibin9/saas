"""INT-only contracts for the final Academic attendance handoff.

These assertions belong to the integration owner rather than C's owner test file.
They prove the compatibility facade, relation guards, and persisted source authority
without mutating C-owned contract history.
"""
from __future__ import annotations

import importlib
import inspect


def test_int_attendance_facades_resolve_to_final_relation_aware_authority():
    from app.modules.academic_affairs import services as service_package
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as public_service

    compatibility_service = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_attendance_service"
    )
    service = service_package.academic_affairs_attendance_service

    authoritative_entrypoints = (
        "create_session",
        "get_session",
        "mark_attendance",
        "submit_session",
        "list_sessions",
        "attendance_stats",
    )
    for name in authoritative_entrypoints:
        assert getattr(compatibility_service, name) is getattr(public_service, name), name
        assert getattr(service, name) is getattr(public_service, name), name

    guarded_entrypoints = {
        "create_session": (
            "academic_affairs_attendance_teacher_relation_guard",
            "_attendance_teacher_relation_guard",
        ),
        "get_session": (
            "academic_affairs_attendance_teacher_relation_guard",
            "_attendance_teacher_relation_guard",
        ),
        "mark_attendance": (
            "academic_affairs_attendance_teacher_relation_guard",
            "_attendance_teacher_relation_guard",
        ),
        "submit_session": (
            "academic_affairs_attendance_teacher_relation_guard",
            "_attendance_teacher_relation_guard",
        ),
        "list_sessions": (
            "academic_affairs_attendance_teacher_relation_read_guard",
            "_attendance_teacher_relation_read_guard",
        ),
        "attendance_stats": (
            "academic_affairs_attendance_teacher_relation_read_guard",
            "_attendance_teacher_relation_read_guard",
        ),
    }
    for name, (guard_module, guard_marker) in guarded_entrypoints.items():
        fn = getattr(public_service, name)
        if fn.__module__.endswith("academic_affairs_attendance_public_service"):
            continue
        assert fn.__module__.endswith(guard_module), (name, fn.__module__)
        assert getattr(fn, guard_marker, False) is True, name


def test_int_persisted_source_authority_overrides_legacy_session_marker():
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    backfilled_special = service._with_source_type(
        {"sessionType": "常规", "sourceType": "ADMIN_SPECIAL"}
    )
    assert backfilled_special["sourceType"] == "ADMIN_SPECIAL"
    assert backfilled_special["sourceLabel"] == "管理员特殊补录"

    invalid = service._with_source_type(
        {"sessionType": "常规", "sourceType": "BROKEN_SOURCE"}
    )
    assert invalid["sourceType"] == "UNKNOWN"
    assert invalid["sourceLabel"] == "来源待治理"


def test_int_admin_special_stats_prefers_persisted_source_type():
    from app.models import AaAttendanceSession
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    condition = service._stats_session_type_condition(AaAttendanceSession, "ADMIN_SPECIAL")
    sql = str(condition.compile(compile_kwargs={"literal_binds": True}))
    assert "source_type" in sql
    assert "ADMIN_SPECIAL" in sql
    assert " = " in sql
    assert "IS NULL" in sql


def test_int_relation_guard_persists_attendance_provenance_fields():
    from app.modules.academic_affairs.services import academic_affairs_attendance_teacher_relation_guard as guard

    source = inspect.getsource(guard)
    for required in (
        "teaching_task_id=",
        "occurrence_identity=",
        "source_type=",
        "source_reason=",
        "source_evidence=",
    ):
        assert required in source, required
