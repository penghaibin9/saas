"""特殊备案：补齐 service 一直在读写、但表里从来没有的申请人/审核人四列

Revision ID: 20260814_ix_filing_actor_cols
Revises: 20260814_ix_leave_makeup_active
Create Date: 2026-08-14

`internship_special_filing_service.create()` 用
`requested_by_name=` / `requested_by_user_id=` 构造 `InternshipSpecialFiling`，
`review()` 又写 `reviewed_by_name` / `reviewed_at`。
但这四列在 ORM 模型和真实表里**都不存在**（已用 information_schema 核对
t_internship_special_filing 的 33 列）。后果：

1. `POST /internship/filings` 100% 抛 `TypeError: 'requested_by_name' is an
   invalid keyword argument`，也就是 500——特殊备案根本建不出来；
2. `review()` 里「申请人与审核人必须分离」的守卫读 `row.requested_by_user_id`，
   会 AttributeError；
（合规工作台的备案列表不读这几列，逐行核对过；会炸的是上面两处。）

这个缺陷会自我掩盖：创建永远失败 → 表里永远 0 行 → 第 2 处永远轮不到执行，
于是既有测试和人工点验都发现不了。是本批次「剩余实体首次创建并发实测」在写串行
基线用例时撞出来的。

为什么是补列而不是删代码：这四列是**被设计用来承载责任人的**，其中
`requested_by_user_id` 还撑着一条职责分离的安全守卫（申请人不能自己审批）。
把 service 里的引用删掉能让接口不报错，但会静默去掉那条守卫，并让责任人永远显示
不出申请人/审核人——那是把功能缺陷改成合规缺陷，不是修复。

四列全部可空：历史行（当前 0 行，但其它环境可能有）不需要回填，也没有默认值可编。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_ix_filing_actor_cols"
down_revision = "20260814_ix_leave_makeup_active"
branch_labels = None
depends_on = None

_TABLE = "t_internship_special_filing"

# 列名 → 建表定义。顺序与 ORM 模型一致，便于对照。
_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("requested_by_name",
     sa.Column("requested_by_name", sa.String(100), nullable=True,
               comment="申请人姓名（工作台展示）")),
    ("requested_by_user_id",
     sa.Column("requested_by_user_id", sa.String(64), nullable=True,
               comment="申请人用户ID；review() 据此拒绝申请人自审")),
    ("reviewed_by_name",
     sa.Column("reviewed_by_name", sa.String(100), nullable=True,
               comment="最近一次审核人姓名")),
    ("reviewed_at",
     sa.Column("reviewed_at", sa.DateTime(), nullable=True,
               comment="最近一次审核时间")),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def upgrade() -> None:
    if _TABLE not in _tables():
        # 表由 0131 创建；跑在更早基线上时本迁移无事可做，不应报错。
        return
    existing = _columns()
    for name, column in _COLUMNS:
        if name not in existing:
            op.add_column(_TABLE, column)


def downgrade() -> None:
    if _TABLE not in _tables():
        return
    existing = _columns()
    # 逆序删除，与 upgrade 对称。
    for name, _ in reversed(_COLUMNS):
        if name in existing:
            op.drop_column(_TABLE, name)
