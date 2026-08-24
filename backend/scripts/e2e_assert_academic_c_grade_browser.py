"""Post-browser MySQL truth seal for the Academic C grade lifecycle.

This script is read-only. It must run only after Playwright performed every grade business write
through the real UI. It verifies final state, official projection, append-only correction lineage,
todo convergence and high-risk audit evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaGradeRecord,
    AaGradeTask,
    AcademicGrade,
    AffairsAuditTrail,
    StudentProfile,
    Tenant,
    UnifiedTodo,
)
from app.models.academic_affairs_effective_grade import AaGradeChangeRequest, AaGradeCorrection

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "e2e" / "academic-c-grade-browser-fixture.json"


def main() -> int:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.tenant_code == fixture["tenant"], Tenant.is_deleted.is_(False)
        )).first()
        assert tenant, "sandbox tenant missing"
        tid = int(tenant.id)

        tasks = db.scalars(select(AaGradeTask).where(
            AaGradeTask.tenant_id == tid,
            AaGradeTask.teaching_task_id == int(fixture["teachingTaskId"]),
        )).all()
        assert len(tasks) == 1, f"expected exactly one browser-created grade task, got {len(tasks)}"
        task = tasks[0]
        assert task.status == "PUBLISHED", f"grade task final status must be PUBLISHED, got {task.status}"
        assert task.publish_at is not None, "published task missing publish_at"
        assert task.submitted_at is not None, "published task missing submitted_at"
        assert task.college_reviewed_at is not None, "published task missing college_reviewed_at"

        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tid,
            StudentProfile.student_no.in_(fixture["students"]),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.student_no.asc())).all()
        assert len(students) == 2, f"expected two fixture students, got {len(students)}"
        student_ids = [int(row.id) for row in students]

        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == tid,
            AaGradeRecord.task_id == int(task.id),
            AaGradeRecord.is_deleted.is_(False),
        ).order_by(AaGradeRecord.student_id.asc())).all()
        assert len(records) == 2, f"expected two grade records, got {len(records)}"
        by_student = {int(row.student_id): row for row in records}
        assert set(by_student) == set(student_ids), "grade records must match the authoritative LOCKED roster"

        first = by_student[student_ids[0]]
        second = by_student[student_ids[1]]
        assert int(first.usual_score) == 82, first.usual_score
        # Browser First intentionally completes a post-publish correction for the first student: final 96 -> 90.
        # The task is 30% usual + 70% final, so the authoritative total must move 92 -> 88.
        assert int(first.final_score) == 90, f"approved correction did not become current server truth: {first.final_score}"
        assert int(first.total_score) == 88, f"corrected grade record total must be 88, got {first.total_score}"
        assert int(first.prev_final_score) == 96, f"grade record must preserve previous final component 96, got {first.prev_final_score}"
        assert int(first.prev_total_score) == 92, f"grade record must preserve previous total 92, got {first.prev_total_score}"
        assert int(second.usual_score) == 55 and int(second.final_score) == 50
        assert all(row.acad_grade_id for row in records), "every published record must link to official t_acad_grade"

        official = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == tid,
            AcademicGrade.id.in_([int(row.acad_grade_id) for row in records]),
            AcademicGrade.is_deleted.is_(False),
        )).all()
        assert len(official) == 2, f"expected two current official grade projections, got {len(official)}"
        official_by_id = {int(row.id): row for row in official}
        first_current = official_by_id[int(first.acad_grade_id)]
        second_current = official_by_id[int(second.acad_grade_id)]
        assert int(first_current.score) == 88, f"current official grade must expose corrected total 88, got {first_current.score}"
        assert str(getattr(first_current, "record_status", "")).upper() == "ACTIVE"
        assert str(getattr(first_current, "source", "")).upper() == "CHANGE", getattr(first_current, "source", None)
        assert str(getattr(second_current, "record_status", "")).upper() == "ACTIVE"
        assert str(getattr(second_current, "source", "")).upper() == "PUBLISH", getattr(second_current, "source", None)
        assert all(str(getattr(row, "course_name", "")) == fixture["courseName"] for row in official)

        change_requests = db.scalars(select(AaGradeChangeRequest).where(
            AaGradeChangeRequest.tenant_id == tid,
            AaGradeChangeRequest.grade_task_id == int(task.id),
            AaGradeChangeRequest.grade_record_id == int(first.id),
            AaGradeChangeRequest.student_id == int(first.student_id),
            AaGradeChangeRequest.is_deleted.is_(False),
        ).order_by(AaGradeChangeRequest.id.asc())).all()
        assert len(change_requests) == 1, f"expected one browser grade change request, got {len(change_requests)}"
        change_request = change_requests[0]
        assert str(change_request.status or "").upper() == "APPROVED", change_request.status
        assert int(change_request.before_final_score) == 96, change_request.before_final_score
        assert int(change_request.proposed_final_score) == 90, change_request.proposed_final_score
        assert int(change_request.before_total_score) == 92, f"change request must snapshot original total 92, got {change_request.before_total_score}"
        assert int(change_request.proposed_total_score) == 88, f"change request must calculate corrected total 88, got {change_request.proposed_total_score}"
        assert int(change_request.current_grade_id or 0) > 0, "change request missing original official grade"
        assert int(change_request.workflow_instance_id or 0) > 0, "change request missing workflow instance"

        corrections = db.scalars(select(AaGradeCorrection).where(
            AaGradeCorrection.tenant_id == tid,
            AaGradeCorrection.source_type == "CHANGE_REQUEST",
            AaGradeCorrection.source_ref_id == int(change_request.id),
            AaGradeCorrection.is_deleted.is_(False),
        )).all()
        assert len(corrections) == 1, f"expected one append-only correction link, got {len(corrections)}"
        correction = corrections[0]
        assert str(correction.status or "").upper() == "ACTIVE", correction.status
        assert int(correction.original_grade_id) == int(change_request.current_grade_id)
        assert int(correction.corrected_grade_id) == int(first.acad_grade_id)
        assert int(correction.corrected_grade_id) != int(correction.original_grade_id)
        assert int(correction.before_score) == 92, f"correction lineage must seal original score 92, got {correction.before_score}"
        assert int(correction.after_score) == 88, f"correction lineage must seal corrected score 88, got {correction.after_score}"

        lineage = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == tid,
            AcademicGrade.id.in_([int(correction.original_grade_id), int(correction.corrected_grade_id)]),
            AcademicGrade.is_deleted.is_(False),
        )).all()
        assert len(lineage) == 2, f"correction lineage incomplete: {[row.id for row in lineage]}"
        lineage_by_id = {int(row.id): row for row in lineage}
        original = lineage_by_id[int(correction.original_grade_id)]
        corrected = lineage_by_id[int(correction.corrected_grade_id)]
        assert int(original.score) == 92, f"superseded PUBLISH version must retain original total 92, got {original.score}"
        assert int(corrected.score) == 88, f"ACTIVE CHANGE version must carry corrected total 88, got {corrected.score}"
        assert str(getattr(original, "record_status", "")).upper() == "SUPERSEDED", getattr(original, "record_status", None)
        assert str(getattr(original, "source", "")).upper() == "PUBLISH", getattr(original, "source", None)
        assert str(getattr(corrected, "record_status", "")).upper() == "ACTIVE", getattr(corrected, "record_status", None)
        assert str(getattr(corrected, "source", "")).upper() == "CHANGE", getattr(corrected, "source", None)
        assert str(getattr(corrected, "source_biz_type", "")).upper() == "GRADE_CHANGE_REQUEST"
        assert int(getattr(corrected, "source_biz_id", 0) or 0) == int(change_request.id)
        assert int(getattr(corrected, "grade_record_id", 0) or 0) == int(first.id)
        assert int(getattr(original, "grade_record_id", 0) or 0) == int(first.id)

        pending_todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == tid,
            UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(task.id),
            UnifiedTodo.todo_type == "AA_GRADE_ENTRY",
            UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.status == "PENDING",
        )).all()
        assert not pending_todos, "published grade task must not leave teacher grade-entry todo pending"

        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_id == int(task.id),
            AffairsAuditTrail.biz_type == "AA_GRADE_TASK",
        ).order_by(AffairsAuditTrail.id.asc())).all()
        assert audits, "grade task has no AffairsAuditTrail rows"
        high_risk = [row for row in audits if any(token in str(row.action or "").upper() for token in (
            "SUBMIT", "RETURN", "COLLEGE", "REVIEW", "PUBLISH"
        ))]
        assert len(high_risk) >= 4, f"insufficient high-risk grade audit rows: {[row.action for row in audits]}"
        for row in high_risk:
            assert str(row.operator or "").strip(), f"audit {row.action} missing operator"
            assert str(row.role_name or "").strip(), f"audit {row.action} missing role"
            assert row.occurred_at is not None, f"audit {row.action} missing timestamp"
            # Production acceptance rule: high-risk approval/return/publish evidence must contain before/after facts.
            assert str(getattr(row, "before_val", "") or "").strip(), f"audit {row.action} missing before_val"
            assert str(getattr(row, "after_val", "") or "").strip(), f"audit {row.action} missing after_val"

        correction_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_id == int(first.id),
            AffairsAuditTrail.biz_type == "AA_GRADE_RECORD",
            AffairsAuditTrail.action == "CHANGE_APPROVE",
        ).order_by(AffairsAuditTrail.id.asc())).all()
        assert correction_audits, "approved correction missing AA_GRADE_RECORD CHANGE_APPROVE audit"
        assert all(str(row.operator or "").strip() for row in correction_audits)
        assert all(str(row.role_name or "").strip() for row in correction_audits)
        assert all(row.occurred_at is not None for row in correction_audits)

        evidence = {
            "tenantId": tid,
            "gradeTaskId": int(task.id),
            "status": task.status,
            "records": [
                {
                    "studentId": int(row.student_id),
                    "usual": row.usual_score,
                    "final": row.final_score,
                    "total": row.total_score,
                    "previousFinal": row.prev_final_score,
                    "previousTotal": row.prev_total_score,
                    "passStatus": row.pass_status,
                    "acadGradeId": int(row.acad_grade_id),
                    "officialScore": official_by_id[int(row.acad_grade_id)].score,
                    "officialSource": str(getattr(official_by_id[int(row.acad_grade_id)], "source", "")),
                    "officialRecordStatus": str(getattr(official_by_id[int(row.acad_grade_id)], "record_status", "")),
                }
                for row in records
            ],
            "correction": {
                "changeRequestId": int(change_request.id),
                "status": change_request.status,
                "beforeFinal": change_request.before_final_score,
                "afterFinal": change_request.proposed_final_score,
                "beforeTotal": change_request.before_total_score,
                "afterTotal": change_request.proposed_total_score,
                "originalGradeId": int(correction.original_grade_id),
                "correctedGradeId": int(correction.corrected_grade_id),
                "originalScore": original.score,
                "correctedScore": corrected.score,
                "originalStatus": str(getattr(original, "record_status", "")),
                "correctedStatus": str(getattr(corrected, "record_status", "")),
                "correctedSource": str(getattr(corrected, "source", "")),
            },
            "auditActions": [row.action for row in audits],
            "highRiskAuditCount": len(high_risk),
            "correctionAuditActions": [row.action for row in correction_audits],
            "pendingTeacherTodos": len(pending_todos),
        }
        out = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_c_grade_browser_db_evidence.json"
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
