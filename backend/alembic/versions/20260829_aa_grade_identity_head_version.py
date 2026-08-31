"""add grade identity head optimistic-lock version

Revision ID: 20260829_aa_grade_head_ver
Revises: 20260829_affairs_sandbox_merge
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_aa_grade_head_ver"
down_revision = "20260829_affairs_sandbox_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand phase: keep a server default so the previous release can still
    # insert grade-identity rows after an application rollback. Removing the
    # default belongs to a later contract migration once N-1 is retired.
    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("t_aa_grade_identity_head")
    }
    existing = columns.get("version")
    if existing is None:
        op.add_column(
            "t_aa_grade_identity_head",
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
                comment="乐观锁",
            ),
        )
        return

    # MySQL DDL is non-transactional. A prior interrupted/manual rollout can
    # leave the expand column present while alembic_version is still behind.
    # Accept only the exact compatible shape; never stamp over an incompatible
    # column and never silently weaken the optimistic-lock contract.
    default = str(existing.get("default") or "").strip("'\"")
    compatible = (
        isinstance(existing.get("type"), sa.Integer)
        and existing.get("nullable") is False
        and default == "0"
    )
    if not compatible:
        raise RuntimeError(
            "existing t_aa_grade_identity_head.version is incompatible with "
            "20260829_aa_grade_head_ver"
        )
    if existing.get("comment") != "乐观锁":
        op.alter_column(
            "t_aa_grade_identity_head",
            "version",
            existing_type=sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="乐观锁",
        )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("t_aa_grade_identity_head")
    }
    if "version" in columns:
        op.drop_column("t_aa_grade_identity_head", "version")
