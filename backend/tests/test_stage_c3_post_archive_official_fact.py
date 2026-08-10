"""Stage C3 golden correction facts: old facts stay, corrected facts append."""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.context import set_tenant
from app.db.session import get_sessionmaker

TID = 1000000000000000001


def _activate():
    set_tenant({"tenantId": str(TID), "tenantCode": "stage-c3"})


@pytest.mark.usefixtures("db_mode")
def test_post_archive_grade_correction_supersedes_old_grade_and_appends_official_fact():
    from app.models import AaGradeCorrection, AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services.academic_affairs_post_archive_fact_service import (
        apply_official_correction_fact,
    )

    _activate()
    db = get_sessionmaker()()
    try:
        academic = AcademicStudent(
            tenant_id=TID,
            student_no="C3G001",
            name="归档成绩纠错甲",
            obtained_credits=0,
        )
        db.add(academic)
        db.flush()
        original = AcademicGrade(
            tenant_id=TID,
            acad_student_id=academic.id,
            course_name="高等数学",
            term="2025-2026-2",
            nature="REQUIRED",
            credit_value=4,
            score=58,
            pass_status="FAILED",
            exam_type="FINAL",
            record_status="ACTIVE",
            source="PUBLISH",
            course_code="MATH101",
            course_version=1,
            attempt_no=1,
            effective_policy_code="DEFAULT",
            effective_policy_version=1,
            effective_attempt_strategy="LATEST_ATTEMPT",
            pass_line_snapshot=60,
        )
        db.add(original)
        db.commit()
        db.refresh(original)

        case = SimpleNamespace(
            id=8801,
            target_ref=str(original.id),
            correction_json=json.dumps({"score": 65}, ensure_ascii=False),
            reason="原卷复核确认登分错误，按原始卷面纠正",
            business_type="GRADE",
        )
        batch = SimpleNamespace(id=9901, term_id=None, term_code="2025-2026-2")
        official = apply_official_correction_fact(db, batch, case, actor=2002)
        db.commit()

        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == TID,
            AcademicGrade.acad_student_id == academic.id,
        ).order_by(AcademicGrade.id).all()
        assert len(rows) == 2
        old, new = rows
        assert old.id == original.id and old.record_status == "SUPERSEDED" and old.score == 58
        assert new.record_status == "ACTIVE" and new.score == 65 and new.pass_status == "PASSED"
        assert new.course_code == old.course_code and new.attempt_no == old.attempt_no
        assert new.effective_policy_code == old.effective_policy_code
        assert new.effective_policy_version == old.effective_policy_version
        assert official["factType"] == "ACADEMIC_GRADE"
        assert int(official["factId"]) == int(new.id)
        assert official["beforeHash"] != official["afterHash"]

        correction = db.query(AaGradeCorrection).filter(
            AaGradeCorrection.tenant_id == TID,
            AaGradeCorrection.source_type == "POST_ARCHIVE",
            AaGradeCorrection.source_ref_id == case.id,
        ).one()
        assert correction.original_grade_id == old.id
        assert correction.corrected_grade_id == new.id
        db.refresh(academic)
        assert float(academic.obtained_credits or 0) == 4.0
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_post_archive_graduation_correction_appends_run2_and_decision2_without_overwriting_v1(monkeypatch):
    from app.models import (
        AaGraduationAuditBatch,
        AaGraduationAuditResult,
        AaTerm,
        GraduationDecisionFact,
        GraduationEvaluationRun,
        StudentProfile,
    )
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable
    from app.modules.academic_affairs.services.academic_affairs_post_archive_fact_service import (
        apply_official_correction_fact,
    )

    _activate()
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2025-2026",
            term_no=2,
            term_name="2025-2026 第二学期",
            start_date=datetime(2026, 2, 23),
            end_date=datetime(2026, 7, 10, 23, 59, 59),
            status="ARCHIVED",
        )
        db.add(term)
        db.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no="C3D001",
            real_name="归档毕业纠错甲",
            current_stage="GRADUATED",
            student_status="GRADUATED",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        grad_batch = AaGraduationAuditBatch(
            tenant_id=TID,
            batch_name="2026届毕业资格",
            status="ARCHIVED",
            generate_at=datetime(2026, 6, 20, 9, 0, 0),
        )
        db.add(grad_batch)
        db.flush()
        result = AaGraduationAuditResult(
            tenant_id=TID,
            batch_id=grad_batch.id,
            student_id=student.id,
            item_results_json="[]",
            overall="SYSTEM_PASSED",
            conclusion="GRADUATED",
            rerun_count=1,
            status="ARCHIVED",
        )
        db.add(result)
        db.flush()
        run1 = GraduationEvaluationRun(
            tenant_id=TID,
            batch_id=grad_batch.id,
            result_id=result.id,
            student_id=student.id,
            run_no=1,
            program_id=None,
            input_snapshot_json="{}",
            input_hash="1" * 64,
            item_results_json="[]",
            overall="SYSTEM_PASSED",
            evaluator_version="STAGE_C3_V1",
        )
        db.add(run1)
        db.flush()
        decision1 = GraduationDecisionFact(
            tenant_id=TID,
            batch_id=grad_batch.id,
            result_id=result.id,
            student_id=student.id,
            decision_no=1,
            evaluation_run_id=run1.id,
            conclusion="GRADUATED",
            decision_at=datetime(2026, 6, 21, 9, 0, 0),
            decision_by=1001,
        )
        db.add(decision1)
        db.commit()

        monkeypatch.setattr(
            immutable,
            "evaluate_student",
            lambda _db, _student, evaluated_at=None: {
                "programId": None,
                "inputSnapshot": {
                    "evaluatorVersion": "STAGE_C3_V1",
                    "evaluatedAt": (evaluated_at or datetime.utcnow()).isoformat(),
                    "studentId": str(student.id),
                    "evidenceHashes": ["e" * 64],
                },
                "inputHash": "2" * 64,
                "items": [{"item": "CREDIT", "result": "PASS", "evidenceHash": "e" * 64}],
                "overall": "SYSTEM_PASSED",
            },
        )
        case = SimpleNamespace(
            id=8802,
            target_ref=str(decision1.id),
            correction_json=json.dumps({"conclusion": "GRADUATED"}, ensure_ascii=False),
            reason="归档后成绩纠错完成，重新执行毕业资格正式评估",
            business_type="GRADUATION",
        )
        archive_batch = SimpleNamespace(
            id=9902,
            term_id=term.id,
            term_code="2025-2026-2",
        )
        official = apply_official_correction_fact(db, archive_batch, case, actor=2002)
        db.commit()

        runs = db.query(GraduationEvaluationRun).filter(
            GraduationEvaluationRun.tenant_id == TID,
            GraduationEvaluationRun.result_id == result.id,
        ).order_by(GraduationEvaluationRun.run_no).all()
        decisions = db.query(GraduationDecisionFact).filter(
            GraduationDecisionFact.tenant_id == TID,
            GraduationDecisionFact.result_id == result.id,
        ).order_by(GraduationDecisionFact.decision_no).all()
        assert [row.run_no for row in runs] == [1, 2]
        assert [row.input_hash for row in runs] == ["1" * 64, "2" * 64]
        assert [row.decision_no for row in decisions] == [1, 2]
        assert decisions[1].supersedes_id == decisions[0].id
        assert decisions[1].correction_case_id == case.id
        assert decisions[1].evaluation_run_id == runs[1].id
        assert official["factType"] == "GRADUATION_DECISION"
        assert int(official["factId"]) == int(decisions[1].id)
        assert decisions[0].conclusion == "GRADUATED"
        db.refresh(result)
        assert result.status == "ARCHIVED"
        assert result.rerun_count == 2
    finally:
        db.close()
        set_tenant(None)
