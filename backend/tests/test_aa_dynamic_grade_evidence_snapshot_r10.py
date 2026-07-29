"""R10 动态成绩、毕业逐项证据和统计快照回归。"""
from pathlib import Path

import pytest
from app.core.exceptions import AppException


def test_dynamic_grade_scheme_accepts_one_to_twelve_and_requires_total_100():
    from app.modules.academic_affairs.services.academic_affairs_dynamic_grade_service import normalize_components

    one = normalize_components([
        {"code": "FINAL", "name": "期末成绩", "weight": 100, "required": True},
    ])
    assert one == [{
        "code": "FINAL", "name": "期末成绩", "weight": 100.0,
        "required": True, "order": 1,
    }]

    twelve = normalize_components([
        {
            "code": f"ITEM_{index}",
            "name": f"项目{index}",
            "weight": 12 if index == 11 else 8,
            "required": index < 11,
        }
        for index in range(12)
    ])
    assert len(twelve) == 12
    assert sum(item["weight"] for item in twelve) == 100

    with pytest.raises(AppException):
        normalize_components([])
    with pytest.raises(AppException):
        normalize_components([{"code": "A1", "name": "项目", "weight": 90}])
    with pytest.raises(AppException):
        normalize_components([
            {"code": "A1", "name": "项目1", "weight": 50},
            {"code": "A1", "name": "项目2", "weight": 50},
        ])


def test_dynamic_grade_source_defaults_optional_component_to_zero_and_revives_soft_deleted_rows():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_dynamic_grade_service.py"
    ).read_text(encoding="utf-8")

    assert "动态成绩项须为1-12项" in source
    assert 'value = _score(submitted[component["code"]], component["name"]) if supplied else 0.0' in source
    assert '"defaultedToZero": not supplied' in source
    assert "resolve_versioned_roster" in source
    assert "AaGradeRecord" in source
    assert 'scheme.status = "LOCKED"' in source
    assert "academic_affairs_grade_service as grade_service" in source
    assert "academic_affairs_grade_identity_facade" not in source
    assert "row.is_deleted = False" in source
    assert "AaGradeComponentScore.component_code == component[\"code\"]" in source
    assert ").with_for_update()).first()" in source


def test_graduation_evidence_hash_is_stable_and_contains_drill_identity():
    from app.modules.academic_affairs.services.academic_affairs_graduation_evidence_facade import (
        normalize_evidence_item,
    )

    item = {
        "item": "CREDIT", "result": "PASS", "owner": "AA_STAFF",
        "evidence": "已得 120/120 学分", "refId": "8",
    }
    first = normalize_evidence_item(item, student_id=99, checked_at="2026-07-27T10:00:00")
    second = normalize_evidence_item(item, student_id=99, checked_at="2026-07-27T11:00:00")

    assert first["evidenceCode"] == "GRAD-CREDIT"
    assert first["sourceType"] == "ACADEMIC_GRADE"
    assert first["sourceIds"] == ["8"]
    assert first["facts"]["studentId"] == "99"
    assert first["drillRoute"] == "/admin/academic-affairs/graduation-audit"
    assert first["evidenceHash"] == second["evidenceHash"]
    assert first["checkedAt"] != second["checkedAt"]


def test_stats_snapshot_hash_is_canonical_and_changes_with_payload():
    from app.modules.academic_affairs.services.academic_affairs_stats_snapshot_service import payload_hash

    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})
    assert payload_hash({"a": 1}) != payload_hash({"a": 2})


def test_r10_models_and_migration_are_additive():
    from app.models.academic_affairs_r10 import (
        AaGradeComponentScore, AaGradeSchemeSnapshot, AaStatsSnapshot,
    )

    assert "uk_aa_grade_scheme_task" in {
        value.name for value in AaGradeSchemeSnapshot.__table__.constraints if value.name
    }
    assert "uk_aa_grade_component_student" in {
        value.name for value in AaGradeComponentScore.__table__.constraints if value.name
    }
    assert {"payload_json", "payload_hash", "scope_json", "filters_json"} <= set(
        AaStatsSnapshot.__mapper__.attrs.keys()
    )

    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "alembic/versions/0130_aa_dynamic_grade_stats_snapshot.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "0130_aa_dynamic_grade_stats_snapshot"' in migration
    assert 'down_revision = "0129_aa_roster_consumer_snapshot"' in migration
    for table in (
        "t_aa_grade_scheme_snapshot",
        "t_aa_grade_component_score",
        "t_aa_stats_snapshot",
    ):
        assert table in migration


def test_r10_routes_are_registered_through_domain_bundle():
    from app.modules.academic_affairs.routers import dynamic_grade_router, stats_snapshot_router

    root = Path(__file__).resolve().parents[1]
    registration = (root / "app/api/v1/route_registration.py").read_text(encoding="utf-8")
    bundle = (
        root / "app/modules/academic_affairs/routers/academic_affairs_bundle.py"
    ).read_text(encoding="utf-8")

    assert 'api_router.include_router(academic_affairs.router, dependencies=deps["aa"])' in registration
    assert "dynamic_grade_router" in bundle
    assert "stats_snapshot_router" in bundle
    assert "router.include_router(module.router)" in bundle

    dynamic_routes = {
        (route.path, tuple(sorted(route.methods or set())))
        for route in dynamic_grade_router.router.routes
    }
    assert ("/academic-affairs/grade-tasks/{task_id}/scheme", ("PUT",)) in dynamic_routes
    assert ("/academic-affairs/grade-tasks/{task_id}/component-scores", ("POST",)) in dynamic_routes

    stats_routes = {
        (route.path, tuple(sorted(route.methods or set())))
        for route in stats_snapshot_router.router.routes
    }
    assert ("/academic-affairs/stats/snapshots", ("POST",)) in stats_routes
    assert ("/academic-affairs/stats/snapshots", ("GET",)) in stats_routes
    assert ("/academic-affairs/stats/snapshots/{snapshot_id}", ("GET",)) in stats_routes


def test_r10_public_services_are_explicit_and_do_not_assert_facade_module_locations():
    from app.modules.academic_affairs.services import academic_affairs_dynamic_grade_service as dynamic_grade
    from app.modules.academic_affairs.services import academic_affairs_stats_snapshot_service as stats_snapshot

    assert callable(dynamic_grade.enter_component_scores)
    assert callable(dynamic_grade.configure_scheme)
    assert callable(stats_snapshot.create_snapshot)
    assert callable(stats_snapshot.get_snapshot)


def test_stats_snapshot_service_is_immutable_and_hash_checked():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_stats_snapshot_service.py"
    ).read_text(encoding="utf-8")

    assert 'status="FROZEN"' in source
    assert '"immutable": True' in source
    assert "payload_hash(parsed) != row.payload_hash" in source
    assert "STATS_SNAPSHOT_CREATE" in source
    assert "STATS_SNAPSHOT_READ" in source
    assert "update_snapshot" not in source
    assert "delete_snapshot" not in source
