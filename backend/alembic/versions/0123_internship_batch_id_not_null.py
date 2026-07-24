"""岗位实习：t_internship_record.batch_id 前置检查 + 条件 NOT NULL。

- 若存在 batch_id IS NULL 或同租户同学生同批次重复有效记录，迁移中止并提示人工修复。
- 数据干净后才将 batch_id 改为 NOT NULL，并保留 uk_intern_stu_batch。
- 禁止自动猜测历史批次归属。

Revision ID: 0123_internship_batch_id_not_null
Revises: 0121_file_object_acl
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0123_internship_batch_id_not_null"
down_revision = "0121_file_object_acl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "t_internship_record" not in insp.get_table_names():
        return
    cols = {c["name"]: c for c in insp.get_columns("t_internship_record")}
    if "batch_id" not in cols:
        return

    null_cnt = bind.execute(text(
        "SELECT COUNT(*) FROM t_internship_record "
        "WHERE batch_id IS NULL AND is_deleted = 0"
    )).scalar() or 0
    dup_cnt = bind.execute(text(
        "SELECT COUNT(*) FROM ("
        "  SELECT tenant_id, student_id, batch_id FROM t_internship_record "
        "  WHERE is_deleted = 0 AND batch_id IS NOT NULL "
        "  GROUP BY tenant_id, student_id, batch_id HAVING COUNT(*) > 1"
        ") t"
    )).scalar() or 0

    if null_cnt or dup_cnt:
        raise RuntimeError(
            f"internship batch_id 前置检查失败：null={null_cnt}, duplicates={dup_cnt}。"
            "请先用 backend/scripts/internship_batch_null_scan.py 扫描，"
            "并由人工提供映射修复后重跑本迁移。禁止自动猜测批次。"
        )

    # 已是 NOT NULL 则跳过
    if cols["batch_id"].get("nullable") is False:
        return

    dialect = bind.dialect.name
    if dialect == "mysql":
        op.alter_column(
            "t_internship_record", "batch_id",
            existing_type=sa.BigInteger(),
            nullable=False,
            existing_nullable=True,
        )
    else:
        # 非 MySQL 环境不强制（项目生产为 MySQL-only）
        pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "t_internship_record" not in insp.get_table_names():
        return
    if bind.dialect.name == "mysql":
        op.alter_column(
            "t_internship_record", "batch_id",
            existing_type=sa.BigInteger(),
            nullable=True,
            existing_nullable=False,
        )
