"""V2-02 独立教学班及名单版本回归。"""
from importlib import util
from pathlib import Path
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


def test_teaching_class_model_indexes_match_0127_names():
    from app.models import (
        AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingClassTeacher,
    )

    class_indexes = {index.name for index in AaTeachingClass.__table__.indexes}
    teacher_indexes = {index.name for index in AaTeachingClassTeacher.__table__.indexes}
    version_indexes = {index.name for index in AaTeachingClassRosterVersion.__table__.indexes}
    member_indexes = {index.name for index in AaTeachingClassMember.__table__.indexes}

    assert {
        "ix_t_aa_teaching_class_tenant_id", "ix_aa_tc_term_id", "ix_aa_tc_course_id",
        "ix_aa_tc_current_roster", "ix_aa_tc_term_course", "ix_aa_tc_status",
    } <= class_indexes
    assert {
        "ix_t_aa_teaching_class_teacher_tenant_id", "ix_aa_tc_teacher_class", "ix_aa_tc_teacher_key",
    } <= teacher_indexes
    assert {
        "ix_t_aa_teaching_class_roster_version_tenant_id", "ix_aa_tc_roster_class",
        "ix_aa_tc_roster_status", "ix_aa_tc_roster_hash",
    } <= version_indexes
    assert {
        "ix_t_aa_teaching_class_member_tenant_id", "ix_aa_tc_member_teaching_class",
        "ix_aa_tc_member_roster_version", "ix_aa_tc_member_student_id",
        "ix_aa_tc_member_student", "ix_aa_tc_member_class",
    } <= member_indexes


def test_roster_hash_is_order_independent_and_deduplicated():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_service import _roster_hash

    assert _roster_hash([3, 1, 2, 2]) == _roster_hash([1, 2, 3])
    assert _roster_hash([1, 2, 3]) != _roster_hash([1, 2, 4])


def test_selection_validation_carries_batch_id(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

    monkeypatch.setattr(service._base, "_legacy_validate_selection_lock", lambda _db, _batch: {
        "valid": True, "issues": [], "selectedRecordCount": 2, "taskStudentCounts": {"8": 2},
    })
    result = service._base.validate_selection_lock(object(), SimpleNamespace(id=17))

    assert result["batchId"] == "17"
    assert result["valid"] is True


def test_locked_projection_calls_legacy_then_version_projection(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

    calls = []
    monkeypatch.setattr(service._base, "_legacy_apply_locked_projection", lambda db, validation: calls.append(("legacy", db, validation["batchId"])))
    monkeypatch.setattr(service._base, "project_selection_batch_locked", lambda db, batch_id: calls.append(("v2", db, str(batch_id))))

    db = object()
    service._base.apply_locked_roster_projection(db, {"batchId": "9", "taskStudentCounts": {"3": 10}})

    assert calls == [("legacy", db, "9"), ("v2", db, "9")]


def test_roster_change_sets_are_version_oriented():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_change_service import _change_sets

    result = _change_sets([1, 2, 3], [2, 3, 4, 4])
    assert result["addedIds"] == [4]
    assert result["removedIds"] == [1]
    assert result["unchangedIds"] == [2, 3]
    assert result["changed"] is True


def test_roster_impact_blocks_attendance_exam_or_grade_but_not_schedule_only():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_change_service import _impact_summary

    schedule_only = _impact_summary(8, 0, 0, 0)
    assert schedule_only["scheduleCount"] == 8
    assert schedule_only["blocked"] is False

    consumed = _impact_summary(8, 2, 1, 1)
    assert consumed["blockingConsumerCount"] == 4
    assert consumed["blocked"] is True
    assert "下游名单迁移" in consumed["blockerMessage"]


def test_selection_managed_class_cannot_be_overwritten_manually():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_change_service import _manual_mode

    assert _manual_mode(True, "ADMIN", "ADMIN_CLASS")["canManualChange"] is False
    assert _manual_mode(False, "SELECTION", "SELECTION_LOCK")["managedBySelection"] is True
    assert _manual_mode(False, "ADMIN", "MANUAL")["canManualChange"] is True


def test_atomic_backfill_report_exposes_existing_skip_and_blocked_counts():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_admin_service import _public_report

    result = _public_report(3, True, [
        {
            "legacyReady": True, "readyForBackfill": True, "existingProjected": True,
            "studentIds": [1], "batchIds": [], "note": "已有一致正式版本",
        },
        {
            "legacyReady": False, "readyForBackfill": False, "existingProjected": False,
            "studentIds": [], "batchIds": [], "note": "选课未锁定",
        },
    ])
    assert result["taskCount"] == 2
    assert result["readyCount"] == 1
    assert result["blockedCount"] == 1
    assert result["alreadyProjectedCount"] == 1
    assert result["toCreateCount"] == 0
    assert "studentIds" not in result["items"][0]
    assert "batchIds" not in result["items"][0]


def test_final_change_scope_is_applied_to_preview_and_create():
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_change_final_service as final

    assert final._base._validate_student_scope is final._validate_student_scope
    assert final.preview_roster_change.__module__.endswith("academic_affairs_teaching_class_change_final_service")
    assert final.create_manual_roster_version.__module__.endswith("academic_affairs_teaching_class_change_final_service")


def test_public_roster_resolver_and_task_service_use_v2_layers():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as roster_service

    assert services.academic_affairs_teaching_class_service.__name__.endswith(
        "academic_affairs_teaching_class_lock_service"
    )
    assert services.academic_affairs_teaching_class_service._base.__name__.endswith(
        "academic_affairs_teaching_class_service"
    )
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


def test_teaching_class_router_exposes_list_detail_backfill_and_version_flow():
    from app.modules.academic_affairs.routers.teaching_class_router import router

    paths = {route.path for route in router.routes}
    assert "/academic-affairs/teaching-classes" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}" in paths
    assert "/academic-affairs/teaching-classes/actions/backfill" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}/roster/impact" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}/roster/versions" in paths


def test_teaching_class_list_keeps_items_and_list_compatibility():
    from app.modules.academic_affairs.routers.teaching_class_router import teaching_class_list
    from app.modules.academic_affairs.routers import teaching_class_router as module

    original = module.query_service.list_teaching_classes
    module.query_service.list_teaching_classes = lambda *_args, **_kwargs: ([{"teachingClassId": "1"}], 1)
    try:
        response = teaching_class_list(page=1, pageSize=30, user={})
    finally:
        module.query_service.list_teaching_classes = original

    assert response["data"]["items"] == [{"teachingClassId": "1"}]
    assert response["data"]["list"] == response["data"]["items"]
    assert response["data"]["total"] == 1


def test_academic_affairs_main_router_mounts_teaching_class_routes():
    from app.modules.academic_affairs.routers import academic_affairs

    paths = {route.path for route in academic_affairs.router.routes}
    assert "/academic-affairs/teaching-classes" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}" in paths
    assert "/academic-affairs/teaching-classes/actions/backfill" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}/roster/impact" in paths
    assert "/academic-affairs/teaching-classes/{teaching_class_id}/roster/versions" in paths


def test_0127_migration_is_single_line_successor_and_idempotent():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0127_aa_teaching_class_roster.py"
    spec = util.spec_from_file_location("aa_migration_0127", migration_path)
    assert spec and spec.loader
    migration = util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "0127_aa_teaching_class_roster"
    assert migration.down_revision == "0126_aa_grade_task_uniqueness_guard"
    assert callable(migration._ensure_index)
    assert callable(migration._ensure_unique)
