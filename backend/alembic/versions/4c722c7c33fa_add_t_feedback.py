"""add_t_feedback

Revision ID: 4c722c7c33fa
Revises: aa_sandbox_baseline
Create Date: 2026-07-17 07:28:34.422538

守卫说明（2026-07-17 加固）：0001_init_core_tables 是 `metadata.create_all` 活基线——全新库
跑链时第一步就会按当前代码建出全部模型表（含本表），故本迁移必须幂等：表已存在则整体跳过，
否则全新库纯迁移建库在此处撞 "table t_feedback already exists"（增量升级的现网库不受影响，
表不存在时照常创建）。与 0085-0098 / aa_sandbox_baseline 的 inspect 守卫同款。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '4c722c7c33fa'
down_revision = 'aa_sandbox_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if 't_feedback' in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        't_feedback',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('user_key', sa.String(length=100), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False, server_default='STUDENT'),
        sa.Column('category', sa.String(length=30), nullable=False, server_default='OTHER'),
        sa.Column('title', sa.String(length=120), nullable=True),
        sa.Column('content', sa.String(length=2000), nullable=False),
        sa.Column('contact', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='SUBMITTED'),
        sa.Column('reply', sa.String(length=2000), nullable=True),
        sa.Column('handled_by', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_t_feedback_tenant_id', 't_feedback', ['tenant_id'])
    op.create_index('ix_t_feedback_user_key', 't_feedback', ['user_key'])


def downgrade() -> None:
    if 't_feedback' not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_index('ix_t_feedback_user_key', table_name='t_feedback')
    op.drop_index('ix_t_feedback_tenant_id', table_name='t_feedback')
    op.drop_table('t_feedback')
