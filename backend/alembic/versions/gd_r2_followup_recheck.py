"""Graduation round-2 follow-up: explicit plagiarism recheck lineage.

Revision ID: gd_r2_followup_recheck
Revises: 0136_gd_concurrency
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "gd_r2_followup_recheck"
down_revision = "0136_gd_concurrency"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("gd_r2_followup_recheck must be executed on MySQL")
    cols = {column["name"] for column in inspect(bind).get_columns("t_gd_plagiarism")}
    if "recheck_of_id" not in cols:
        op.add_column("t_gd_plagiarism", sa.Column("recheck_of_id", sa.BigInteger()))
        op.create_index("ix_t_gd_plagiarism_recheck_of_id", "t_gd_plagiarism", ["recheck_of_id"])

    # 历史数据缺少稳定关联时不能按姓名猜测，统一进入人工复核清单。
    issue_specs = (
        ("t_gd_review", "MISSING_FINAL_ID", "gd_final_id IS NULL",
         "历史评阅未绑定正式成果，禁止自动猜测"),
        ("t_gd_review", "MISSING_REVIEWER_ID", "reviewer_mentor_id IS NULL",
         "历史评阅缺少稳定评阅人ID，禁止按姓名静默合并"),
        ("t_gd_plagiarism", "MISSING_FINAL_ID", "gd_final_id IS NULL",
         "历史查重未绑定成果，不能自动创建复查链"),
    )
    for table_name, issue_type, predicate, detail in issue_specs:
        result = bind.execute(text(f"""
            INSERT INTO t_gd_migration_issue
              (tenant_id, table_name, row_id, issue_type, detail, status, created_at)
            SELECT src.tenant_id, :table_name, src.id, :issue_type, :detail, 'OPEN', NOW()
            FROM {table_name} src
            WHERE {predicate}
              AND NOT EXISTS (
                SELECT 1 FROM t_gd_migration_issue issue
                WHERE issue.tenant_id=src.tenant_id
                  AND issue.table_name=:table_name
                  AND issue.row_id=src.id
                  AND issue.issue_type=:issue_type
              )
        """), {
            "table_name": table_name, "issue_type": issue_type, "detail": detail,
        })
        print(
            f"[gd_r2_followup_recheck] {table_name}/{issue_type}: "
            f"new review issues={result.rowcount}"
        )


def downgrade():
    bind = op.get_bind()
    cols = {column["name"] for column in inspect(bind).get_columns("t_gd_plagiarism")}
    indexes = {index["name"] for index in inspect(bind).get_indexes("t_gd_plagiarism")}
    if "ix_t_gd_plagiarism_recheck_of_id" in indexes:
        op.drop_index("ix_t_gd_plagiarism_recheck_of_id", table_name="t_gd_plagiarism")
    if "recheck_of_id" in cols:
        op.drop_column("t_gd_plagiarism", "recheck_of_id")
