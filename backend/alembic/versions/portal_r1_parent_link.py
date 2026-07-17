"""学生 PC 门户 R1 · 家长授权代理绑定表：

新建 1 表：t_student_parent_link（学生本人授权家长 proxy 只读；link_status ACTIVE/REVOKED；
家长手机号 *_encrypted 存值 + *_hash 供验证码登录/查重；visible_scopes JSON 可见范围）。
无历史数据兼容问题（全新表）。回滚 drop_table。

Revision ID: portal_r1_parent_link
Revises: aa_correction_material_r3
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "portal_r1_parent_link"
down_revision = "aa_correction_material_r3"
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


def _has_table(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_student_parent_link"):
        return
    op.create_table(
        "t_student_parent_link",
        *_pk_tenant(),
        sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_no", sa.String(length=50), nullable=False, index=True),
        sa.Column("guardian_name", sa.String(length=100), nullable=False),
        sa.Column("relation", sa.String(length=20), nullable=False, server_default="PARENT"),
        sa.Column("guardian_phone_encrypted", sa.String(length=500), nullable=False),
        sa.Column("guardian_phone_hash", sa.String(length=128), nullable=False, index=True),
        sa.Column("visible_scopes", sa.JSON()),
        sa.Column("link_status", sa.String(length=20), nullable=False, server_default="ACTIVE", index=True),
        *_COMMON,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_student_parent_link"):
        op.drop_table("t_student_parent_link")
