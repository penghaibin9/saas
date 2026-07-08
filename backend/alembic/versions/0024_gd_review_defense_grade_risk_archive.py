"""查重记录 + 教师评阅 + 答辩评分 + 成绩评定 + 问题预警 + 毕设归档

Revision ID: 0024_gd_review_defense_grade_risk_archive
Revises: 0023_gd_guidance_midterm

新表：t_gd_plagiarism / t_gd_review / t_gd_defense_score / t_gd_grade / t_gd_risk_case / t_gd_archive_record。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0024_gd_review_defense_grade_risk_archive"
down_revision = "0023_gd_guidance_midterm"
branch_labels = None
depends_on = None

_COMMON = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")


def _common_cols():
    return [
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "t_gd_plagiarism" not in tables:
        op.create_table(
            "t_gd_plagiarism",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_final_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("submit_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="CHECKING"),
            sa.Column("rate", sa.String(20), nullable=True),
            sa.Column("report_url", sa.String(500), nullable=True),
            sa.Column("threshold", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("over_threshold", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("dispute_reason", sa.String(500), nullable=True),
            sa.Column("dispute_status", sa.String(30), nullable=True),
            sa.Column("dispute_comment", sa.String(500), nullable=True),
            *_common_cols(),
            **_COMMON,
        )

    if "t_gd_review" not in tables:
        op.create_table(
            "t_gd_review",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_final_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("reviewer_name", sa.String(100), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="ASSIGNED"),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("opinion", sa.String(2000), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("assigned_by", sa.String(100), nullable=True),
            sa.Column("assigned_at", sa.DateTime(), nullable=True),
            *_common_cols(),
            **_COMMON,
        )

    if "t_gd_defense_score" not in tables:
        op.create_table(
            "t_gd_defense_score",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("defense_group_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("judge_name", sa.String(100), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("comment", sa.String(1000), nullable=True),
            sa.Column("absent", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("absent_reason", sa.String(500), nullable=True),
            sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            *_common_cols(),
            **_COMMON,
        )

    if "t_gd_grade" not in tables:
        op.create_table(
            "t_gd_grade",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("advisor_score", sa.Integer(), nullable=True),
            sa.Column("reviewer_score", sa.Integer(), nullable=True),
            sa.Column("defense_score", sa.Integer(), nullable=True),
            sa.Column("total_score", sa.Integer(), nullable=True),
            sa.Column("grade_level", sa.String(20), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("remark", sa.String(500), nullable=True),
            sa.Column("calculated_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by", sa.String(100), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("published_by", sa.String(100), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("withdraw_reason", sa.String(500), nullable=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_grade_student"),
            **_COMMON,
        )

    if "t_gd_risk_case" not in tables:
        op.create_table(
            "t_gd_risk_case",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("risk_code", sa.String(20), nullable=False, index=True),
            sa.Column("risk_name", sa.String(100), nullable=False),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("level", sa.String(20), nullable=False, server_default="MEDIUM"),
            sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
            sa.Column("assignee", sa.String(100), nullable=True),
            sa.Column("handle_note", sa.String(1000), nullable=True),
            sa.Column("close_reason", sa.String(500), nullable=True),
            sa.Column("detected_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "risk_code", "gd_student_id", name="uk_gd_risk_case"),
            **_COMMON,
        )

    if "t_gd_archive_record" not in tables:
        op.create_table(
            "t_gd_archive_record",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("checklist_json", sa.JSON(), nullable=True),
            sa.Column("missing_items", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="NOT_GENERATED"),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("verified_by", sa.String(100), nullable=True),
            sa.Column("filed_at", sa.DateTime(), nullable=True),
            sa.Column("archive_batch_no", sa.String(100), nullable=True),
            sa.Column("reject_reason", sa.String(500), nullable=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_archive_student"),
            **_COMMON,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for t in ("t_gd_archive_record", "t_gd_risk_case", "t_gd_grade", "t_gd_defense_score",
             "t_gd_review", "t_gd_plagiarism"):
        if t in insp.get_table_names():
            for idx in insp.get_indexes(t):
                op.drop_index(idx["name"], table_name=t)
            op.drop_table(t)
