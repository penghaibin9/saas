"""W7 review evidence metadata extension.

Production schema is owned by Alembic. This mirrors W7 columns/tables into SQLAlchemy
metadata so isolated MySQL pytest schemas created from metadata remain schema-exact.
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from app.models.base import Base
from app.models.graduation import GraduationReview

_review_table = GraduationReview.__table__
for _column in (
    sa.Column("material_id", sa.BigInteger(), nullable=True),
    sa.Column("file_version_id", sa.BigInteger(), nullable=True),
    sa.Column("source_sha256", sa.String(length=64), nullable=True),
    sa.Column("started_at", sa.DateTime(), nullable=True),
):
    if _column.name not in _review_table.c:
        _review_table.append_column(_column)

if "t_gd_review_feedback" not in Base.metadata.tables:
    GraduationReviewFeedbackTable = sa.Table(
        "t_gd_review_feedback", Base.metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("batch_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("source_record_id", sa.BigInteger(), nullable=False),
        sa.Column("review_id", sa.BigInteger(), nullable=True),
        sa.Column("material_id", sa.BigInteger(), nullable=True),
        sa.Column("file_version_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("round_no", sa.Integer(), nullable=False, default=1),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(2000), nullable=True),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("reviewer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_mentor_id", sa.BigInteger(), nullable=True),
        sa.Column("visible_to_student", sa.Boolean(), nullable=False, default=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("is_superseded", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_gd_review_feedback_idem"),
        sa.Index("ix_gd_feedback_batch_stage", "tenant_id", "batch_id", "stage", "created_at", "id"),
        sa.Index("ix_gd_feedback_source", "tenant_id", "stage", "source_record_id", "created_at", "id"),
        sa.Index("ix_gd_feedback_student_version", "tenant_id", "gd_student_id", "file_version_id", "created_at", "id"),
    )
else:
    GraduationReviewFeedbackTable = Base.metadata.tables["t_gd_review_feedback"]
