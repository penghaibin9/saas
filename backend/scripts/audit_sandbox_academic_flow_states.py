"""盘点 AA-001～024 关键表的租户行数与状态分布。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402


FLOW_TABLES = {
    "AA-001": ["t_aa_term", "t_aa_calendar_event", "t_aa_time_slot", "t_aa_class_time_band"],
    "AA-002": ["t_aa_registration_batch", "t_aa_registration", "t_aa_registration_exception", "t_aa_registration_deferral", "t_aa_student_correction"],
    "AA-003": ["t_aa_status_change", "t_aa_student_academic_fact", "t_aa_program_transition_assessment"],
    "AA-004": ["t_aa_major_split_batch", "t_aa_major_split_option", "t_aa_major_split_volunteer"],
    "AA-005": ["t_aa_program", "t_aa_program_course", "t_aa_program_binding", "t_aa_program_graduation_requirement", "t_aa_program_practice_segment"],
    "AA-006": ["t_aa_course", "t_aa_course_material", "t_aa_teaching_task_batch"],
    "AA-007": ["t_aa_teaching_task", "t_aa_teaching_class", "t_aa_teaching_class_roster_version", "t_aa_teaching_class_member", "t_aa_roster_consumer_snapshot"],
    "AA-008": ["t_aa_schedule_batch", "t_aa_schedule_item", "t_aa_schedule_publish", "t_aa_schedule_rule", "t_aa_teacher_availability"],
    "AA-009": ["t_aa_schedule_change", "t_workflow_instance", "t_workflow_task", "t_unified_todo", "t_unified_message"],
    "AA-010": ["t_aa_attendance_session", "t_acad_warning", "t_acad_intervention"],
    "AA-011": ["t_aa_selection_batch", "t_aa_selection_round", "t_aa_selection_course", "t_aa_selection_record"],
    "AA-012": ["t_aa_exam_batch", "t_aa_exam_course", "t_aa_exam_room", "t_aa_exam_room_student", "t_aa_exam_invigilator", "t_aa_exam_incident"],
    "AA-013": ["t_aa_deferred_exam", "t_aa_makeup_batch", "t_acad_makeup", "t_aa_retake_apply", "t_acad_retake", "t_aa_exemption"],
    "AA-014": ["t_aa_grade_task", "t_aa_grade_record", "t_aa_grade_scheme_snapshot", "t_aa_grade_component_score", "t_acad_grade"],
    "AA-015": ["t_aa_grade_change_request", "t_aa_grade_correction", "t_aa_grade_recheck", "t_aa_grade_recognition"],
    "AA-016": ["t_acad_warning", "t_acad_intervention", "t_aa_attendance_session"],
    "AA-017": ["t_aa_textbook", "t_aa_textbook_selection", "t_aa_textbook_review_batch", "t_aa_textbook_review_batch_item", "t_aa_textbook_order_batch", "t_aa_textbook_order_item", "t_aa_textbook_distribution_batch", "t_aa_textbook_distribution_record", "t_aa_textbook_fee_ledger"],
    "AA-018": ["t_aa_classroom", "t_aa_classroom_booking", "t_aa_lab_resource", "t_aa_lab_booking", "t_aa_equipment", "t_aa_resource_repair"],
    "AA-019": ["t_aa_evaluation_batch", "t_aa_evaluation_task", "t_aa_evaluation_record", "t_aa_evaluation_result", "t_aa_evaluation_appeal"],
    "AA-020": ["t_aa_quality_record", "t_aa_quality_rectification"],
    "AA-021": ["t_aa_graduation_audit_batch", "t_aa_graduation_audit_result", "t_aa_graduation_evaluation_run", "t_aa_graduation_decision_fact", "t_aa_graduation_certificate"],
    "AA-022": ["t_aa_archive_batch", "t_aa_archive_item", "t_aa_archive_manifest", "t_aa_post_archive_correction_case"],
    "AA-023": ["t_aa_stats_snapshot", "t_aa_workload_declaration"],
    "AA-024": ["t_import_job", "t_import_row_error", "t_export_job", "t_file_object", "t_file_binding", "t_security_audit_log"],
}


def main() -> int:
    tenant_id = 1000000000000000007
    report = {}
    with get_sessionmaker()() as db:
        schema = db.execute(text("SELECT DATABASE()" )).scalar()
        columns = {
            (row[0], row[1])
            for row in db.execute(text("""
                SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA=:schema
            """), {"schema": schema}).all()
        }
        for flow, tables in FLOW_TABLES.items():
            items = []
            for table in tables:
                if (table, "tenant_id") not in columns:
                    items.append({"table": table, "missingTable": True})
                    continue
                count = int(db.execute(
                    text(f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id=:tenant_id"),
                    {"tenant_id": tenant_id},
                ).scalar() or 0)
                statuses = {}
                if (table, "status") in columns:
                    statuses = {
                        str(status): int(total)
                        for status, total in db.execute(text(
                            f"SELECT COALESCE(status,'<NULL>'),COUNT(*) FROM `{table}` "
                            "WHERE tenant_id=:tenant_id GROUP BY status ORDER BY status"
                        ), {"tenant_id": tenant_id}).all()
                    }
                items.append({"table": table, "count": count, "statuses": statuses})
            report[flow] = items
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
