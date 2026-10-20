"""Yiyang C08/G15 report rules, immutable versions and review facts.

Revision ID: ix0008
Revises: ix0007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0008"
down_revision = "ix0007"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def _audit_time():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "t_internship_report_rule_config",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("weekly_min_words", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("plan_task_min_words", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("monthly_min_words", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("summary_min_words", sa.Integer(), nullable=False, server_default=sa.text("300")),
        sa.Column("max_images", sa.Integer(), nullable=False, server_default=sa.text("9")),
        sa.Column("max_videos", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("remark", sa.String(500), nullable=True),
        *_common(),
        sa.UniqueConstraint("tenant_id", "batch_id", name="uk_ix_report_rule_batch"),
    )
    op.create_index(
        "ix_ix_report_rule_batch_active",
        "t_internship_report_rule_config",
        ["tenant_id", "batch_id", "is_deleted"],
    )
    for col in ("tenant_id", "batch_id"):
        op.create_index(
            f"ix_t_internship_report_rule_config_{col}",
            "t_internship_report_rule_config",
            [col],
        )

    op.create_table(
        "t_internship_report_version",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("report_kind", sa.String(20), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("report_type", sa.String(20), nullable=True),
        sa.Column("period_key", sa.String(32), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("attachment_file_ids_json", sa.JSON(), nullable=True),
        sa.Column("attachment_meta_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        *_audit_time(),
        sa.UniqueConstraint(
            "tenant_id", "report_kind", "report_id", "version_no",
            name="uk_ix_report_snapshot_version",
        ),
    )
    op.create_index(
        "ix_ix_report_snapshot_lookup",
        "t_internship_report_version",
        ["tenant_id", "report_kind", "report_id", "version_no"],
    )
    op.create_index(
        "ix_ix_report_snapshot_internship",
        "t_internship_report_version",
        ["tenant_id", "internship_id", "student_id", "submitted_at"],
    )
    for col in ("tenant_id", "internship_id", "student_id"):
        op.create_index(
            f"ix_t_internship_report_version_{col}",
            "t_internship_report_version",
            [col],
        )

    op.create_table(
        "t_internship_report_review",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("report_kind", sa.String(20), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("report_version_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("rating_level", sa.Integer(), nullable=True),
        sa.Column("summary_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", sa.String(64), nullable=True),
        sa.Column("reviewer_name", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        *_audit_time(),
        sa.UniqueConstraint(
            "tenant_id", "report_version_id", name="uk_ix_report_version_review"),
    )
    op.create_index(
        "ix_ix_report_review_lookup",
        "t_internship_report_review",
        ["tenant_id", "report_kind", "report_id", "reviewed_at"],
    )
    for col in ("tenant_id", "report_version_id"):
        op.create_index(
            f"ix_t_internship_report_review_{col}",
            "t_internship_report_review",
            [col],
        )


def downgrade() -> None:
    op.drop_table("t_internship_report_review")
    op.drop_table("t_internship_report_version")
    op.drop_table("t_internship_report_rule_config")
