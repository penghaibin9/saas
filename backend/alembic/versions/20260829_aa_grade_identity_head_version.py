"""add grade identity head optimistic-lock version

Revision ID: 20260829_aa_grade_head_ver
Revises: 20260829_affairs_sandbox_merge
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_aa_grade_head_ver"
down_revision = "20260829_affairs_sandbox_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_aa_grade_identity_head",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="乐观锁",
        ),
    )
    op.alter_column(
        "t_aa_grade_identity_head",
        "version",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
        existing_comment="乐观锁",
    )


def downgrade() -> None:
    op.drop_column("t_aa_grade_identity_head", "version")
