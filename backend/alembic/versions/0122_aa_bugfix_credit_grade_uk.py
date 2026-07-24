"""教务 Bug 修复：培养方案学分小数精度 + 成绩任务教学任务唯一约束。

- t_aa_program.total_credits Integer → Numeric(4,1)
- t_aa_program_course.credit_snapshot Integer → Numeric(4,1)
- t_aa_grade_task 增加 uk_aa_grade_task_tt(tenant_id, teaching_task_id)
  MySQL UNIQUE 允许多个 NULL，历史无 teaching_task_id 的任务不受影响。

安全规则（生产数据保护）：
- 检测到同租户同 teaching_task_id 的重复行时，中止迁移、零写入业务行。
- 禁止按最大 ID 自动保留、禁止自动软删除、禁止清空 teaching_task_id。
- 学分字段变更与唯一约束均幂等；有重复时两者均不执行，避免半迁移。

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

UK_NAME = "uk_aa_grade_task_tt"

# 人工裁定排序提示（仅报告展示，绝不自动据此删除）
_STATUS_SORT = {
    "PUBLISHED": 0,
    "ARCHIVED": 0,
    "ACADEMIC_REVIEW": 1,
    "COLLEGE_REVIEW": 2,
    "SUBMITTED": 2,
    "INPUTTING": 3,
    "RETURNED": 3,
    "NOT_STARTED": 4,
}


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


def find_grade_task_teaching_task_duplicates(bind):
    """查询所有 teaching_task_id 非空的重复组（含已软删除行）。

    唯一约束覆盖全部记录，故不能只看 is_deleted=0。
    返回 [(tenant_id, teaching_task_id, count), ...]
    """
    rows = bind.execute(text("""
        SELECT tenant_id, teaching_task_id, COUNT(*) AS task_count
        FROM t_aa_grade_task
        WHERE teaching_task_id IS NOT NULL
        GROUP BY tenant_id, teaching_task_id
        HAVING COUNT(*) > 1
        ORDER BY tenant_id, teaching_task_id
    """)).fetchall()
    return [(r[0], r[1], int(r[2])) for r in rows]


def format_grade_task_duplicate_report(bind, groups) -> str:
    """生成可人工核对的重复组成绩任务清单（只读）。"""
    lines = [
        "检测到成绩任务重复占用同一教学任务，已中止唯一约束迁移，未修改任何业务行。",
        "业务规则：一个教学任务终身只允许一条成绩任务（含 ARCHIVED / 已软删除）。",
        "请人工确认保留策略后重新执行迁移。裁定时建议优先核对：是否已发布、是否有成绩明细、",
        "是否已投影正式成绩、是否有工作流/审计；下列状态排序仅为提示，不得自动据此删除。",
        "",
    ]
    for tenant_id, teaching_task_id, cnt in groups:
        lines.append(
            f"=== 重复组 tenant_id={tenant_id} teaching_task_id={teaching_task_id} count={cnt} ==="
        )
        detail = bind.execute(text("""
            SELECT id, status, is_deleted, created_at, updated_at
            FROM t_aa_grade_task
            WHERE tenant_id = :tid AND teaching_task_id = :ttid
            ORDER BY id
        """), {"tid": tenant_id, "ttid": teaching_task_id}).fetchall()
        ranked = sorted(
            detail,
            key=lambda r: (_STATUS_SORT.get(str(r[1] or ""), 9), r[0]),
        )
        for r in ranked:
            lines.append(
                f"  id={r[0]} status={r[1]} is_deleted={int(bool(r[2]))} "
                f"created_at={r[3]} updated_at={r[4]}"
            )
        lines.append("")
    return "\n".join(lines)


def _uk_exists(bind) -> bool:
    existing_uks = _unique_constraints(bind, "t_aa_grade_task")
    existing_ix = _indexes(bind, "t_aa_grade_task")
    return UK_NAME in existing_uks or UK_NAME in existing_ix


def _abort_on_duplicates(bind) -> None:
    groups = find_grade_task_teaching_task_duplicates(bind)
    if not groups:
        return
    raise RuntimeError(format_grade_task_duplicate_report(bind, groups))


def _alter_credit_columns(bind) -> None:
    prog_cols = _cols(bind, "t_aa_program")
    if prog_cols and "total_credits" in prog_cols:
        col = prog_cols["total_credits"]
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


def upgrade() -> None:
    bind = op.get_bind()
    gt_cols = _cols(bind, "t_aa_grade_task")

    # 方案 A1：先检查重复；有重复则学分与唯一约束均不执行，避免半迁移。
    if gt_cols and not _uk_exists(bind):
        _abort_on_duplicates(bind)

    _alter_credit_columns(bind)

    if not gt_cols:
        return
    if _uk_exists(bind):
        return

    # 创建约束前再确认一次（并发写入窗口）
    _abort_on_duplicates(bind)
    op.create_unique_constraint(UK_NAME, "t_aa_grade_task", ["tenant_id", "teaching_task_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_uks = _unique_constraints(bind, "t_aa_grade_task")
    if UK_NAME in existing_uks:
        op.drop_constraint(UK_NAME, "t_aa_grade_task", type_="unique")

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
