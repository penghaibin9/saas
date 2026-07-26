"""学生主档统一整改 阶段 C · 学生账号稳定绑定表 + 历史回填。

新建 1 表：t_student_account_link（学生主档 ↔ 登录账号）。

为什么要它：此前全系统靠 `User.login_name == StudentProfile.student_no` 隐式关联学生与
账号——登录、移动端本人解析、消息受众都走这条约定。学号一更正，该生就登录不到自己的
档案、收不到班级消息。本表把这层关系显式固定下来，学号从此只是学籍属性，不再是关联键。

回填：按既有约定（同租户内 login_name == student_no 且账号类型为 STUDENT）建立 ACTIVE 链接，
source=BACKFILL。回填是幂等的，重复执行不会产生第二条。回填不到的学生保持未绑定状态，
由「账号异常中心 / 统一身份导入」后续处理，不在迁移里猜。

不做的事：不改 t_user、不改 t_student_profile、不动任何账号状态或密码。
回滚 drop_table，历史数据不受影响（回填只新增本表行）。

Revision ID: student_c1_account_link
Revises: portal_r3_sign_record
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "student_c1_account_link"
down_revision = "portal_r3_sign_record"
branch_labels = None
depends_on = None

TABLE = "t_student_account_link"


def _has_table(bind, t) -> bool:
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True,
                      comment="= t_student_profile.id"),
            sa.Column("user_id", sa.BigInteger(), nullable=False, index=True,
                      comment="= t_user.id"),
            sa.Column("link_status", sa.String(length=20), nullable=False,
                      server_default="ACTIVE", index=True,
                      comment="ACTIVE/SUSPENDED/REVOKED/MERGED"),
            sa.Column("bound_login_name", sa.String(length=100),
                      comment="绑定时登录名快照，仅供追溯"),
            sa.Column("bound_student_no", sa.String(length=50),
                      comment="绑定时学号快照，仅供追溯"),
            sa.Column("source", sa.String(length=30), nullable=False,
                      server_default="BACKFILL",
                      comment="IDENTITY_IMPORT/MANUAL/BACKFILL"),
            sa.Column("bound_at", sa.DateTime()),
            sa.Column("unbound_at", sa.DateTime()),
            sa.Column("remark", sa.String(length=500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        )
        # ACTIVE 唯一：一个学生只有一条有效绑定，一个账号也只绑一个学生。
        # MySQL 无部分索引，故把 link_status 纳入唯一键——历史行状态不同即可共存。
        op.create_unique_constraint("uk_sal_tenant_student_status", TABLE,
                                    ["tenant_id", "student_id", "link_status"])
        op.create_unique_constraint("uk_sal_tenant_user_status", TABLE,
                                    ["tenant_id", "user_id", "link_status"])
        op.create_index("ix_sal_tenant_student_status", TABLE,
                        ["tenant_id", "student_id", "link_status"])
        op.create_index("ix_sal_tenant_user_status", TABLE,
                        ["tenant_id", "user_id", "link_status"])

    _backfill(bind)


def _backfill(bind) -> None:
    """按历史约定回填：同租户 + login_name == student_no + 学生账号 + 双方均未软删。

    幂等：已存在任一状态链接的 (tenant_id, student_id) 或 (tenant_id, user_id) 跳过，
    避免重复执行时撞唯一键。回填不到的学生保持未绑定，由账号异常中心处理。
    """
    names = inspect(bind).get_table_names()
    if not {"t_student_profile", "t_user"}.issubset(set(names)):
        return  # 全新库尚未建主表时（如按 create_all 建库的测试环境）跳过回填

    bind.execute(sa.text(f"""
        INSERT INTO {TABLE}
            (tenant_id, student_id, user_id, link_status, bound_login_name,
             bound_student_no, source, bound_at, created_at, updated_at, is_deleted, version)
        SELECT s.tenant_id, s.id, u.id, 'ACTIVE', u.login_name,
               s.student_no, 'BACKFILL', NOW(), NOW(), NOW(), 0, 0
          FROM t_student_profile s
          JOIN t_user u
            ON u.tenant_id = s.tenant_id
           AND u.login_name = s.student_no
           AND u.user_type = 'STUDENT'
           AND u.is_deleted = 0
         WHERE s.is_deleted = 0
           AND NOT EXISTS (SELECT 1 FROM {TABLE} l
                            WHERE l.tenant_id = s.tenant_id AND l.student_id = s.id)
           AND NOT EXISTS (SELECT 1 FROM {TABLE} l2
                            WHERE l2.tenant_id = s.tenant_id AND l2.user_id = u.id)
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        op.drop_table(TABLE)
