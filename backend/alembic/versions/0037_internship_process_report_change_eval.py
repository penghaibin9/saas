"""岗位实习 · 日报/月报/总结 + 变更申请 + 学生对企业岗位评价

Revision ID: 0037_internship_process_report_change_eval
Revises: 0036_internship_agreement_rendered_body
Create Date: 2026-07-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0037_internship_process_report_change_eval"
down_revision = "0036_internship_agreement_rendered_body"
branch_labels = None
depends_on = None


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def _cols(bind, t):
    return {c["name"] for c in inspect(bind).get_columns(t)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_process_report"):
        op.create_table(
            "t_internship_process_report",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("report_type", sa.String(20), nullable=False),
            sa.Column("period_key", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING_REVIEW"),
            sa.Column("review_action", sa.String(50), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("reviewed_by_name", sa.String(100), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "internship_id", "report_type", "period_key",
                                name="uk_intern_process_report"),
        )
    if not _has(bind, "t_internship_change_request"):
        op.create_table(
            "t_internship_change_request",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("change_type", sa.String(30), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("target_enterprise_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("target_position_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("target_enterprise_name", sa.String(200), nullable=True),
            sa.Column("target_position_name", sa.String(100), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("reviewed_by_name", sa.String(50), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        )
    if _has(bind, "t_internship_student_eval"):
        cols = _cols(bind, "t_internship_student_eval")
        if "enterprise_rating" not in cols:
            op.add_column("t_internship_student_eval",
                          sa.Column("enterprise_rating", sa.Integer(), nullable=True))
        if "position_rating" not in cols:
            op.add_column("t_internship_student_eval",
                          sa.Column("position_rating", sa.Integer(), nullable=True))
        if "enterprise_feedback" not in cols:
            op.add_column("t_internship_student_eval",
                          sa.Column("enterprise_feedback", sa.String(1000), nullable=True))
        if "position_feedback" not in cols:
            op.add_column("t_internship_student_eval",
                          sa.Column("position_feedback", sa.String(1000), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_student_eval"):
        for c in ("position_feedback", "enterprise_feedback", "position_rating", "enterprise_rating"):
            if c in _cols(bind, "t_internship_student_eval"):
                op.drop_column("t_internship_student_eval", c)
    if _has(bind, "t_internship_change_request"):
        op.drop_table("t_internship_change_request")
    if _has(bind, "t_internship_process_report"):
        op.drop_table("t_internship_process_report")
