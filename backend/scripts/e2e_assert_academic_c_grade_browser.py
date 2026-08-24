"""Post-browser MySQL truth seal for the Academic C grade lifecycle.

This script is read-only. It must run only after Playwright performed every grade business write
through the real UI. It verifies final state, official projection, todo convergence and high-risk audit evidence.
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
        assert int(first.final_score) == 96, f"returned/resubmitted score did not persist: {first.final_score}"
        assert int(second.usual_score) == 55 and int(second.final_score) == 50
        assert all(row.acad_grade_id for row in records), "every published record must link to official t_acad_grade"

        official = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == tid,
            AcademicGrade.id.in_([int(row.acad_grade_id) for row in records]),
            AcademicGrade.is_deleted.is_(False),
        )).all()
        assert len(official) == 2, f"expected two official grade projections, got {len(official)}"
        assert all(str(getattr(row, "source", "")).upper() == "PUBLISH" for row in official), [getattr(row, "source", None) for row in official]
        assert all(str(getattr(row, "course_name", "")) == fixture["courseName"] for row in official)

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
                    "passStatus": row.pass_status,
                    "acadGradeId": int(row.acad_grade_id),
                }
                for row in records
            ],
            "auditActions": [row.action for row in audits],
            "highRiskAuditCount": len(high_risk),
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
