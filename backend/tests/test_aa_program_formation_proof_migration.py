"""Apply the actual additive migration against the disposable MySQL test schema."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect


def _migration():
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20261005_aa_formation_proof.py'
    spec = importlib.util.spec_from_file_location('formation_proof_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_migration_matches_model_without_rewriting_tasks(db_mode):
    from app.db.session import get_engine
    from app.models import AaProgramCourseFormationProof, AaTeachingTask
    migration = _migration()
    engine = get_engine()
    assert engine.url.database == 'student_lifecycle_test'
    assert engine.dialect.name == 'mysql'
    table = AaProgramCourseFormationProof.__table__
    source_index = next(index for index in AaTeachingTask.__table__.indexes if index.name == 'ix_aa_task_formation_source')
    with engine.begin() as connection:
        before_tasks = connection.exec_driver_sql('SELECT COUNT(*) FROM t_aa_teaching_task').scalar_one()
        table.drop(connection)
        source_index.drop(connection)
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        inspector = inspect(connection)
        columns = inspector.get_columns(table.name)
        assert {column['name'] for column in columns} == set(table.c.keys())
        for column in columns:
            assert column['nullable'] == table.c[column['name']].nullable
        assert {item['name'] for item in inspector.get_unique_constraints(table.name)} == {'uk_aa_formation_proof_source', 'uk_aa_formation_proof_idem'}
        assert {item['name'] for item in inspector.get_check_constraints(table.name)} == {'ck_aa_formation_proof_mode', 'ck_aa_formation_proof_requirements'}
        assert any(index['name'] == source_index.name and index['column_names'] == ['tenant_id', 'source_program_course_id', 'id'] for index in inspector.get_indexes('t_aa_teaching_task'))
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM t_aa_teaching_task').scalar_one() == before_tasks
    with pytest.raises(RuntimeError, match='must be preserved'):
        migration.downgrade()
