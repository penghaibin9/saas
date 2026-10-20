"""Yiyang C08/TM14 teacher check-in evidence and makeup.

Revision ID: ix0019
Revises: ix0018
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0019"
down_revision = "ix0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("result", sa.String(30), nullable=False, server_default="RECORDED"),
        sa.Column("distance_m", sa.Numeric(12, 2), nullable=True),
        sa.Column("coordinate_system", sa.String(20), nullable=True),
        sa.Column("country_region", sa.String(100), nullable=True),
        sa.Column("location_provider", sa.String(50), nullable=True),
        sa.Column("photo_file_id", sa.String(64), nullable=True),
        sa.Column("watermarked_file_id", sa.String(64), nullable=True),
        sa.Column("photo_sha256", sa.String(64), nullable=True),
        sa.Column("watermarked_sha256", sa.String(64), nullable=True),
        sa.Column("watermark_text", sa.String(500), nullable=True),
    ):
        op.add_column("t_internship_teacher_checkin", column)

    op.create_table(
        "t_internship_teacher_makeup",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_name_snapshot", sa.String(100), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("evidence_file_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("active_pending_key", sa.String(1), nullable=True, server_default="1"),
        sa.Column("reviewed_by_name", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "teacher_user_id", "local_date", "active_pending_key",
            name="uk_ix_teacher_makeup_pending_day",
        ),
    )
    op.create_index(
        "ix_ix_teacher_makeup_batch_teacher",
        "t_internship_teacher_makeup",
        ["tenant_id", "batch_id", "teacher_user_id", "local_date"],
    )
    for column in ("batch_id", "teacher_user_id"):
        op.create_index(
            f"ix_t_internship_teacher_makeup_{column}",
            "t_internship_teacher_makeup", [column],
        )


def downgrade() -> None:
    op.drop_table("t_internship_teacher_makeup")
    for name in (
        "watermark_text", "watermarked_sha256", "photo_sha256",
        "watermarked_file_id", "photo_file_id", "location_provider",
        "country_region", "coordinate_system", "distance_m", "result",
    ):
        op.drop_column("t_internship_teacher_checkin", name)
