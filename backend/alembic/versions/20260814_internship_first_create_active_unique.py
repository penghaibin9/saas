"""变更申请/意向/合规豁免：用生成列 + 唯一索引锁住「同时只能有一条活动记录」

Revision ID: 20260814_ix_first_create
Revises: 20260814_ix_filing_actor_cols
Create Date: 2026-08-14

批次二对剩余 6 个实体做首次创建并发实测（真实 MySQL，每个实体跑 5 轮独立种子），
三个实体确认存在竞态，形状与上一批已修的请假/补卡完全相同——
「无锁 SELECT 查重 → 没有就 INSERT」，两个并发请求同时查到「没有」，各插一条：

| 实体 | 创建函数 | 实测 5 轮落库条数 |
|---|---|---|
| 变更申请 | `internship_change_service.student_apply()` | [1, 2, 2, 2, 2] |
| 意向 | `internship_match_service.create_intention()` | [1, 2, 2, 2, 2] |
| 合规豁免 | `internship_compliance_service.grant_exemption()` | 2（连查重代码都没有） |

注意单轮命中率约 80%——竞态是间歇性的，一轮一测会时红时绿，所以测试跑多轮。

后果都不是"数据不好看"：变更申请重复会让教师队列里出现同一学生的两条申请，
批了一条另一条还挂着；意向重复会让匹配算法对同一学生算出两套推荐。

**不变量是「同时只能有一条活动记录」，不是「一辈子只能有一条」**：学生整个实习期会陆续
提交多次变更、撤回后重填意向、旧豁免过期后重新申请。普通唯一约束表达不了"仅当状态为 X 时
唯一"，本仓已有现成写法——`20260806_discipline_package11.py` 的 `active_student_id`
STORED GENERATED 列（非活动时为 NULL）+ 唯一索引，MySQL 视 NULL 互不相同，于是历史行
数量不限、活动行至多一条。上一批的 `20260814_ix_leave_makeup_active` 也是这一套。

生成列表达式与各 service 的去重谓词逐条对齐：

- 变更申请：`is_deleted=0 AND status='PENDING'` → internship_id；唯一键 (tenant_id, 该列)
- 意向：`is_deleted=0 AND status IN ('DRAFT','SUBMITTED')` → record_id；同上
- 豁免：`is_deleted=0 AND status='PENDING_REVIEW'` → internship_id；
  唯一键再加 check_code（豁免是按检查项去重的）

**豁免为什么只锁 PENDING_REVIEW、不含 APPROVED**：已批准的豁免会随 `valid_until` 过期
（见 `evaluate_internship_compliance` 里的 apply_exemption），过期后学校应当能重新申请。
而 MySQL 生成列必须是确定性表达式、不能引用 NOW()，"是否过期"进不了约束。已生效豁免的
重复申请由 service 层显式校验拦截——那不是竞态（已有行是可见的），数据完整性由本约束兜底。

升级前先扫历史重复；有脏数据时直接失败并把冲突分组打出来，不静默删数据——这些都是学校
真实提交的申请，删哪条该由学校决定。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_ix_first_create"
down_revision = "20260814_ix_filing_actor_cols"
branch_labels = None
depends_on = None

#: (表名, 生成列名, 生成表达式来源列, 活动状态 SQL 谓词, 唯一索引名, 唯一键附加列, 人话名)
_SPECS = (
    ("t_internship_change_request", "active_pending_internship_id", "internship_id",
     "status = 'PENDING'", "uk_ix_change_active_pending", (), "变更申请"),
    ("t_internship_intention", "active_record_id", "record_id",
     "status IN ('DRAFT', 'SUBMITTED')", "uk_ix_intention_active", (), "意向"),
    ("t_internship_compliance_exemption", "active_pending_internship_id", "internship_id",
     "status = 'PENDING_REVIEW'", "uk_ix_exempt_active_pending", ("check_code",), "合规豁免"),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    names = {i["name"] for i in insp.get_indexes(table)}
    # 唯一约束在 MySQL 上也表现为索引，但部分驱动会把它单列在 unique_constraints 里。
    names |= {u["name"] for u in insp.get_unique_constraints(table)}
    return {n for n in names if n}


def _scan_duplicates(bind, table: str, source_col: str, active_sql: str,
                     extra_cols: tuple[str, ...]) -> list:
    """升级前扫描已经违反不变量的历史数据。

    有重复就停下来让人处理：这些是学校真实提交的申请，删哪条是学校的决定，
    不是迁移脚本能替他们做的。
    """
    group_cols = ", ".join(("tenant_id", source_col, *extra_cols))
    return list(bind.execute(sa.text(f"""
        SELECT {group_cols}, COUNT(*) AS c
        FROM {table}
        WHERE is_deleted = 0 AND {active_sql}
        GROUP BY {group_cols}
        HAVING c > 1
        LIMIT 50
    """)).fetchall())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()

    for table, gen_col, source_col, active_sql, uk, extra, label in _SPECS:
        if table not in tables:
            continue

        dups = _scan_duplicates(bind, table, source_col, active_sql, extra)
        if dups:
            raise RuntimeError(
                f"{table}（{label}）已存在多条同时活动的记录，唯一索引无法建立。"
                f"这些是学校真实提交的数据，请先由学校决定保留哪条再重跑迁移。"
                f"冲突分组（最多列出 50 组）：{dups}")

        if gen_col not in _columns(table):
            op.execute(sa.text(f"""
                ALTER TABLE {table}
                ADD COLUMN {gen_col} BIGINT
                GENERATED ALWAYS AS (
                    CASE WHEN is_deleted = 0 AND {active_sql}
                         THEN {source_col} ELSE NULL END
                ) STORED
                COMMENT '仅活动状态时等于 {source_col}，用于唯一索引；其余为 NULL'
            """))

        if uk not in _indexes(table):
            op.create_index(uk, table, ["tenant_id", gen_col, *extra], unique=True)


def downgrade() -> None:
    tables = _tables()
    # 逆序拆除，与 upgrade 对称。
    for table, gen_col, _source, _active, uk, _extra, _label in reversed(_SPECS):
        if table not in tables:
            continue
        if uk in _indexes(table):
            op.drop_index(uk, table_name=table)
        if gen_col in _columns(table):
            op.drop_column(table, gen_col)
