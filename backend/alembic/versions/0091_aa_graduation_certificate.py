"""毕业/结业证书台账表。

对标商业教务系统（强智《智慧教学服务平台操作手册》7-7 毕业证书管理，印刷页 514-517：
证书编号规则+电子注册号自动编号+批量证书生成+台账）。

全新业务表；downgrade drop。幂等：inspect 判表。

Revision ID: 0091_aa_graduation_certificate
Revises: 0090_aa_grade_recognition
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0091_aa_graduation_certificate"
down_revision = "0090_aa_grade_recognition"
branch_labels = None
depends_on = None

TABLE = "t_aa_graduation_certificate"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("student_no", sa.String(50)),
        sa.Column("student_name", sa.String(100)),
        sa.Column("audit_batch_id", sa.BigInteger()),
        sa.Column("cert_type", sa.String(20), nullable=False, server_default="GRADUATION"),
        sa.Column("cert_no", sa.String(50), nullable=False),
        sa.Column("e_reg_no", sa.String(50)),
        sa.Column("issue_year", sa.String(10)),
        sa.Column("issue_date", sa.String(20)),
        sa.Column("major_name", sa.String(200)),
        sa.Column("void_reason", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="GENERATED"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "cert_no", name="uk_aa_grad_cert_no"))
    op.create_index("ix_aa_grad_cert_student", TABLE, ["student_id"])
    op.create_index("ix_aa_grad_cert_batch", TABLE, ["audit_batch_id"])
    op.create_index("ix_aa_grad_cert_status", TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        op.drop_table(TABLE)
