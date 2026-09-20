"""手机号登录绑定基础模型与凭据安全版本。

Revision ID: 20260910_phone_login_foundation
Revises: 20260910_merge_academic_affairs_main
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260910_phone_login_foundation"
down_revision = "20260910_merge_academic_affairs_main"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    user_columns = {c["name"] for c in inspector.get_columns("t_user")}
    if "credential_version" not in user_columns:
        op.add_column("t_user", sa.Column("credential_version", sa.BigInteger(), nullable=False, server_default="0"))
    tables = set(inspector.get_table_names())
    if "t_user_phone_login_binding" not in tables:
        op.create_table("t_user_phone_login_binding",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False), sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("state", sa.String(20), nullable=False, server_default="UNBOUND"),
            sa.Column("phone_ciphertext", sa.String(500)), sa.Column("active_phone_lookup", sa.String(64)),
            sa.Column("lookup_key_id", sa.String(32)), sa.Column("verified_at", sa.DateTime()), sa.Column("revoked_at", sa.DateTime()),
            sa.Column("source_candidate_id", sa.BigInteger()), sa.Column("source_job_id", sa.BigInteger()), sa.Column("verification_method", sa.String(64)),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "user_id", name="uk_phone_login_binding_user"),
            sa.UniqueConstraint("tenant_id", "active_phone_lookup", name="uk_phone_login_binding_active_lookup"),
            sa.CheckConstraint("version >= 0", name="ck_phone_binding_version"),
            sa.CheckConstraint("(state = 'VERIFIED' AND active_phone_lookup IS NOT NULL AND phone_ciphertext IS NOT NULL) OR (state IN ('UNBOUND', 'REVOKED') AND active_phone_lookup IS NULL AND phone_ciphertext IS NULL)", name="ck_phone_binding_state"),
        )
        op.create_index("ix_phone_login_binding_lookup", "t_user_phone_login_binding", ["tenant_id", "active_phone_lookup"])
        op.create_index("ix_t_user_phone_login_binding_tenant_id", "t_user_phone_login_binding", ["tenant_id"])
        op.create_index("ix_t_user_phone_login_binding_user_id", "t_user_phone_login_binding", ["user_id"])
    if "t_user_phone_login_candidate" not in tables:
        op.create_table("t_user_phone_login_candidate",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False), sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("candidate_phone_ciphertext", sa.String(500)), sa.Column("candidate_lookup", sa.String(64)),
            sa.Column("owner_type", sa.String(20), nullable=False, server_default="SELF"), sa.Column("state", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("source_kind", sa.String(40)), sa.Column("source_job_id", sa.BigInteger()), sa.Column("source_row_no", sa.BigInteger()),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "user_id", name="uk_phone_login_candidate_user"),
            sa.CheckConstraint("version >= 0", name="ck_phone_candidate_version"),
            sa.CheckConstraint("state IN ('PENDING', 'CONFLICT', 'APPLIED', 'CLEARED')", name="ck_phone_candidate_state"),
            sa.CheckConstraint("owner_type = 'SELF'", name="ck_phone_candidate_owner"),
        )
        op.create_index("ix_t_user_phone_login_candidate_candidate_lookup", "t_user_phone_login_candidate", ["candidate_lookup"])
        op.create_index("ix_t_user_phone_login_candidate_tenant_id", "t_user_phone_login_candidate", ["tenant_id"])
        op.create_index("ix_t_user_phone_login_candidate_user_id", "t_user_phone_login_candidate", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for table in ("t_user_phone_login_binding", "t_user_phone_login_candidate"):
        if table in tables and bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Phone history exists; preserve records and use a forward migration.")
    if "credential_version" in {c["name"] for c in inspect(bind).get_columns("t_user")}:
        if bind.execute(sa.text("SELECT EXISTS(SELECT 1 FROM t_user WHERE credential_version <> 0)")).scalar():
            raise RuntimeError("Credential epochs exist; downgrade would reactivate revoked credentials.")
    if "t_user_phone_login_candidate" in tables:
        op.drop_table("t_user_phone_login_candidate")
    if "t_user_phone_login_binding" in tables:
        op.drop_table("t_user_phone_login_binding")
    if "credential_version" in {c["name"] for c in inspect(bind).get_columns("t_user")}:
        op.drop_column("t_user", "credential_version")
