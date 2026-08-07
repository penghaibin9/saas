"""包 1：成绩更正统一命令表，更正链来源泛化到复查与教师发起两条入口。

Revision ID: 20260806_aa_pkg1_change
Revises: 20260806_aa_pkg2_policy
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20260806_aa_pkg1_change"
down_revision = "20260806_aa_pkg2_policy"
branch_labels = None
depends_on = None

# alembic_version.version_num 的正式合同为 VARCHAR(32)，迁移 ID 必须稳定落入该边界。
assert len(revision) <= 32

_REQUEST = "t_aa_grade_change_request"
_CORRECTION = "t_aa_grade_correction"
_GRADE = "t_acad_grade"
_UK_RECHECK = "uk_aa_grade_correction_recheck"
_UK_SOURCE = "uk_aa_grade_correction_source"
_UK_GRADE_RECORD = "uk_acad_grade_source_record"
_UK_GRADE_ACTIVE = "uk_acad_grade_active_record"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260806_aa_pkg1_change requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if _REQUEST not in tables:
        op.create_table(
            _REQUEST,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("grade_task_id", sa.BigInteger(), nullable=False),
            sa.Column("grade_record_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(length=20), nullable=False, server_default="CHANGE_REQUEST"),
            sa.Column("proposed_usual_score", sa.Integer(), nullable=True),
            sa.Column("proposed_midterm_score", sa.Integer(), nullable=True),
            sa.Column("proposed_final_score", sa.Integer(), nullable=True),
            sa.Column("proposed_total_score", sa.Integer(), nullable=True),
            sa.Column("proposed_pass_status", sa.String(length=20), nullable=True),
            sa.Column("before_usual_score", sa.Integer(), nullable=True),
            sa.Column("before_midterm_score", sa.Integer(), nullable=True),
            sa.Column("before_final_score", sa.Integer(), nullable=True),
            sa.Column("before_total_score", sa.Integer(), nullable=True),
            sa.Column("current_grade_id", sa.BigInteger(), nullable=True),
            sa.Column("expected_grade_version", sa.Integer(), nullable=True),
            sa.Column("reason", sa.String(length=500), nullable=False),
            sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
            sa.Column("current_task_id", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("decided_by", sa.String(length=100), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.PrimaryKeyConstraint("id", name="pk_t_aa_grade_change_request"),
        )
        op.create_index("ix_aa_grade_change_request_record", _REQUEST,
                        ["tenant_id", "grade_record_id", "status"], unique=False)
        op.create_index("ix_aa_grade_change_request_instance", _REQUEST,
                        ["tenant_id", "workflow_instance_id"], unique=False)

    if _CORRECTION in tables:
        columns = {row["name"] for row in inspect(bind).get_columns(_CORRECTION)}
        if "source_type" not in columns:
            op.add_column(_CORRECTION, sa.Column(
                "source_type", sa.String(length=20), nullable=False, server_default="RECHECK",
                comment="RECHECK/CHANGE_REQUEST"))
        if "source_ref_id" not in columns:
            op.add_column(_CORRECTION, sa.Column(
                "source_ref_id", sa.BigInteger(), nullable=True, comment="来源单据ID"))
        # 存量行全部来自成绩复查：来源类型 RECHECK，来源单据即原 recheck_id。
        bind.execute(text(
            f"UPDATE {_CORRECTION} SET source_type = 'RECHECK', source_ref_id = recheck_id "
            "WHERE source_ref_id IS NULL"
        ))
        op.alter_column(_CORRECTION, "source_ref_id", existing_type=sa.BigInteger(), nullable=False)
        # 教师发起的更正没有复查单，recheck_id 必须允许为空。
        op.alter_column(_CORRECTION, "recheck_id", existing_type=sa.BigInteger(), nullable=True)

        existing = ({row["name"] for row in inspect(bind).get_indexes(_CORRECTION)}
                    | {row["name"] for row in inspect(bind).get_unique_constraints(_CORRECTION)})
        if _UK_RECHECK in existing:
            op.drop_constraint(_UK_RECHECK, _CORRECTION, type_="unique")
        if _UK_SOURCE not in existing:
            op.create_unique_constraint(_UK_SOURCE, _CORRECTION,
                                        ["tenant_id", "source_type", "source_ref_id"])

    if _GRADE in tables:
        columns = {row["name"] for row in inspect(bind).get_columns(_GRADE)}
        if "active_record_key" not in columns:
            op.add_column(_GRADE, sa.Column(
                "active_record_key", sa.BigInteger(), nullable=True,
                comment="ACTIVE 版本的 grade_record_id；非 ACTIVE 版本为 NULL"))
        bind.execute(text(
            f"UPDATE {_GRADE} SET active_record_key = "
            "CASE WHEN record_status = 'ACTIVE' THEN grade_record_id ELSE NULL END"
        ))
        existing = ({row["name"] for row in inspect(bind).get_indexes(_GRADE)}
                    | {row["name"] for row in inspect(bind).get_unique_constraints(_GRADE)})
        if _UK_GRADE_RECORD in existing:
            # 旧合同 UNIQUE(tenant_id, grade_record_id) 只允许一个成绩明细存在一条正式成绩，
            # 追加式更正链（原行 SUPERSEDED + 新行 ACTIVE）在它面前必然撞键，必须换成只约束有效版本。
            op.drop_constraint(_UK_GRADE_RECORD, _GRADE, type_="unique")
        if _UK_GRADE_ACTIVE not in existing:
            op.create_unique_constraint(_UK_GRADE_ACTIVE, _GRADE, ["tenant_id", "active_record_key"])


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if _GRADE in tables:
        existing = ({row["name"] for row in inspect(bind).get_indexes(_GRADE)}
                    | {row["name"] for row in inspect(bind).get_unique_constraints(_GRADE)})
        if _UK_GRADE_ACTIVE in existing:
            op.drop_constraint(_UK_GRADE_ACTIVE, _GRADE, type_="unique")
        # 回滚回"一个成绩明细一条正式成绩"的旧合同前，必须先删掉历史版本行，否则唯一键建不起来。
        bind.execute(text(
            f"DELETE FROM {_GRADE} WHERE record_status <> 'ACTIVE' AND grade_record_id IS NOT NULL"))
        if _UK_GRADE_RECORD not in existing:
            op.create_unique_constraint(_UK_GRADE_RECORD, _GRADE, ["tenant_id", "grade_record_id"])
        columns = {row["name"] for row in inspect(bind).get_columns(_GRADE)}
        if "active_record_key" in columns:
            op.drop_column(_GRADE, "active_record_key")

    if _CORRECTION in tables:
        existing = ({row["name"] for row in inspect(bind).get_indexes(_CORRECTION)}
                    | {row["name"] for row in inspect(bind).get_unique_constraints(_CORRECTION)})
        if _UK_SOURCE in existing:
            op.drop_constraint(_UK_SOURCE, _CORRECTION, type_="unique")
        # 回滚前必须先清掉没有复查来源的更正行，否则旧的非空+唯一约束建不起来。
        bind.execute(text(f"DELETE FROM {_CORRECTION} WHERE recheck_id IS NULL"))
        op.alter_column(_CORRECTION, "recheck_id", existing_type=sa.BigInteger(), nullable=False)
        if _UK_RECHECK not in existing:
            op.create_unique_constraint(_UK_RECHECK, _CORRECTION, ["tenant_id", "recheck_id"])
        columns = {row["name"] for row in inspect(bind).get_columns(_CORRECTION)}
        if "source_ref_id" in columns:
            op.drop_column(_CORRECTION, "source_ref_id")
        if "source_type" in columns:
            op.drop_column(_CORRECTION, "source_type")

    if _REQUEST in tables:
        op.drop_index("ix_aa_grade_change_request_instance", table_name=_REQUEST)
        op.drop_index("ix_aa_grade_change_request_record", table_name=_REQUEST)
        op.drop_table(_REQUEST)
