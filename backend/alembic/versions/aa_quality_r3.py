"""教学质量 R3 续工：建 2 表（问题记录 t_aa_quality_record + 整改任务 t_aa_quality_rectification）。

覆盖三级卡 01 督导听课 / 02 巡课记录 / 03 教学检查 / 04 教学事故（共用 t_aa_quality_record，
record_type 判别）与 05 质量整改 / 06 整改跟进（共用 t_aa_quality_rectification，同一任务表两个
前端视角）。09 质量归档不新建表，读侧聚合以上两表。全新业务表，downgrade 逆序 drop。

Revision ID: aa_quality_r3
Revises: aa_course_lib_tier1_r2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_quality_r3"
down_revision = "aa_course_lib_tier1_r2"
branch_labels = None
depends_on = None

_COMMON = [
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by", sa.BigInteger()),
    sa.Column("updated_by", sa.BigInteger()),
    sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
]


def _pk_tenant():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
    ]


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_quality_record"):
        op.create_table(
            "t_aa_quality_record", *_pk_tenant(),
            sa.Column("record_type", sa.String(20), nullable=False, comment="SUPERVISION/PATROL/INSPECTION/INCIDENT"),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("major_id", sa.BigInteger()),
            sa.Column("class_id", sa.BigInteger()),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("course_id", sa.BigInteger()),
            sa.Column("course_name", sa.String(200)),
            sa.Column("occurred_at", sa.DateTime()),
            sa.Column("location", sa.String(200)),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("category", sa.String(50)),
            sa.Column("score", sa.Numeric(5, 2)),
            sa.Column("conclusion", sa.String(50)),
            sa.Column("description", sa.Text()),
            sa.Column("handling_note", sa.Text()),
            sa.Column("need_rectify", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("recorder_key", sa.String(100)),
            sa.Column("recorder_name", sa.String(100)),
            sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"),
            sa.Column("confirmed_at", sa.DateTime()),
            sa.Column("confirmed_by_name", sa.String(100)),
            *_COMMON)
        op.create_index("ix_aa_qrec_type", "t_aa_quality_record", ["tenant_id", "record_type", "status"])
        op.create_index("ix_aa_qrec_term", "t_aa_quality_record", ["tenant_id", "term_id"])
        op.create_index("ix_aa_qrec_college", "t_aa_quality_record", ["tenant_id", "college_id"])
        op.create_index("ix_aa_qrec_teacher", "t_aa_quality_record", ["tenant_id", "teacher_key"])

    if not _has(bind, "t_aa_quality_rectification"):
        op.create_table(
            "t_aa_quality_rectification", *_pk_tenant(),
            sa.Column("source_record_id", sa.BigInteger()),
            sa.Column("source_type", sa.String(20)),
            sa.Column("source_title", sa.String(200)),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("major_id", sa.BigInteger()),
            sa.Column("class_id", sa.BigInteger()),
            sa.Column("requirement", sa.Text(), nullable=False),
            sa.Column("deadline", sa.DateTime()),
            sa.Column("responsible_key", sa.String(100)),
            sa.Column("responsible_name", sa.String(100)),
            sa.Column("initiator_key", sa.String(100)),
            sa.Column("initiator_name", sa.String(100)),
            sa.Column("progress_log_json", sa.Text()),
            sa.Column("result_note", sa.Text()),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("closed_at", sa.DateTime()),
            *_COMMON)
        op.create_index("ix_aa_qrect_status", "t_aa_quality_rectification", ["tenant_id", "status"])
        op.create_index("ix_aa_qrect_source", "t_aa_quality_rectification", ["tenant_id", "source_record_id"])
        op.create_index("ix_aa_qrect_deadline", "t_aa_quality_rectification", ["tenant_id", "deadline"])
        op.create_index("ix_aa_qrect_term", "t_aa_quality_rectification", ["tenant_id", "term_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_quality_rectification", "t_aa_quality_record"):
        if _has(bind, t):
            op.drop_table(t)
