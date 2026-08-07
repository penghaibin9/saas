"""P0-N02：正式成绩修读次数唯一分配点（成绩身份头）。

修读次数原来靠 ``MAX(attempt_no) + 1`` 现算，没有互斥：两个事务同时读到 MAX=0 就各自返回 1。
正常发布、成绩认定、免修、补考、清考、重修都会写正式成绩，任意两条路径并发就能给同一个学生
同一门课造出两条 attempt_no 相同且都 PASSED 的正式事实——(source_biz_type, source_biz_id)
唯一键拦不住，因为两条来源本来就不同。

本迁移把「这个学生这门课修读到第几次」落成一行可加锁的权威计数器。

存量回填：按现有正式成绩的 (acad_student_id, course_code) 分组取 MAX(attempt_no) 建头，
让已有历史数据直接进入新序列，不重号也不跳号。attempt_no 为 NULL 的历史行不参与
（它们属于既有身份欠账，由 grade_identity_debt 单独报告，不在这里猜测回填）。

Revision ID: 20260807_aa_grade_head
Revises: 20260807_aa_exempt_ev
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260807_aa_grade_head"
down_revision = "20260807_aa_exempt_ev"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_HEAD = "t_aa_grade_identity_head"
_GRADE = "t_acad_grade"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, _HEAD):
        op.create_table(
            _HEAD,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("acad_student_id", sa.BigInteger(), nullable=False),
            sa.Column("course_code", sa.String(50), nullable=False),
            sa.Column("current_attempt_no", sa.Integer(), nullable=False, server_default="0",
                      comment="已分配到的最大修读次数；0 表示尚未分配"),
            sa.Column("last_source_biz_type", sa.String(50), nullable=True,
                      comment="最近一次分配的来源业务类型，便于追溯"),
            sa.Column("last_allocated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.UniqueConstraint("tenant_id", "acad_student_id", "course_code",
                                name="uk_aa_grade_identity_head"),
        )
        op.create_index("ix_aa_grade_head_student", _HEAD, ["acad_student_id"])
        op.create_index("ix_aa_grade_head_course", _HEAD, ["course_code"])

    if _has_table(bind, _GRADE):
        bind.execute(sa.text(
            f"INSERT INTO {_HEAD} "
            f"(tenant_id, acad_student_id, course_code, current_attempt_no, is_deleted) "
            f"SELECT tenant_id, acad_student_id, course_code, MAX(attempt_no), 0 "
            f"FROM {_GRADE} "
            f"WHERE attempt_no IS NOT NULL AND course_code IS NOT NULL AND course_code <> '' "
            f"AND is_deleted = 0 "
            f"GROUP BY tenant_id, acad_student_id, course_code "
            f"ON DUPLICATE KEY UPDATE "
            f"current_attempt_no = GREATEST({_HEAD}.current_attempt_no, VALUES(current_attempt_no))"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _HEAD):
        op.drop_table(_HEAD)
