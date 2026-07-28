"""R8 独立教学班与名单版本兼容迁移回归。"""
from pathlib import Path


def test_empty_selection_roster_has_stable_hash():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_service import _roster_hash

    assert _roster_hash([]) == _roster_hash(set())
    assert _roster_hash([]) != _roster_hash([1])


def test_r8_compat_layer_allows_only_selection_empty_version():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_teaching_class_compat_migration_service.py"
    ).read_text(encoding="utf-8")

    assert 'source != "SELECTION_LOCK"' in source
    assert "member_count=len(ids)" in source
    assert "project_selection_course_locked" in source
    assert "AaSelectionRecord.status == \"LOCKED\"" in source
    assert "旧版本只保留历史" in source


def test_locked_manual_drop_projects_new_roster_version_in_same_transaction():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_selection_service.py"
    ).read_text(encoding="utf-8")

    admin_drop = source[source.index("def admin_drop("):source.index("def reselect(")]
    drop_at = admin_drop.index("record.status = _REC_DROPPED")
    project_at = admin_drop.index("roster_projection.apply_admin_drop")
    commit_at = admin_drop.index("db.commit()")
    assert drop_at < project_at < commit_at
    assert "consumer_counts" in admin_drop
    assert "for_update=True" in admin_drop


def test_public_selection_and_teaching_class_paths_use_canonical_entrypoints():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import (
        academic_affairs_teaching_class_compat_migration_service as compat,
    )

    teaching_class = services.academic_affairs_teaching_class_service
    assert teaching_class.__name__.endswith("academic_affairs_teaching_class_service")
    assert teaching_class.create_roster_version.__module__.endswith(
        "academic_affairs_teaching_class_service"
    )
    assert compat.create_roster_version.__module__.endswith(
        "academic_affairs_teaching_class_compat_migration_service"
    )
    assert teaching_class.create_roster_version is not compat.create_roster_version

    selection = services.academic_affairs_selection_service
    assert selection.__name__.endswith("academic_affairs_selection_final_service")
    assert selection.admin_drop.__module__.endswith("academic_affairs_selection_service")


def test_migration_remains_additive_and_keeps_history_tables():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "alembic/versions/0127_aa_teaching_class_roster.py").read_text(encoding="utf-8")

    for table in (
        "t_aa_teaching_class",
        "t_aa_teaching_class_teacher",
        "t_aa_teaching_class_roster_version",
        "t_aa_teaching_class_member",
    ):
        assert table in migration
    assert "不删除或改写 AaTeachingTask 历史字段" in migration
    assert "SUPERSEDED" in (
        root / "app/modules/academic_affairs/services/academic_affairs_teaching_class_service.py"
    ).read_text(encoding="utf-8")
