"""Internship P2 compliance evidence and labour-rights schema."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0131_internship_p2_compliance"
down_revision = "0130_gd_risk_reopen_lifecycle"
branch_labels = None
depends_on = None

PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _has_col(bind, table, name):
    return _has(bind, table) and any(c["name"] == name for c in inspect(bind).get_columns(table))


def _common():
    return [
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()),
        sa.Column("created_by", sa.BigInteger()), sa.Column("updated_by", sa.BigInteger()),
    ]


def _create(bind, name, *columns, constraints=()):
    if not _has(bind, name):
        op.create_table(name, sa.Column("id", PK, primary_key=True, autoincrement=True),
                        sa.Column("tenant_id", sa.BigInteger(), nullable=False), *columns, *_common(),
                        *constraints, mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")


def _add_missing(bind, table, columns):
    for name, col in columns:
        if not _has_col(bind, table, name):
            op.add_column(table, col)


def upgrade():
    bind = op.get_bind()
    S, I, B, D, F, T, J = sa.String, sa.Integer, sa.Boolean, sa.DateTime, sa.Float, sa.Text, sa.JSON
    _create(bind, "t_internship_compliance_template",
        sa.Column("template_code", S(64), nullable=False), sa.Column("template_name", S(200), nullable=False),
        sa.Column("template_version", I(), nullable=False, server_default="1"), sa.Column("status", S(20), nullable=False, server_default="DRAFT"),
        sa.Column("config", J()), sa.Column("effective_at", D()), sa.Column("approved_by_name", S(100)),
        sa.Column("approved_at", D()), sa.Column("change_reason", S(500)), sa.Column("remark", S(500)),
        constraints=(sa.UniqueConstraint("tenant_id", "template_code", "template_version", name="uk_ix_compliance_tpl_ver"),))
    _create(bind, "t_internship_enterprise_inspection",
        sa.Column("company_id", sa.BigInteger(), nullable=False), sa.Column("batch_id", sa.BigInteger()),
        sa.Column("inspection_type", S(30), nullable=False, server_default="DOCUMENT"), sa.Column("inspection_required", B(), nullable=False, server_default=sa.text("1")),
        sa.Column("inspection_date", D()), sa.Column("inspectors", S(200)), sa.Column("workplace_address", S(300)),
        sa.Column("safety_condition", S(500)), sa.Column("accommodation_condition", S(500)), sa.Column("mentor_condition", S(500)),
        sa.Column("remuneration_condition", S(500)), sa.Column("conclusion", S(1000)), sa.Column("risk_items", T()),
        sa.Column("rectification_items", T()), sa.Column("file_ids", J()), sa.Column("valid_until", D()),
        sa.Column("status", S(30), nullable=False, server_default="DRAFT"), sa.Column("review_comment", S(500)),
        sa.Column("reviewed_by_name", S(100)), sa.Column("reviewed_at", D()), sa.Column("rule_version", S(64)))
    _create(bind, "t_internship_consent",
        sa.Column("internship_id", sa.BigInteger(), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("consent_type", S(20), nullable=False), sa.Column("applicable", B(), nullable=False, server_default=sa.text("1")),
        sa.Column("participant_name", S(100)), sa.Column("participant_relation", S(50)), sa.Column("identity_masked", S(64)), sa.Column("contact_masked", S(64)),
        sa.Column("content_version", S(64)), sa.Column("content_snapshot", T()), sa.Column("delivery_channel", S(40)), sa.Column("message_id", sa.BigInteger()),
        sa.Column("delivered_at", D()), sa.Column("viewed_at", D()), sa.Column("confirmed_at", D()), sa.Column("confirmation_method", S(40)),
        sa.Column("device_digest", S(128)), sa.Column("file_id", S(64)), sa.Column("status", S(30), nullable=False, server_default="PENDING"),
        sa.Column("revoked_at", D()), sa.Column("revoke_reason", S(500)), sa.Column("rule_version", S(64)))
    _create(bind, "t_internship_safety_course",
        sa.Column("batch_id", sa.BigInteger()), sa.Column("title", S(200), nullable=False), sa.Column("course_version", S(40), nullable=False, server_default="v1"),
        sa.Column("required_minutes", I(), nullable=False, server_default="60"), sa.Column("passing_score", I(), nullable=False, server_default="80"),
        sa.Column("max_attempts", I(), nullable=False, server_default="3"), sa.Column("require_commitment", B(), nullable=False, server_default=sa.text("1")),
        sa.Column("content_snapshot", T()), sa.Column("material_file_ids", J()), sa.Column("status", S(20), nullable=False, server_default="ACTIVE"),
        sa.Column("effective_at", D()), sa.Column("retired_at", D()), sa.Column("rule_version", S(64)))
    _create(bind, "t_internship_safety_completion",
        sa.Column("internship_id", sa.BigInteger(), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False), sa.Column("course_version", S(40), nullable=False), sa.Column("started_at", D()),
        sa.Column("completed_at", D()), sa.Column("studied_minutes", I(), nullable=False, server_default="0"), sa.Column("attempt_count", I(), nullable=False, server_default="0"),
        sa.Column("score", I()), sa.Column("passed", B(), nullable=False, server_default=sa.text("0")), sa.Column("commitment_confirmed", B(), nullable=False, server_default=sa.text("0")),
        sa.Column("commitment_at", D()), sa.Column("evidence_file_id", S(64)), sa.Column("review_mode", S(30), nullable=False, server_default="TEACHER_REVIEW"),
        sa.Column("reviewed_by_name", S(100)), sa.Column("reviewed_at", D()), sa.Column("status", S(30), nullable=False, server_default="PENDING"), sa.Column("rule_version", S(64)),
        constraints=(sa.UniqueConstraint("tenant_id", "internship_id", "course_id", name="uk_ix_safety_completion"),))
    _create(bind, "t_internship_special_filing",
        sa.Column("internship_id", sa.BigInteger(), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("filing_type", S(40), nullable=False), sa.Column("applicable", B(), nullable=False, server_default=sa.text("1")), sa.Column("trigger_reason", S(500)),
        sa.Column("destination_region", S(200)), sa.Column("work_address", S(300)), sa.Column("risk_description", T()), sa.Column("student_application", T()),
        sa.Column("guardian_consent_required", B(), nullable=False, server_default=sa.text("0")), sa.Column("college_review_by", S(100)), sa.Column("college_review_at", D()),
        sa.Column("college_comment", S(500)), sa.Column("school_review_by", S(100)), sa.Column("school_review_at", D()), sa.Column("school_comment", S(500)),
        sa.Column("regulator_filing_no", S(100)), sa.Column("status", S(30), nullable=False, server_default="DRAFT"), sa.Column("approved_by_name", S(100)),
        sa.Column("approved_at", D()), sa.Column("valid_until", D()), sa.Column("file_ids", J()), sa.Column("rule_version", S(64)), sa.Column("superseded_by_id", sa.BigInteger()))
    _create(bind, "t_internship_remuneration_record",
        sa.Column("internship_id", sa.BigInteger(), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("position_id", sa.BigInteger()),
        sa.Column("agreed_amount", F()), sa.Column("agreed_cycle", S(30)), sa.Column("actual_paid_amount", F()), sa.Column("paid_at", D()),
        sa.Column("proof_file_id", S(64)), sa.Column("status", S(30), nullable=False, server_default="AGREED"), sa.Column("discrepancy", S(500)),
        sa.Column("student_confirmed_at", D()), sa.Column("rule_version", S(64)))
    _create(bind, "t_internship_emergency_plan",
        sa.Column("company_id", sa.BigInteger()), sa.Column("batch_id", sa.BigInteger()), sa.Column("plan_name", S(200), nullable=False),
        sa.Column("responsible_person", S(100)), sa.Column("emergency_contact", S(100)), sa.Column("backup_contact", S(100)), sa.Column("hospital_or_support", S(300)),
        sa.Column("response_steps", T()), sa.Column("valid_from", D()), sa.Column("valid_until", D()), sa.Column("file_ids", J()),
        sa.Column("status", S(30), nullable=False, server_default="DRAFT"), sa.Column("reviewed_by_name", S(100)), sa.Column("reviewed_at", D()), sa.Column("rule_version", S(64)))
    _create(bind, "t_internship_incident",
        sa.Column("incident_no", S(64), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("internship_id", sa.BigInteger()),
        sa.Column("company_id", sa.BigInteger()), sa.Column("student_id", sa.BigInteger()), sa.Column("risk_id", sa.BigInteger()), sa.Column("incident_type", S(50), nullable=False, server_default="OTHER"),
        sa.Column("severity", S(20), nullable=False, server_default="MEDIUM"), sa.Column("occurred_at", D()), sa.Column("location", S(300)), sa.Column("summary", T()),
        sa.Column("injury_flag", B(), nullable=False, server_default=sa.text("0")), sa.Column("affected_persons", S(500)), sa.Column("reported_by_name", S(100)),
        sa.Column("reported_at", D()), sa.Column("emergency_action", T()), sa.Column("guardian_notified_at", D()), sa.Column("school_notified_at", D()),
        sa.Column("enterprise_notified_at", D()), sa.Column("external_reported_at", D()), sa.Column("status", S(30), nullable=False, server_default="REPORTED"),
        sa.Column("investigation_conclusion", T()), sa.Column("responsibility_conclusion", T()), sa.Column("rectification_plan", T()),
        sa.Column("rectification_deadline", D()), sa.Column("closed_at", D()), sa.Column("closed_by_name", S(100)), sa.Column("file_ids", J()),
        sa.Column("idempotency_key", S(80)), sa.Column("rule_version", S(64)), constraints=(sa.UniqueConstraint("tenant_id", "incident_no", name="uk_ix_incident_no"),))
    _create(bind, "t_internship_compliance_exemption",
        sa.Column("internship_id", sa.BigInteger(), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("check_code", S(64), nullable=False),
        sa.Column("reason", S(1000), nullable=False), sa.Column("evidence_file_ids", J()), sa.Column("valid_from", D()), sa.Column("valid_until", D()),
        sa.Column("status", S(20), nullable=False, server_default="ACTIVE"), sa.Column("approved_by_name", S(100)), sa.Column("approved_at", D()), sa.Column("rule_version", S(64)))
    _create(bind, "t_internship_evidence_package",
        sa.Column("package_type", S(20), nullable=False), sa.Column("batch_id", sa.BigInteger()), sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("package_version", I(), nullable=False, server_default="1"), sa.Column("package_file_id", S(64)), sa.Column("manifest_json", J()), sa.Column("included_items", J()),
        sa.Column("missing_items", J()), sa.Column("rule_version", S(64)), sa.Column("metric_version", S(64)), sa.Column("generated_by_name", S(100)),
        sa.Column("generated_at", D()), sa.Column("status", S(20), nullable=False, server_default="READY"), sa.Column("row_count", I(), nullable=False, server_default="0"), sa.Column("file_count", I(), nullable=False, server_default="0"))
    _add_missing(bind, "t_internship_position", [
        ("daily_hours", sa.Column("daily_hours", sa.Float())), ("weekly_hours", sa.Column("weekly_hours", sa.Float())),
        ("shift_type", sa.Column("shift_type", sa.String(30))), ("night_shift", sa.Column("night_shift", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
        ("overtime_allowed", sa.Column("overtime_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0"))), ("rest_days", sa.Column("rest_days", sa.String(50))),
        ("remuneration_type", sa.Column("remuneration_type", sa.String(30))), ("remuneration_amount", sa.Column("remuneration_amount", sa.Float())),
        ("remuneration_cycle", sa.Column("remuneration_cycle", sa.String(30))), ("accommodation_provided", sa.Column("accommodation_provided", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
        ("meal_provided", sa.Column("meal_provided", sa.Boolean(), nullable=False, server_default=sa.text("0"))), ("hazardous_flag", sa.Column("hazardous_flag", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
        ("special_equipment", sa.Column("special_equipment", sa.String(200))), ("work_content", sa.Column("work_content", sa.Text())), ("prohibited_reason", sa.Column("prohibited_reason", sa.String(500)))])
    _add_missing(bind, "t_internship_batch", [("compliance_template_id", sa.Column("compliance_template_id", sa.BigInteger())), ("compliance_template_version", sa.Column("compliance_template_version", sa.Integer()))])
    _add_missing(bind, "t_emp_company", [("access_valid_until", sa.Column("access_valid_until", sa.DateTime()))])


def downgrade():
    bind = op.get_bind()
    for table in ("t_internship_evidence_package", "t_internship_compliance_exemption", "t_internship_incident",
                  "t_internship_emergency_plan", "t_internship_remuneration_record", "t_internship_special_filing",
                  "t_internship_safety_completion", "t_internship_safety_course", "t_internship_consent",
                  "t_internship_enterprise_inspection", "t_internship_compliance_template"):
        if _has(bind, table):
            op.drop_table(table)
