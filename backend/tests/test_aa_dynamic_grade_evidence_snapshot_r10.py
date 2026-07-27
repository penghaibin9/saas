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


def test_dynamic_grade_source_defaults_optional_component_to_zero():
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


def test_r10_routes_are_registered_on_public_academic_router():
    from app.modules.academic_affairs.routers import academic_affairs

    signatures = {
        (route.path, tuple(sorted(route.methods or set())))
        for route in academic_affairs.router.routes
    }
    for signature in (
        ("/academic-affairs/grade-tasks/{task_id}/scheme", ("GET",)),
        ("/academic-affairs/grade-tasks/{task_id}/scheme", ("PUT",)),
        ("/academic-affairs/grade-tasks/{task_id}/component-scores", ("POST",)),
        ("/academic-affairs/grade-tasks/{task_id}/students/{student_id}/component-scores", ("GET",)),
        ("/academic-affairs/stats/snapshots", ("POST",)),
        ("/academic-affairs/stats/snapshots", ("GET",)),
        ("/academic-affairs/stats/snapshots/{snapshot_id}", ("GET",)),
    ):
        assert signature in signatures


def test_r10_compatibility_layers_are_loaded_from_public_services():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as graduation

    assert services.academic_affairs_dynamic_grade_service.__name__.endswith(
        "academic_affairs_dynamic_grade_service"
    )
    assert services.academic_affairs_stats_snapshot_service.__name__.endswith(
        "academic_affairs_stats_snapshot_service"
    )
    assert graduation._run_items.__module__.endswith(
        "academic_affairs_graduation_evidence_facade"
    )


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
