"""培养方案 Tier1 R3（三级模块补缺：实践环节 / 方案变更 / 方案归档）：
新建 t_aa_program_practice_segment。

背景：13B-培养方案二级模块第三轮续工三级菜单——实践环节 / 方案变更 / 方案归档。
- 实践环节：以「周数」为核心计量单位（认识实习/课程设计/生产实习/顶岗实习/毕业设计(论文)/军训/
  社会实践等），区别于理论课程的学时；既有 t_aa_program_course 无 weeks/组织方式/实践地点字段，
  故新建独立子表，与课程模块/学分要求/毕业要求同构（program_id 外键 + 编制态可写 + ACTIVE/REMOVED
  逻辑态），本迁移新建该表。
- 方案变更（状态生命周期：冻结/停用/恢复）复用既有 t_aa_program.status 字符串枚举——FROZEN/DISABLED
  两个终态早已写在模型注释与 create_new_version()/list_program_versions() 的前置校验里（代码事实：
  canNewVersion 已预期这两个终态可再新建版本），只是此前从未有 service/端点能把方案实际置于这两个
  状态，本轮在 service 层补齐 change_program_status()，不改表结构。
- 方案归档为只读派生视图（DISABLED 终态 + 版本链中已被更新版本取代的历史版本），复用既有
  t_aa_program 数据与 prev_version_id 版本链，不需要新表/新状态值。
以上三项合计只新建 1 张表。全新业务表，downgrade drop。幂等：inspect 判表。

Revision ID: aa_training_r3
Revises: aa_course_lib_tier1_r2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_training_r3"
down_revision = "aa_courses_r3"
branch_labels = None
depends_on = None

TABLE = "t_aa_program_practice_segment"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("program_id", sa.BigInteger(), nullable=False),
            sa.Column("segment_name", sa.String(200), nullable=False),
            sa.Column("segment_type", sa.String(50), nullable=False, server_default="OTHER"),
            sa.Column("open_term_no", sa.Integer()),
            sa.Column("weeks", sa.Numeric(4, 1)),
            sa.Column("credit", sa.Numeric(4, 1)),
            sa.Column("org_mode", sa.String(20), nullable=False, server_default="CENTRALIZED"),
            sa.Column("location", sa.String(200)),
            sa.Column("assessment_mode", sa.String(20), nullable=False, server_default="CHECK"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_aa_program_practice_tenant", TABLE, ["tenant_id"])
        op.create_index("ix_aa_program_practice_program", TABLE, ["program_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
