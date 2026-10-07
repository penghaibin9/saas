"""O6 newcomer self activation and reserved student number.

Revision ID: 20260901_orientation_self_activate_o6
Revises: 20260901_school_xlsx_x1
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260901_orientation_self_activate_o6"
down_revision = "20260901_school_xlsx_x1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_orientation_student",
        sa.Column("student_no", sa.String(length=50), nullable=True,
                  comment="学校预分配正式学号；新生自助激活使用"),
    )
    op.create_unique_constraint(
        "uk_ori_reserved_student_no", "t_orientation_student", ["tenant_id", "student_no"]
    )
    op.create_table(
        "t_orientation_activation_challenge",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("orientation_student_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_nonce_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="VERIFIED"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("client_request_id", sa.String(length=100), nullable=True),
        sa.Column("bound_user_id", sa.BigInteger(), nullable=True),
        sa.Column("wechat_bound", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "orientation_student_id", name="uk_ori_activation_student"),
        sa.UniqueConstraint("token_hash", name="uk_ori_activation_token_hash"),
    )
    op.create_index(
        "ix_ori_activation_expiry", "t_orientation_activation_challenge", ["status", "expires_at"]
    )
    op.create_index(
        "ix_ori_activation_bound_user", "t_orientation_activation_challenge", ["bound_user_id"]
    )
    op.create_index(
        "ix_ori_activation_orientation_student",
        "t_orientation_activation_challenge", ["orientation_student_id"],
    )
    op.create_index(
        "ix_ori_activation_tenant", "t_orientation_activation_challenge", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_table("t_orientation_activation_challenge")
    op.drop_constraint("uk_ori_reserved_student_no", "t_orientation_student", type_="unique")
    op.drop_column("t_orientation_student", "student_no")
