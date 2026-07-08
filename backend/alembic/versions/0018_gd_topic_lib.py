"""毕设题目库字段增强 t_gd_topic

Revision ID: 0018_gd_topic_lib
Revises: 0017_gd_student_subpanels
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0018_gd_topic_lib"
down_revision = "0017_gd_student_subpanels"
branch_labels = None
depends_on = None

T = "t_gd_topic"

COLS = [
    ("batch_id", sa.BigInteger(), {"nullable": True}),
    ("topic_no", sa.String(50), {"nullable": True}),
    ("source_type", sa.String(30), {"nullable": False, "server_default": "TEACHER"}),
    ("college_id", sa.String(50), {"nullable": True}),
    ("major_id", sa.String(50), {"nullable": True}),
    ("category", sa.String(50), {"nullable": True}),
    ("difficulty", sa.String(30), {"nullable": True}),
    ("enterprise_name", sa.String(200), {"nullable": True}),
    ("requirements", sa.String(2000), {"nullable": True}),
    ("outcome", sa.String(2000), {"nullable": True}),
    ("skills", sa.String(500), {"nullable": True}),
    ("attachments_json", sa.JSON(), {"nullable": True}),
    ("review_status", sa.String(50), {"nullable": False, "server_default": "DRAFT"}),
    ("review_comment", sa.String(500), {"nullable": True}),
    ("archive_reason", sa.String(500), {"nullable": True}),
    ("archived_at", sa.DateTime(), {"nullable": True}),
]


def _has_col(bind, col):
    return col in {c["name"] for c in inspect(bind).get_columns(T)}


def upgrade() -> None:
    bind = op.get_bind()
    if T not in inspect(bind).get_table_names():
        return
    for name, coltype, kw in COLS:
        if not _has_col(bind, name):
            op.add_column(T, sa.Column(name, coltype, **kw))
    if not _has_col(bind, "batch_id"):
        pass
    elif _has_col(bind, "batch_id"):
        try:
            op.create_index("ix_t_gd_topic_batch_id", T, ["batch_id"])
        except Exception:
            pass
    # 历史已确认题目同步审核态
    if _has_col(bind, "review_status"):
        op.execute(sa.text(
            "UPDATE t_gd_topic SET review_status='APPROVED' "
            "WHERE status='CONFIRMED' AND (review_status IS NULL OR review_status='DRAFT')"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if T not in inspect(bind).get_table_names():
        return
    for name, _, _ in reversed(COLS):
        if _has_col(bind, name):
            op.drop_column(T, name)
