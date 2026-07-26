"""V2-02 独立教学班及名单版本回归。"""
from types import SimpleNamespace


def test_teaching_class_models_have_required_version_fields():
    from app.models import (
        AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingClassTeacher,
    )

    assert {
        "teaching_task_id", "term_id", "course_id", "class_code", "class_name",
        "class_type", "current_roster_version_id", "current_roster_version_no",
        "roster_status", "status",
    } <= set(AaTeachingClass.__mapper__.attrs.keys())
    assert {
        "teaching_class_id", "teacher_key", "role_type", "start_week", "end_week", "status",
    } <= set(AaTeachingClassTeacher.__mapper__.attrs.keys())
    assert {
        "teaching_class_id", "version_no", "source_type", "source_id", "member_count",
        "roster_hash", "status", "locked_at", "locked_by",
    } <= set(AaTeachingClassRosterVersion.__mapper__.attrs.keys())
    assert {
        "teaching_class_id", "roster_version_id", "student_id", "source_type", "source_id", "status",
    } <= set(AaTeachingClassMember.__mapper__.attrs.keys())


def test_roster_hash_is_order_independent_and_deduplicated():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_service import _roster_hash

    assert _roster_hash([3, 1, 2, 2]) == _roster_hash([1, 2, 3])
    assert _roster_hash([1, 2, 3]) != _roster_hash([1, 2, 4])


def test_selection_validation_carries_batch_id(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

    monkeypatch.setattr(service, "_legacy_validate_selection_lock", lambda _db, _batch: {
        "valid": True, "issues": [], "selectedRecordCount": 2, "taskStudentCounts": {"8": 2},
    })
    result = service.validate_selection_lock(object(), SimpleNamespace(id=17))

    assert result["batchId"] == "17"
    assert result["valid"] is True


def test_locked_projection_calls_legacy_then_version_projection(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

    calls = []
    monkeypatch.setattr(service, "_legacy_apply_locked_projection", lambda db, validation: calls.append(("legacy", db, validation["batchId"])))
    monkeypatch.setattr(service, "project_selection_batch_locked", lambda db, batch_id: calls.append(("v2", db, str(batch_id))))

    db = object()
    service.apply_locked_roster_projection(db, {"batchId": "9", "taskStudentCounts": {"3": 10}})

    assert calls == [("legacy", db, "9"), ("v2", db, "9")]


def test_public_roster_resolver_and_task_service_use_v2_layers():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as roster_service

    assert roster_service.resolve_teaching_task_roster.__module__.endswith(
        "academic_affairs_teaching_class_service"
    )
    assert roster_service.apply_locked_roster_projection.__module__.endswith(
        "academic_affairs_teaching_class_service"
    )
    assert services.academic_affairs_task_service.__name__.endswith(
        "academic_affairs_task_teaching_class_facade"
    )
    assert services.academic_affairs_task_service._base.__name__.endswith(
        "academic_affairs_task_program_gate_facade"
    )


def test_teaching_class_router_exposes_list_detail_and_backfill():
    from app.modules.academic_affairs.routers.teaching_class_router import router

    paths = {route.path for route in router.routes}
    assert "/academic-affairs/teaching-classes" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}" in paths
    assert "/academic-affairs/teaching-classes/actions/backfill" in paths


def test_0127_migration_is_single_line_successor():
    import importlib

    migration = importlib.import_module("alembic.versions.0127_aa_teaching_class_roster")
    assert migration.revision == "0127_aa_teaching_class_roster"
    assert migration.down_revision == "0126_aa_grade_task_uniqueness_guard"
