"""成绩任务唯一性安全守卫（纠正旧 0122 破坏性清理风险）。

背景：旧版 0122 曾按最大 ID 自动软删除重复成绩任务，并把已删行的 teaching_task_id 置空。
Alembic 不会重跑已执行的 0122，因此：
- 已执行旧 0122 的环境：本迁移做只读检查与约束兜底，绝不自动恢复/删除/清空。
- 全新环境：先跑修正后的安全 0122，再由本迁移复核。

本迁移只负责：
1. 检查是否仍存在非空 teaching_task_id 重复组；有则中止并输出清单（零写入）。
2. 检查 uk_aa_grade_task_tt 是否存在；缺失且无重复时补建。
3. 列出 is_deleted=1 且 teaching_task_id IS NULL 的可疑历史行，供人工复核（不自动恢复）。
   若唯一约束已存在且无重复组，可疑行仅警告不阻断后续迁移链。

Revision ID: 0126_aa_grade_task_uniqueness_guard
Revises: 0125_p1_delivery_idempotency
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

revision = "0126_aa_grade_task_uniqueness_guard"
down_revision = "0125_p1_delivery_idempotency"
branch_labels = None
depends_on = None

UK_NAME = "uk_aa_grade_task_tt"

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


def _uk_exists(bind) -> bool:
    return UK_NAME in _unique_constraints(bind, "t_aa_grade_task") or UK_NAME in _indexes(
        bind, "t_aa_grade_task"
    )


def find_grade_task_teaching_task_duplicates(bind):
    """与 0122 同源口径：teaching_task_id 非空的全部重复组（含软删除）。"""
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
    lines = [
        "检测到成绩任务重复占用同一教学任务，已中止唯一性守卫迁移，未修改任何业务行。",
        "请人工确认保留策略后再执行。状态排序仅为人工提示，不得自动据此删除。",
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
        ranked = sorted(detail, key=lambda r: (_STATUS_SORT.get(str(r[1] or ""), 9), r[0]))
        for r in ranked:
            lines.append(
                f"  id={r[0]} status={r[1]} is_deleted={int(bool(r[2]))} "
                f"created_at={r[3]} updated_at={r[4]}"
            )
        lines.append("")
    return "\n".join(lines)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "t_aa_grade_task" not in insp.get_table_names():
        return

    groups = find_grade_task_teaching_task_duplicates(bind)
    if groups:
        raise RuntimeError(format_grade_task_duplicate_report(bind, groups))

    if not _uk_exists(bind):
        op.create_unique_constraint(UK_NAME, "t_aa_grade_task", ["tenant_id", "teaching_task_id"])

    suspicious = bind.execute(text("""
        SELECT id, tenant_id, teaching_task_id, status, is_deleted, created_at, updated_at
        FROM t_aa_grade_task
        WHERE is_deleted = 1 AND teaching_task_id IS NULL
        ORDER BY updated_at DESC
        LIMIT 50
    """)).fetchall()
    if suspicious:
        lines = [
            "[WARN] 发现 is_deleted=1 且 teaching_task_id IS NULL 的成绩任务（可能含旧 0122 清理痕迹，"
            "也可能来自其他人工操作）。不得自动恢复；请人工复核：",
        ]
        for r in suspicious:
            lines.append(
                f"  id={r[0]} tenant_id={r[1]} status={r[3]} "
                f"created_at={r[5]} updated_at={r[6]}"
            )
        print("\n".join(lines))


def downgrade() -> None:
    # 守卫迁移不回滚唯一约束（约束属于业务不变量，downgrade 交由 0122）。
    pass
