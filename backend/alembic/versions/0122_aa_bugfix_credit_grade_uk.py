"""教务 Bug 修复：培养方案学分小数精度 + 成绩任务教学任务唯一约束。

- t_aa_program.total_credits Integer → Numeric(4,1)
- t_aa_program_course.credit_snapshot Integer → Numeric(4,1)
- t_aa_grade_task 增加 uk_aa_grade_task_tt(tenant_id, teaching_task_id)
  MySQL UNIQUE 允许多个 NULL，历史无 teaching_task_id 的任务不受影响。
  若已有重复 (tenant_id, teaching_task_id) 非空行，先软归档重复项再加约束。

Revision ID: 0122_aa_bugfix_credit_grade_uk
Revises: 0121_file_object_acl
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0122_aa_bugfix_credit_grade_uk"
down_revision = "0121_file_object_acl"
branch_labels = None
depends_on = None


def _cols(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return {}
    return {c["name"]: c for c in insp.get_columns(table)}


def _indexes(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {ix["name"] for ix in insp.get_indexes(table)}


def _unique_constraints(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {uc["name"] for uc in insp.get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 培养方案学分：Integer → Numeric(4,1) ──
    prog_cols = _cols(bind, "t_aa_program")
    if prog_cols and "total_credits" in prog_cols:
        col = prog_cols["total_credits"]
        # 已是 Numeric 则跳过（幂等）
        if not isinstance(col.get("type"), sa.Numeric):
            op.alter_column(
                "t_aa_program", "total_credits",
                existing_type=sa.Integer(),
                type_=sa.Numeric(4, 1),
                existing_nullable=True,
                comment="毕业总学分(支持0.5步长)",
            )

    pc_cols = _cols(bind, "t_aa_program_course")
    if pc_cols and "credit_snapshot" in pc_cols:
        col = pc_cols["credit_snapshot"]
        if not isinstance(col.get("type"), sa.Numeric):
            op.alter_column(
                "t_aa_program_course", "credit_snapshot",
                existing_type=sa.Integer(),
                type_=sa.Numeric(4, 1),
                existing_nullable=True,
                comment="方案课程学分快照(支持0.5步长)",
            )

    # ── 成绩任务：同租户同教学任务仅允许一条有效任务 ──
    gt_cols = _cols(bind, "t_aa_grade_task")
    if not gt_cols:
        return
    uk_name = "uk_aa_grade_task_tt"
    existing_uks = _unique_constraints(bind, "t_aa_grade_task")
    existing_ix = _indexes(bind, "t_aa_grade_task")
    if uk_name in existing_uks or uk_name in existing_ix:
        return

    # 历史重复：保留最新 id，其余软删（不物理删除生产数据）
    bind.execute(text("""
        UPDATE t_aa_grade_task t
        INNER JOIN (
            SELECT tenant_id, teaching_task_id, MAX(id) AS keep_id
            FROM t_aa_grade_task
            WHERE teaching_task_id IS NOT NULL AND is_deleted = 0
            GROUP BY tenant_id, teaching_task_id
            HAVING COUNT(*) > 1
        ) d ON t.tenant_id = d.tenant_id
            AND t.teaching_task_id = d.teaching_task_id
            AND t.id <> d.keep_id
            AND t.is_deleted = 0
        SET t.is_deleted = 1,
            t.updated_at = UTC_TIMESTAMP()
    """))

    # MySQL：软删后仍可能因 UNIQUE 含已删行冲突；用生成列或仅对未删建唯一。
    # 采用应用层幂等 + 普通唯一索引（NULL 可重复）；已软删的重复 teaching_task_id
    # 若仍挡约束，再把已删行的 teaching_task_id 置空保留审计痕迹。
    bind.execute(text("""
        UPDATE t_aa_grade_task t
        INNER JOIN (
            SELECT tenant_id, teaching_task_id, MAX(id) AS keep_id
            FROM t_aa_grade_task
            WHERE teaching_task_id IS NOT NULL
            GROUP BY tenant_id, teaching_task_id
            HAVING COUNT(*) > 1
        ) d ON t.tenant_id = d.tenant_id
            AND t.teaching_task_id = d.teaching_task_id
            AND t.id <> d.keep_id
        SET t.teaching_task_id = NULL
        WHERE t.is_deleted = 1
    """))

    op.create_unique_constraint(uk_name, "t_aa_grade_task", ["tenant_id", "teaching_task_id"])


def downgrade() -> None:
    bind = op.get_bind()
    uk_name = "uk_aa_grade_task_tt"
    existing_uks = _unique_constraints(bind, "t_aa_grade_task")
    if uk_name in existing_uks:
        op.drop_constraint(uk_name, "t_aa_grade_task", type_="unique")

    pc_cols = _cols(bind, "t_aa_program_course")
    if pc_cols and "credit_snapshot" in pc_cols:
        op.alter_column(
            "t_aa_program_course", "credit_snapshot",
            existing_type=sa.Numeric(4, 1),
            type_=sa.Integer(),
            existing_nullable=True,
        )

    prog_cols = _cols(bind, "t_aa_program")
    if prog_cols and "total_credits" in prog_cols:
        op.alter_column(
            "t_aa_program", "total_credits",
            existing_type=sa.Numeric(4, 1),
            type_=sa.Integer(),
            existing_nullable=True,
        )
