"""13B-SM-10 考务管理：建 9 表（批次/课程/考场/座位/监考/巡考/异常/缓考/域审计）。

全新业务表，无存量兼容负担；downgrade 逆序 drop。幂等：inspect 判表存在再建/删。
审计表 t_aa_exam_audit_trail 为 append-only（无 is_deleted/version/updated_*）。

Revision ID: 0073_13b_exam
Revises: 0072_13b_p7_selection
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0073_13b_exam"
down_revision = "0072_13b_p7_selection"
branch_labels = None
depends_on = None

_COMMON = [
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by", sa.BigInteger()),
    sa.Column("updated_by", sa.BigInteger()),
    sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
]


def _pk_tenant():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
    ]


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_exam_batch"):
        op.create_table(
            "t_aa_exam_batch", *_pk_tenant(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("exam_type", sa.String(20), nullable=False, server_default="FINAL"),
            sa.Column("college_scope_json", sa.String(2000)),
            sa.Column("exam_week_start", sa.Integer()),
            sa.Column("exam_week_end", sa.Integer()),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            *_COMMON)
        op.create_index("ix_aa_exam_batch_status", "t_aa_exam_batch", ["tenant_id", "status"])

    if not _has(bind, "t_aa_exam_course"):
        op.create_table(
            "t_aa_exam_course", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("teaching_task_id", sa.BigInteger()),
            sa.Column("course_id", sa.BigInteger()),
            sa.Column("course_name", sa.String(200)),
            sa.Column("class_id", sa.BigInteger()),
            sa.Column("class_name", sa.String(100)),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("expected_students", sa.Integer()),
            sa.Column("exam_date", sa.String(20)),
            sa.Column("start_time", sa.String(10)),
            sa.Column("end_time", sa.String(10)),
            sa.Column("duration_minutes", sa.Integer()),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_CONFIRM"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "batch_id", "teaching_task_id", name="uk_aa_exam_course"))
        op.create_index("ix_aa_exam_course_batch", "t_aa_exam_course", ["tenant_id", "batch_id"])
        op.create_index("ix_aa_exam_course_college", "t_aa_exam_course", ["tenant_id", "college_id"])

    if not _has(bind, "t_aa_exam_room"):
        op.create_table(
            "t_aa_exam_room", *_pk_tenant(),
            sa.Column("exam_course_id", sa.BigInteger(), nullable=False),
            sa.Column("room_seq", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("classroom_id", sa.BigInteger()),
            sa.Column("classroom_text", sa.String(100)),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("planned_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("seat_mode", sa.String(20), nullable=False, server_default="SEQUENTIAL"),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "exam_course_id", "room_seq", name="uk_aa_exam_room"))

    if not _has(bind, "t_aa_exam_room_student"):
        op.create_table(
            "t_aa_exam_room_student", *_pk_tenant(),
            sa.Column("exam_room_id", sa.BigInteger(), nullable=False),
            sa.Column("exam_course_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("seat_no", sa.Integer()),
            sa.Column("admission_no", sa.String(50)),
            sa.Column("attendance_status", sa.String(30), nullable=False, server_default="NOT_STARTED"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "exam_room_id", "seat_no", name="uk_aa_exam_seat"),
            sa.UniqueConstraint("tenant_id", "exam_course_id", "student_id", name="uk_aa_exam_course_student"))
        op.create_index("ix_aa_exam_rs_room", "t_aa_exam_room_student", ["tenant_id", "exam_room_id"])
        op.create_index("ix_aa_exam_rs_student", "t_aa_exam_room_student", ["tenant_id", "student_id"])

    if not _has(bind, "t_aa_exam_invigilator"):
        op.create_table(
            "t_aa_exam_invigilator", *_pk_tenant(),
            sa.Column("exam_room_id", sa.BigInteger(), nullable=False),
            sa.Column("teacher_key", sa.String(100), nullable=False),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("role", sa.String(20), nullable=False, server_default="ASSISTANT"),
            sa.Column("confirm_status", sa.String(20), nullable=False, server_default="ASSIGNED"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "exam_room_id", "teacher_key", name="uk_aa_exam_invig"))
        op.create_index("ix_aa_exam_invig_teacher", "t_aa_exam_invigilator", ["tenant_id", "teacher_key"])

    if not _has(bind, "t_aa_exam_patrol"):
        op.create_table(
            "t_aa_exam_patrol", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("teacher_key", sa.String(100), nullable=False),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("patrol_date", sa.String(20)),
            sa.Column("start_time", sa.String(10)),
            sa.Column("end_time", sa.String(10)),
            sa.Column("area_scope_json", sa.String(1000)),
            sa.Column("status", sa.String(20), nullable=False, server_default="ASSIGNED"),
            *_COMMON)
        op.create_index("ix_aa_exam_patrol_teacher", "t_aa_exam_patrol", ["tenant_id", "teacher_key"])

    if not _has(bind, "t_aa_exam_incident"):
        op.create_table(
            "t_aa_exam_incident", *_pk_tenant(),
            sa.Column("exam_room_id", sa.BigInteger()),
            sa.Column("exam_course_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("incident_type", sa.String(30), nullable=False),
            sa.Column("description", sa.String(1000)),
            sa.Column("evidence_file_ids", sa.String(1000)),
            sa.Column("recorded_by", sa.String(100)),
            sa.Column("recorded_at", sa.DateTime()),
            sa.Column("risk_alert_sent", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("discipline_case_ref", sa.String(100)),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "exam_course_id", "student_id", "incident_type",
                                name="uk_aa_exam_incident"))

    if not _has(bind, "t_aa_deferred_exam"):
        op.create_table(
            "t_aa_deferred_exam", *_pk_tenant(),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("exam_course_id", sa.BigInteger(), nullable=False),
            sa.Column("course_name", sa.String(200)),
            sa.Column("reason_type", sa.String(50)),
            sa.Column("reason", sa.String(500)),
            sa.Column("material_file_ids", sa.String(1000)),
            sa.Column("apply_at", sa.DateTime()),
            sa.Column("current_node", sa.String(50)),
            sa.Column("return_reason", sa.String(500)),
            sa.Column("next_batch_ref", sa.String(100)),
            sa.Column("workflow_instance_id", sa.BigInteger()),
            sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED"),
            *_COMMON)
        op.create_index("ix_aa_defer_student", "t_aa_deferred_exam", ["tenant_id", "student_id", "exam_course_id", "status"])

    if not _has(bind, "t_aa_exam_audit_trail"):
        op.create_table(
            "t_aa_exam_audit_trail", *_pk_tenant(),
            sa.Column("biz_type", sa.String(50), nullable=False),
            sa.Column("biz_id", sa.BigInteger()),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("operator", sa.String(100)),
            sa.Column("role_name", sa.String(100)),
            sa.Column("detail", sa.String(1000)),
            sa.Column("before_val", sa.String(1000)),
            sa.Column("after_val", sa.String(1000)),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()))
        op.create_index("ix_aa_exam_audit_biz", "t_aa_exam_audit_trail", ["tenant_id", "biz_type", "biz_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_exam_audit_trail", "t_aa_deferred_exam", "t_aa_exam_incident", "t_aa_exam_patrol",
              "t_aa_exam_invigilator", "t_aa_exam_room_student", "t_aa_exam_room",
              "t_aa_exam_course", "t_aa_exam_batch"):
        if _has(bind, t):
            op.drop_table(t)
