"""13B-R3 学院专业班级：组织三表加列（t_college/t_major/t_class），不建新表。

融合设计 §加列表：
- t_college += short_name / sort_order / secretary_id
- t_major   += education_years(默3) / training_level / enroll_status / direction
- t_class   += class_code / capacity / graduate_year / class_status

全部 nullable 或带 server_default，历史数据零回填即可升级；downgrade 逐列可逆。
幂等：inspect 判列存在再增/删，重复执行不报错。

Revision ID: 0069_13b_r3_orgs
Revises: 0068_13b_r1_grade_review
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0069_13b_r3_orgs"
# 并行波次：本模块与其它 R* 模块同指 R1(0068)，由总控在合并期重新串成单链。
down_revision = "0068_13b_r1_grade_review"
branch_labels = None
depends_on = None


# 表 → [(列名, 列类型工厂, server_default)]
_ADDS: dict[str, list[tuple[str, "callable", str | None]]] = {
    "t_college": [
        ("short_name", lambda: sa.String(length=100), None),
        ("sort_order", lambda: sa.Integer(), "0"),
        ("secretary_id", lambda: sa.BigInteger(), None),
    ],
    "t_major": [
        ("education_years", lambda: sa.Integer(), "3"),
        ("training_level", lambda: sa.String(length=50), None),
        ("enroll_status", lambda: sa.String(length=50), "'ENROLLING'"),
        ("direction", lambda: sa.String(length=200), None),
    ],
    "t_class": [
        ("class_code", lambda: sa.String(length=50), None),
        ("capacity", lambda: sa.Integer(), None),
        ("graduate_year", lambda: sa.String(length=20), None),
        ("class_status", lambda: sa.String(length=50), "'NORMAL'"),
    ],
}


def _cols(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for table, cols in _ADDS.items():
        existing = _cols(bind, table)
        if not existing:  # 表尚未建（异常基线）→ 跳过，交由建表迁移
            continue
        for name, type_factory, default in cols:
            if name in existing:
                continue
            kwargs = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = sa.text(default)
            op.add_column(table, sa.Column(name, type_factory(), **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    for table, cols in _ADDS.items():
        existing = _cols(bind, table)
        for name, _type_factory, _default in cols:
            if name in existing:
                op.drop_column(table, name)
