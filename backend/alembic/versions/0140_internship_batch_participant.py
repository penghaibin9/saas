"""实习批次选人：规则表 + 参与人名单表（阶段 E）。

用组织范围选人替代反复导 Excel 名单：
- t_internship_batch_scope_rule：一批次一条选人规则（未冻结前可反复改，名单现算）
- t_internship_batch_participant：冻结后的正式名单快照（一批次一学生唯一）

只新增表，不改任何既有表结构，可安全回滚。
"""
from alembic import op
import sqlalchemy as sa

revision = "0140_intern_batch_participant"
down_revision = "0139_intern_evidence"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    """在线模式查库；离线 --sql 模式没有真连接可查，按"表不存在"处理照常输出 CREATE。

    直接 sa.inspect(bind) 会在 --sql 下抛 NoInspectionAvailable，运维想先导出 SQL
    审一遍再执行时就卡住了。"""
    ctx = op.get_context()
    if getattr(ctx, "as_sql", False):
        return False
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("t_internship_batch_scope_rule"):
        op.create_table(
            "t_internship_batch_scope_rule",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("rule_json", sa.JSON, nullable=True),
            sa.Column("last_preview_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_preview_at", sa.DateTime, nullable=True),
            sa.Column("frozen_at", sa.DateTime, nullable=True),
            sa.Column("frozen_by", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
            sa.Column("updated_by", sa.String(100), nullable=True),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer, nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_id", name="uk_intern_scope_batch"),
            mysql_charset="utf8mb4",
        )

    if not _has_table("t_internship_batch_participant"):
        op.create_table(
            "t_internship_batch_participant",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("source", sa.String(30), nullable=False, server_default="SCOPE"),
            sa.Column("snapshot_student_no", sa.String(50), nullable=True),
            sa.Column("snapshot_name", sa.String(100), nullable=True),
            sa.Column("snapshot_class_name", sa.String(100), nullable=True),
            sa.Column("snapshot_college_name", sa.String(100), nullable=True),
            sa.Column("internship_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
            sa.Column("remove_reason", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
            sa.Column("updated_by", sa.String(100), nullable=True),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer, nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_id", "student_id", name="uk_intern_participant"),
            mysql_charset="utf8mb4",
        )
        op.create_index("ix_intern_participant_batch", "t_internship_batch_participant",
                        ["tenant_id", "batch_id", "is_deleted"])


def downgrade() -> None:
    if _has_table("t_internship_batch_participant"):
        op.drop_table("t_internship_batch_participant")
    if _has_table("t_internship_batch_scope_rule"):
        op.drop_table("t_internship_batch_scope_rule")
