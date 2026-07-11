"""岗位实习中心 · 三方协议渲染正文快照列 rendered_body（P2-A 深化）

Revision ID: 0036_internship_agreement_rendered_body
Revises: 0035_internship_archive
Create Date: 2026-07-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0036_internship_agreement_rendered_body"
down_revision = "0035_internship_archive"
branch_labels = None
depends_on = None


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def _cols(bind, t):
    return {c["name"] for c in inspect(bind).get_columns(t)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_agreement"):
        return
    cols = _cols(bind, "t_internship_agreement")
    if "rendered_body" not in cols:
        op.add_column("t_internship_agreement",
                      sa.Column("rendered_body", sa.Text(), nullable=True,
                                comment="生成时模板变量渲染快照"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_agreement"):
        return
    cols = _cols(bind, "t_internship_agreement")
    if "rendered_body" in cols:
        op.drop_column("t_internship_agreement", "rendered_body")
