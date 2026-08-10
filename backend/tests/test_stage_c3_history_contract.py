"""Stage C3 immutable-history contract tests.

These are intentionally narrow and deterministic: they prove the shared graduation
evaluator never upgrades UNKNOWN to PASS, immutable historical tables have no mutable
business-row columns, ARCHIVED cannot use the old unfreeze command, and post-archive
corrections are restricted to GRADE/GRADUATION while producing a superseding manifest
payload instead of rewriting V1.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest


def test_shared_graduation_evaluator_keeps_unknown_fail_closed(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable
    from app.modules.academic_affairs.services import academic_affairs_student_fact_service as facts

    checked_at = datetime(2026, 8, 9, 3, 30, 0)
    fact = SimpleNamespace(
        id=901,
        version_no=4,
        valid_from=datetime(2026, 7, 1),
        student_status="NORMAL",
        college_id=11,
        major_id=22,
        class_id=33,
        grade="2024",
    )
    monkeypatch.setattr(facts, "resolve_student_academic_fact", lambda *args, **kwargs: fact)
    monkeypatch.setattr(
        grad,
        "_run_items",
        lambda _db, _student: [
            {"item": "CREDIT", "result": "PASS", "evidenceHash": "a" * 64},
            {"item": "ARCHIVE", "result": "UNKNOWN", "evidenceHash": "b" * 64},
        ],
    )

    result = immutable.evaluate_student(
        object(),
        SimpleNamespace(id=1001),
        evaluated_at=checked_at,
    )

    assert result["overall"] == "SYSTEM_ABNORMAL"
    assert result["inputSnapshot"]["academicFact"]["id"] == "901"
    assert result["inputSnapshot"]["academicFact"]["versionNo"] == 4
    assert result["inputSnapshot"]["evaluatedAt"] == checked_at.isoformat()
    assert len(result["inputHash"]) == 64


def test_stage_c3_formal_archive_unfreeze_is_permanently_fail_closed():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_archive_immutable_guard as guard
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service

    assert archive_service.unfreeze is guard.reject_archive_unfreeze
    with pytest.raises(AppException) as exc:
        archive_service.unfreeze({"currentRoleCode": "SCHOOL_ADMIN"}, 77, "普通解冻")
    assert exc.value.code == "TERM_ARCHIVED"
    assert exc.value.http_status == 409


def test_stage_c3_historical_tables_are_append_only_but_correction_case_is_workflow_row():
    from app.models import (
        ArchiveManifest,
        GraduationDecisionFact,
        GraduationEvaluationRun,
        PostArchiveCorrectionCase,
    )

    for model in (GraduationEvaluationRun, GraduationDecisionFact, ArchiveManifest):
        columns = set(model.__table__.columns.keys())
        assert "updated_at" not in columns
        assert "updated_by" not in columns
        assert "is_deleted" not in columns
        assert "version" not in columns

    correction_columns = set(PostArchiveCorrectionCase.__table__.columns.keys())
    assert {"updated_at", "updated_by", "is_deleted", "version"}.issubset(correction_columns)
    assert {
        "business_type",
        "evidence_manifest",
        "risk_level",
        "second_approved_by",
        "applied_at",
        "resulting_manifest_id",
    }.issubset(correction_columns)


def test_post_archive_correction_scope_and_manifest_supersedes_contract():
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest_service

    assert manifest_service._CORRECTION_TYPES == {"GRADE", "GRADUATION"}
    batch = SimpleNamespace(id=88, term_id=99, term_code="2025-2026-2")
    payload = manifest_service._manifest_payload(
        batch=batch,
        version_no=2,
        domain_counts={"GRADE": 120},
        domain_hashes={"GRADE": "c" * 64},
        max_ids={"GRADE": 456},
        supersedes_id=701,
        reason="归档后纠错 #1",
    )

    assert payload["versionNo"] == 2
    assert payload["supersedesId"] == "701"
    assert payload["archiveBatchId"] == "88"
    assert payload["domainCounts"] == {"GRADE": 120}
    assert len(manifest_service._hash(payload)) == 64
