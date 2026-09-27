"""Standalone initial schema frozen from PR #275 W1.

Revision ID: ix0001
Revises:
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "ix0001"
down_revision = None
branch_labels = None
depends_on = None

_TABLES = ('t_archive_manifest', 't_archive_manifest_item', 't_attendance_exception', 't_audit_outbox', 't_class', 't_college', 't_emp_company', 't_excel_import_job', 't_file_asset', 't_file_binding', 't_file_job', 't_file_object', 't_file_retention_policy', 't_file_scan_record', 't_file_upload_session', 't_file_version', 't_internship_agreement', 't_internship_agreement_template', 't_internship_application', 't_internship_application_material_snapshot', 't_internship_archive', 't_internship_audit_trail', 't_internship_batch', 't_internship_batch_participant', 't_internship_batch_plan', 't_internship_batch_scope_rule', 't_internship_campaign_enterprise', 't_internship_change_request', 't_internship_checkin', 't_internship_communication_log', 't_internship_complaint', 't_internship_compliance_exemption', 't_internship_compliance_template', 't_internship_consent', 't_internship_emergency_plan', 't_internship_enterprise_access_grant', 't_internship_enterprise_application_decision', 't_internship_enterprise_contact', 't_internship_enterprise_eval', 't_internship_enterprise_inspection', 't_internship_enterprise_member', 't_internship_evidence_package', 't_internship_final_score', 't_internship_guidance', 't_internship_incident', 't_internship_insurance', 't_internship_intention', 't_internship_leave', 't_internship_makeup', 't_internship_match', 't_internship_placement_snapshot', 't_internship_plan_ack', 't_internship_plan_task_progress', 't_internship_position', 't_internship_process_report', 't_internship_record', 't_internship_recruitment_campaign', 't_internship_remuneration_record', 't_internship_safety_completion', 't_internship_safety_course', 't_internship_score_config', 't_internship_special_filing', 't_internship_student_eval', 't_internship_student_profile', 't_internship_student_profile_item', 't_internship_visit', 't_internship_visit_plan', 't_internship_volunteer_group', 't_major', 't_message_attachment', 't_message_audience', 't_message_campaign', 't_message_channel_delivery', 't_message_delivery_job', 't_message_event_outbox', 't_permission', 't_risk_record', 't_role', 't_role_permission', 't_student_account_link', 't_student_contact', 't_student_import_batch', 't_student_parent_link', 't_student_profile', 't_student_stage_event', 't_teacher_student_scope', 't_tenant', 't_tenant_brand_config', 't_tenant_storage_quota', 't_unified_message', 't_unified_todo', 't_user', 't_user_role', 't_weekly_report', 't_workflow_definition', 't_workflow_instance', 't_workflow_node_definition', 't_workflow_task', 't_wx_account_binding')
_SQL_SHA256 = "bbffde761bcf135b7465a5b38655447ab62937dbad97a56ff6a562c61b88356a"


def _sql_text() -> str:
    path = Path(__file__).resolve().parents[1] / "sql" / "0001_internship_standalone_baseline.mysql.sql"
    raw = path.read_text(encoding="utf-8")
    import hashlib
    actual = hashlib.sha256(raw.encode()).hexdigest()
    if actual != _SQL_SHA256:
        raise RuntimeError(f"Standalone baseline SQL digest mismatch: {actual}")
    return raw


def upgrade() -> None:
    bind = op.get_bind()
    for statement in _sql_text().split(";\n\n"):
        statement = statement.strip()
        if statement:
            bind.exec_driver_sql(statement + ";")


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
    try:
        for table_name in reversed(_TABLES):
            op.drop_table(table_name)
    finally:
        bind.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
