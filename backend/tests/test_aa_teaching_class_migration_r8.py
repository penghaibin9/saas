"""R8 独立教学班与名单版本兼容迁移回归。"""
from pathlib import Path


def test_empty_selection_roster_has_stable_hash():
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_service import _roster_hash

    assert _roster_hash([]) == _roster_hash(set())
    assert _roster_hash([]) != _roster_hash([1])


def test_r8_compat_layer_delegates_to_current_roster_owners():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_teaching_class_compat_migration_service.py"
    ).read_text(encoding="utf-8")

    assert '_canonical.create_roster_version(' in source
    assert '_selection_projection._create_empty_selection_version(' in source
    assert 'source != "SELECTION_LOCK"' in source
    assert "选课空名单版本必须绑定真实选课批次" in source
    assert "project_selection_course_locked = _selection_projection.project_selection_course_locked" in source
    assert "project_selection_batch_locked = _selection_projection.project_selection_batch_locked" in source

    # 兼容层不得重新长出第二套名单写事务。
    for forbidden in (
        "AaTeachingClassRosterVersion",
        "AaTeachingClassMember",
        "with_for_update",
        "db.query(",
        "db.add(",
        "db.flush(",
    ):
        assert forbidden not in source, f"compat duplicate roster transaction returned: {forbidden}"


def test_locked_manual_adjust_projects_new_roster_version_in_same_transaction():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_selection_final_service.py"
    ).read_text(encoding="utf-8")

    adjust = source[source.index("def adjust_record("):]
    consumer_at = adjust.index("consumer_counts(")
    drop_at = adjust.index("record.status = _base._REC_DROPPED")
    flush_at = adjust.index("db.flush()")
    project_at = adjust.index("roster_projection.project_selection_course_locked(")
    commit_at = adjust.index("db.commit()")
    assert consumer_at < drop_at < flush_at < project_at < commit_at
    assert 'record.status != _base._REC_LOCKED' in adjust
    assert 'batch.status != _base._BATCH_LOCKED' in adjust
    assert ".with_for_update().first()" in adjust


def test_public_selection_and_teaching_class_paths_use_canonical_entrypoints():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import (
        academic_affairs_selection_roster_projection_service as projection,
        academic_affairs_teaching_class_compat_migration_service as compat,
    )

    teaching_class = services.academic_affairs_teaching_class_service
    assert teaching_class.__name__.endswith("academic_affairs_teaching_class_service")
    assert teaching_class.create_roster_version.__module__.endswith(
        "academic_affairs_teaching_class_service"
    )

    # create_roster_version 保留极薄兼容分流；选课投影函数直接就是当前正式 owner。
    assert compat.create_roster_version.__module__.endswith(
        "academic_affairs_teaching_class_compat_migration_service"
    )
    assert compat.project_selection_course_locked is projection.project_selection_course_locked
    assert compat.project_selection_batch_locked is projection.project_selection_batch_locked

    selection = services.academic_affairs_selection_service
    assert selection.__name__.endswith("academic_affairs_selection_final_service")
    assert selection.adjust_record.__module__.endswith("academic_affairs_selection_final_service")


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
