"""毕设题目使用稳定导师 ID，姓名降级为显示快照。

Revision ID: 0135_gd_topic_advisor_mentor_id
Revises: 0134_org_code_empty_to_null
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0135_gd_topic_advisor_mentor_id"
down_revision = "0134_org_code_empty_to_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("t_gd_topic")}
    if "advisor_mentor_id" not in cols:
        op.add_column("t_gd_topic", sa.Column("advisor_mentor_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_t_gd_topic_advisor_mentor_id", "t_gd_topic", ["advisor_mentor_id"])
    # 仅唯一姓名可安全回填；同名导师保持 NULL，权限检查 fail-closed。
    bind.execute(text("""
        UPDATE t_gd_topic t
        JOIN (
          SELECT tenant_id, teacher_name, MIN(id) AS mentor_id
          FROM t_gd_mentor
          WHERE is_deleted = 0 AND teacher_name IS NOT NULL AND teacher_name <> ''
          GROUP BY tenant_id, teacher_name
          HAVING COUNT(*) = 1
        ) m ON m.tenant_id = t.tenant_id AND m.teacher_name = t.advisor_name
        SET t.advisor_mentor_id = m.mentor_id
        WHERE t.advisor_mentor_id IS NULL AND t.is_deleted = 0
    """))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "ix_t_gd_topic_advisor_mentor_id" in {i["name"] for i in insp.get_indexes("t_gd_topic")}:
        op.drop_index("ix_t_gd_topic_advisor_mentor_id", table_name="t_gd_topic")
    if "advisor_mentor_id" in {c["name"] for c in inspect(op.get_bind()).get_columns("t_gd_topic")}:
        op.drop_column("t_gd_topic", "advisor_mentor_id")
