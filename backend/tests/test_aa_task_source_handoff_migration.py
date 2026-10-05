"""实际增量迁移与模型一致，任务及已有审计不被回写。"""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect


def test_actual_task_handoff_migration_is_additive(db_mode):
    from app.db.session import get_engine
    from app.models import AaTeachingTaskSourceHandoff
    file = Path(__file__).resolve().parents[1] / "alembic/versions/20261005_aa_task_source_handoff.py"
    spec = importlib.util.spec_from_file_location("task_handoff_migration", file)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = get_engine()
    assert engine.dialect.name == "mysql" and engine.url.database == "student_lifecycle_test"
    table = AaTeachingTaskSourceHandoff.__table__
    with engine.begin() as connection:
        before = connection.exec_driver_sql("SELECT COUNT(*) FROM t_aa_teaching_task").scalar_one()
        table.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        inspector = inspect(connection)
        actual = inspector.get_columns(table.name)
        assert {column["name"] for column in actual} == set(table.c.keys())
        assert all(column["nullable"] == table.c[column["name"]].nullable for column in actual)
        assert {row["name"] for row in inspector.get_unique_constraints(table.name)} == {
            "uk_aa_task_handoff_successor", "uk_aa_task_handoff_idem"}
        assert {row["name"] for row in inspector.get_check_constraints(table.name)} == {"ck_aa_task_handoff_distinct"}
        assert any(row["name"] == "ix_aa_task_handoff_execution" and row["column_names"] ==
            ["tenant_id", "term_id", "execution_task_id"] for row in inspector.get_indexes(table.name))
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM t_aa_teaching_task").scalar_one() == before
