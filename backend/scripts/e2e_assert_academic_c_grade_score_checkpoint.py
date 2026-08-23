"""Direct-MySQL truth seal for the browser score-entry checkpoint.

This assertion belongs to the score-only browser gate. Playwright must create the GradeTask and write
both score rows through the real Staff PC first, then reload and persist its checkpoint JSON. This script
never calls a business API and never mutates the database.
"""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AaGradeRecord, AaGradeTask, AcademicGrade, AffairsAuditTrail, Tenant

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "e2e" / "academic-c-grade-browser-fixture.json"
CHECKPOINT_PATH = ROOT / "e2e" / "artifacts" / "academic-c-grade-score-checkpoint" / "browser-score-checkpoint.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_c_grade_score_checkpoint_db_evidence.json"


def _number(value):
    return None if value is None else int(value)


def main() -> int:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    assert checkpoint.get("browserReloadVerified") is True, "browser reload persistence checkpoint missing"
    assert checkpoint.get("submitButtonVisible") is True, "canonical submit action was not projected after score entry"
    assert str(checkpoint.get("tenant")) == str(fixture["tenant"])
    assert int(checkpoint["teachingTaskId"]) == int(fixture["teachingTaskId"])

    expected_scores = {
        int(row["studentId"]): (int(row["usualScore"]), int(row["finalScore"]))
        for row in checkpoint.get("expectedScores") or []
    }
    assert len(expected_scores) == 2, f"checkpoint must describe exactly two students: {expected_scores}"

    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.tenant_code == fixture["tenant"],
            Tenant.is_deleted.is_(False),
        )).first()
        assert tenant, "sandbox tenant missing"
        tid = int(tenant.id)
        assert tid == int(checkpoint["tenantId"]), "checkpoint tenant id differs from MySQL tenant"

        task_id = int(checkpoint["gradeTaskId"])
        task = db.scalars(select(AaGradeTask).where(
            AaGradeTask.id == task_id,
            AaGradeTask.tenant_id == tid,
            AaGradeTask.teaching_task_id == int(fixture["teachingTaskId"]),
            AaGradeTask.is_deleted.is_(False),
        )).first()
        assert task, "browser-created GradeTask missing from MySQL"
        assert str(task.status or "").upper() == "INPUTTING", f"score-only checkpoint must stop before submit, got {task.status}"
        assert task.submitted_at is None, "score-only checkpoint unexpectedly crossed submit boundary"
        assert task.publish_at is None, "score-only checkpoint unexpectedly crossed publish boundary"

        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == tid,
            AaGradeRecord.task_id == task_id,
            AaGradeRecord.is_deleted.is_(False),
        ).order_by(AaGradeRecord.student_id.asc())).all()
        assert len(records) == 2, f"expected exactly two persisted grade records, got {len(records)}"
        by_student = {int(row.student_id): row for row in records}
        assert set(by_student) == set(expected_scores), (
            f"persisted students {sorted(by_student)} != browser checkpoint students {sorted(expected_scores)}"
        )
        for student_id, (usual_score, final_score) in expected_scores.items():
            row = by_student[student_id]
            assert _number(row.usual_score) == usual_score, (student_id, row.usual_score, usual_score)
            assert _number(row.final_score) == final_score, (student_id, row.final_score, final_score)
            assert str(row.exception_flag or "NORMAL").upper() == "NORMAL"
            assert row.acad_grade_id is None, "score entry must not create official AcademicGrade before publish"

        official = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == tid,
            AcademicGrade.grade_task_id == task_id,
            AcademicGrade.is_deleted.is_(False),
        )).all()
        assert not official, "pre-submit score checkpoint must not expose official grades"

        enter_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_type == "AA_GRADE_TASK",
            AffairsAuditTrail.biz_id == task_id,
            AffairsAuditTrail.action == "ENTER",
        ).order_by(AffairsAuditTrail.id.asc())).all()
        assert len(enter_audits) == 2, f"expected two ENTER audit rows, got {len(enter_audits)}"
        for row in enter_audits:
            assert str(row.operator or "").strip(), "ENTER audit missing operator"
            assert row.occurred_at is not None, "ENTER audit missing timestamp"
            assert "student=" in str(row.detail or ""), f"ENTER audit missing student evidence: {row.detail}"

        evidence = {
            "tenantId": tid,
            "gradeTaskId": task_id,
            "teachingTaskId": int(task.teaching_task_id),
            "status": task.status,
            "browserReloadVerified": True,
            "submitButtonVisible": True,
            "records": [
                {
                    "studentId": int(row.student_id),
                    "usualScore": _number(row.usual_score),
                    "finalScore": _number(row.final_score),
                    "totalScore": _number(row.total_score),
                    "passStatus": row.pass_status,
                    "acadGradeId": row.acad_grade_id,
                }
                for row in records
            ],
            "enterAuditCount": len(enter_audits),
            "officialGradeCount": len(official),
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
