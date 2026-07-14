"""13A 统一附件：t_affairs_attachment（业务材料 file_id 回链 + 授权下载审计底座）

Revision ID: 0067_13a_affairs_attachment
Revises: 0066_13a_credit_eval_weight
Create Date: 2026-07-14

统一学工业务材料附件（违纪证据/送达回执/申诉材料/党团阶段材料/减免贷款回执/家校材料）：
file 字节仍走 t_file_object（file_service 真实上传），本表只存 (biz_type,biz_id,file_id) 回链 +
上传人；下载另走 require_permission(按 biz) + t_security_audit_log(SENSITIVE_EXPORT)。
幂等：表存在则跳过。回滚：drop。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0067_13a_affairs_attachment"
down_revision = "0066_13a_credit_eval_weight"
branch_labels = None
depends_on = None

T = "t_affairs_attachment"


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _has(bind, T):
        op.create_table(
            T,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("biz_type", sa.String(length=40), nullable=False,
                      comment="DISCIPLINE/DISCIPLINE_APPEAL/LEAGUE/CLUB/FUNDING/REDUCTION/LOAN/HOME_SCHOOL"),
            sa.Column("biz_id", sa.BigInteger(), nullable=False, index=True, comment="业务记录 id"),
            sa.Column("file_id", sa.BigInteger(), nullable=False, comment="回链 t_file_object.id"),
            sa.Column("file_name", sa.String(length=255), comment="展示名（脱敏用途，不含路径）"),
            sa.Column("note", sa.String(length=500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Index("ix_affairs_attachment_biz", "tenant_id", "biz_type", "biz_id"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    if _has(bind, T):
        op.drop_table(T)
