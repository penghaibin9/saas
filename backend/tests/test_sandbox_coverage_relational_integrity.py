from __future__ import annotations

from sqlalchemy import create_engine

from app.models import Base
from scripts import _seed_sandbox_coverage as coverage


def test_discipline_package11_relationship_tables_are_explicit_seed_only():
    expected = {
        "t_affairs_discipline_decision_version",
        "t_affairs_discipline_appeal",
        "t_affairs_discipline_remove_apply",
        "t_affairs_discipline_subflow_lock",
        "t_cs_discipline",
    }
    assert expected <= set(coverage.RELATIONAL_INTEGRITY_TABLES)


def test_generic_coverage_never_enumerates_protected_relationship_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        table_names = {
            "t_affairs_discipline_case",
            "t_affairs_discipline_decision_version",
            "t_affairs_discipline_appeal",
            "t_affairs_discipline_remove_apply",
            "t_affairs_discipline_subflow_lock",
            "t_cs_discipline",
        }
        for name in table_names:
            Base.metadata.tables[name].create(bind=engine, checkfirst=True)

        class Db:
            @staticmethod
            def get_bind():
                return engine

        enumerated = {table.name for table in coverage._domain_tables(Db())}
        assert "t_affairs_discipline_case" in enumerated
        assert not (set(coverage.RELATIONAL_INTEGRITY_TABLES) & enumerated)
    finally:
        engine.dispose()
