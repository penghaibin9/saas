"""请假与补卡：用生成列 + 唯一索引锁住「同时只能有一条活动申请」

Revision ID: 20260814_ix_leave_makeup_active
Revises: 20260813_ix_incident_idem
Create Date: 2026-08-14

`internship_leave_service.apply()` 与 `internship_makeup_service.apply()` 都是
「无锁 SELECT 查 PENDING → 没有就 INSERT」。这两张表既没有唯一约束、也没有
`SELECT ... FOR UPDATE`（同批其它实体至少有其一），所以两个并发请求会同时查到
「没有」，各建一条。学生双击或网络重试就能造出两条待审批申请，教师队列里出现同一个人
的两条记录，批了一条另一条还挂着。

应用层查重不等于并发唯一，这条只能靠数据库兜底。但「一个学生只能有一条请假」不成立——
学生在整个实习期会陆续请很多次假，冲突的只有**同时活动**的那些。普通唯一约束表达不了
「仅当 status=PENDING 时唯一」。

本仓已有现成写法：`20260806_discipline_package11.py` 给 `t_cs_service_student` 加了
`active_student_id` STORED GENERATED 列（非活动时为 NULL），再对它建唯一索引。MySQL 的
唯一索引把 NULL 视作互不相同，于是历史行数量不限，活动行至多一条。这里照抄同一套。

生成列表达式与 service 的去重谓词逐条对齐：
- 请假：`is_deleted=0 AND status='PENDING'` → internship_id，唯一键 (tenant_id, 该列)
- 补卡：同上，唯一键再加 checkin_date（补卡是按天去重的）

升级前先扫历史重复；有脏数据时直接失败并把清单打出来，不静默丢数据——请假和补卡都是
学生真实提交的申请，该由学校决定保留哪条。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_ix_leave_makeup_active"
down_revision = "20260813_ix_incident_idem"
branch_labels = None
depends_on = None

_LEAVE = "t_internship_leave"
_MAKEUP = "t_internship_makeup"
_LEAVE_COL = "active_pending_internship_id"
_MAKEUP_COL = "active_pending_internship_id"
_LEAVE_UK = "uk_ix_leave_active_pending"
_MAKEUP_UK = "uk_ix_makeup_active_pending"


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _scan_duplicates(bind, table: str, extra_cols: str = "") -> list:
    """升级前扫描已经违反不变量的历史数据。

    有重复就必须停下来让人处理：这些是学生真实提交的申请，删哪条是学校的决定，
    不是迁移脚本能替他们做的。
    """
    group_by = f"tenant_id, internship_id{(', ' + extra_cols) if extra_cols else ''}"
    rows = bind.execute(sa.text(f"""
        SELECT {group_by}, COUNT(*) AS c
        FROM {table}
        WHERE is_deleted = 0 AND status = 'PENDING'
        GROUP BY {group_by}
        HAVING c > 1
        LIMIT 50
    """)).fetchall()
    return list(rows)


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()

    if _LEAVE in tables:
        dups = _scan_duplicates(bind, _LEAVE)
        if dups:
            raise RuntimeError(
                f"{_LEAVE} 已存在同一实习记录多条 PENDING 请假，唯一索引无法建立。"
                f"这些是学生真实提交的申请，请先由学校决定保留哪条再重跑迁移。"
                f"冲突分组（最多列出 50 组）：{dups}")
        if _LEAVE_COL not in _columns(_LEAVE):
            op.execute(sa.text(f"""
                ALTER TABLE {_LEAVE}
                ADD COLUMN {_LEAVE_COL} BIGINT
                GENERATED ALWAYS AS (
                    CASE WHEN is_deleted = 0 AND status = 'PENDING'
                         THEN internship_id ELSE NULL END
                ) STORED
                COMMENT '仅待审批时等于 internship_id，用于唯一索引；其余为 NULL'
            """))
        if _LEAVE_UK not in _indexes(_LEAVE):
            op.create_index(_LEAVE_UK, _LEAVE, ["tenant_id", _LEAVE_COL], unique=True)

    if _MAKEUP in tables:
        dups = _scan_duplicates(bind, _MAKEUP, extra_cols="checkin_date")
        if dups:
            raise RuntimeError(
                f"{_MAKEUP} 已存在同一实习记录同一天多条 PENDING 补卡，唯一索引无法建立。"
                f"请先由学校决定保留哪条再重跑迁移。"
                f"冲突分组（最多列出 50 组）：{dups}")
        if _MAKEUP_COL not in _columns(_MAKEUP):
            op.execute(sa.text(f"""
                ALTER TABLE {_MAKEUP}
                ADD COLUMN {_MAKEUP_COL} BIGINT
                GENERATED ALWAYS AS (
                    CASE WHEN is_deleted = 0 AND status = 'PENDING'
                         THEN internship_id ELSE NULL END
                ) STORED
                COMMENT '仅待审核时等于 internship_id，用于唯一索引；其余为 NULL'
            """))
        if _MAKEUP_UK not in _indexes(_MAKEUP):
            # 补卡按天去重，所以唯一键要带上 checkin_date。
            op.create_index(_MAKEUP_UK, _MAKEUP,
                            ["tenant_id", _MAKEUP_COL, "checkin_date"], unique=True)


def downgrade() -> None:
    tables = _tables()
    if _MAKEUP in tables:
        if _MAKEUP_UK in _indexes(_MAKEUP):
            op.drop_index(_MAKEUP_UK, table_name=_MAKEUP)
        if _MAKEUP_COL in _columns(_MAKEUP):
            op.drop_column(_MAKEUP, _MAKEUP_COL)
    if _LEAVE in tables:
        if _LEAVE_UK in _indexes(_LEAVE):
            op.drop_index(_LEAVE_UK, table_name=_LEAVE)
        if _LEAVE_COL in _columns(_LEAVE):
            op.drop_column(_LEAVE, _LEAVE_COL)
