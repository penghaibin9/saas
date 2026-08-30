from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_enterprise_evaluation_is_bound_to_exact_current_formal_placement():
    model = _read("backend/app/models/internship.py")
    collaboration = _read(
        "backend/app/modules/internship/services/internship_enterprise_collaboration_service.py"
    )
    school = _read(
        "backend/app/modules/internship/services/internship_enterprise_eval_service.py"
    )
    score = _read("backend/app/modules/internship/services/internship_score_service.py")
    for field in ("placement_snapshot_id", "enterprise_id", "position_id"):
        assert field in model
    assert "InternshipRecord.current_placement_snapshot_id.is_not(None)" in collaboration
    assert collaboration.count(
        "InternshipEnterpriseEval.placement_snapshot_id == InternshipRecord.current_placement_snapshot_id"
    ) >= 2
    assert "def _current_placement" in collaboration
    assert "def _matches_current_placement" in school
    assert "InternshipEnterpriseEval.placement_snapshot_id == record.current_placement_snapshot_id" in score


def test_score_components_are_server_facts_and_all_three_evaluations_gate_completion():
    fact = _read(
        "backend/app/modules/internship/services/internship_score_fact_guard.py"
    )
    assert "InternshipAuditTrail.is_deleted" not in fact
    assert '"checkinScore", "weeklyScore", "monthlyScore", "enterpriseScore", "schoolScore"' in fact
    assert "正式成绩不得直接提交分项分数" in fact
    assert 'raw = body.get("manualAdjustments") or {}' in fact
    assert 'InternshipStudentEval.school_review_status == "APPROVED"' in fact
    assert "InternshipStudentEval.advisor_opinion.is_not(None)" in fact
    assert '"school": _ratio_score(school_expected, school_actual) if student_eval else None' in fact
    for key in ("enterpriseEvaluation", "studentSelfEvaluation", "advisorEvaluation"):
        assert f'"{key}"' in fact


def test_review_and_publish_are_distinct_versioned_audit_fail_closed_commands():
    fact = _read(
        "backend/app/modules/internship/services/internship_score_fact_guard.py"
    )
    router = _read("backend/app/modules/internship/routers/internship.py")
    assert "def _review(user, score_id, expected_version=None)" in fact
    assert 'expected_status="PENDING_REVIEW"' in fact
    assert 'values={"status": "PENDING_PUBLISH"' in fact
    assert 'expected_status="PENDING_PUBLISH"' in fact
    assert '"status": "PUBLISHED"' in fact
    assert 'score.status == "PENDING_PUBLISH"' in fact
    assert "必须先执行有原因留痕的退回重算" in fact
    assert fact.count("assert_high_risk_write_available(db)") >= 2
    assert '_score._trail(db, score.id, "REVIEW"' in fact
    assert '_score._trail(db, score.id, "PUBLISH"' in fact
    assert '@router.post("/scores/{score_id}/review"' in router
    assert '@router.post("/scores/{score_id}/publish"' in router


def test_appeal_freezes_score_identity_and_version_then_withdraws_atomically():
    appeal = _read(
        "backend/app/modules/internship/services/internship_score_appeal_service.py"
    )
    assert '"scoreId": str(score.id)' in appeal
    assert '"scoreVersion": int(score.version or 0)' in appeal
    assert "if int(score.version or 0) != frozen_score_version" in appeal
    assert 'expected_status="PUBLISHED"' in appeal
    assert 'values={"status": "WITHDRAWN"}' in appeal
    assert "assert_high_risk_write_available(db)" in appeal
    assert "CsWorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES)" in appeal


def test_migration_backfills_placement_truth_and_final_score_stays_unique():
    migration = _read(
        "backend/alembic/versions/20260830_internship_evaluation_placement_truth.py"
    )
    model = _read("backend/app/models/internship.py")
    assert 'revision = "20260830_ix_eval_place"' in migration
    assert 'down_revision = "20260829_pr236_main_merge"' in migration
    assert "requires MySQL" in migration
    assert "JOIN t_internship_placement_snapshot" in migration
    assert "p.id=r.current_placement_snapshot_id" in migration
    assert 'UniqueConstraint("tenant_id", "internship_id", name="uk_internship_final_score_record")' in model
