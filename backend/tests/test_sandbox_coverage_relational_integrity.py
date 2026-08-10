from __future__ import annotations

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


def test_required_parent_ids_force_explicit_relationship_seed():
    decision = Base.metadata.tables["t_affairs_discipline_decision_version"]
    funding = Base.metadata.tables["t_affairs_funding_application"]
    discipline_case = Base.metadata.tables["t_affairs_discipline_case"]

    assert "case_id" in coverage.required_relation_columns(decision)
    assert "batch_id" in coverage.required_relation_columns(funding)
    assert coverage.requires_explicit_relationship_seed(decision) is True
    assert coverage.requires_explicit_relationship_seed(funding) is True

    # 根主案只依赖真实 student_id；generic coverage 可以安全补其声明状态。
    assert coverage.required_relation_columns(discipline_case) == ()
    assert coverage.requires_explicit_relationship_seed(discipline_case) is False
