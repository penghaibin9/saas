"""add t_tenant_portal_config — 学生 PC 门户租户配置表（P1 收口）

Revision ID: 0002_tenant_portal_config
Revises: 0001_init_core_tables
Create Date: 2026-07-05

说明：显式 DDL 建表（不使用 metadata.create_all 代替），字段/索引/唯一约束与
app.models.portal.TenantPortalConfig 完全一致，支持 downgrade，且不触碰任何其它表。

存量库场景：库中尚无 t_tenant_portal_config → 本迁移创建它。
全新库场景：0001 的 create_all 已把当前所有模型（含本表）建好 → 本迁移检测到已存在则跳过，
           避免"表已存在"报错。两种场景都安全、不清空数据。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002_tenant_portal_config"
down_revision = "0001_init_core_tables"
branch_labels = None
depends_on = None

TABLE = "t_tenant_portal_config"
IDX = "ix_t_tenant_portal_config_tenant_id"
# 主键与模型一致：BIGINT（SQLite 下映射为 INTEGER 以获得自增）
BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        return  # 已存在（新库 create_all 场景）：幂等跳过，不影响现有表/数据

    op.create_table(
        TABLE,
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="租户(学校)ID，行级隔离"),
        sa.Column("config_json", sa.JSON(), nullable=True,
                  comment="studentPortal 覆盖配置：enabled/portalName/portalUrl/modules/features/requiredPackage/loginAccountTips"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uk_tenant_portal_config"),
    )
    op.create_index(IDX, TABLE, ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    existing_idx = {i["name"] for i in inspect(bind).get_indexes(TABLE)}
    if IDX in existing_idx:
        op.drop_index(IDX, table_name=TABLE)
    op.drop_table(TABLE)
