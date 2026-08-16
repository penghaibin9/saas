"""E integration M8: add rollback-compatible campaign scope to formal applications.

Revision ID: 20260816_internship_e_m8
Revises: 20260815_internship_e_m7

N-1 compatibility is deliberate:
- historical / legacy writers keep using record_id and the existing unique constraint unchanged;
- V3 campaign rows use campaign_record_id while physical record_id stays NULL;
- the ORM exposes a logical record_id as COALESCE(record_id, campaign_record_id).

This lets multiple recruitment rounds coexist without making the previous release understand
campaign-scoped rows during an application rollback.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260816_internship_e_m8"
down_revision = "20260815_internship_e_m7"
branch_labels = None
depends_on = None

_TABLE = "t_internship_application"
_OLD_UK = "uk_intern_application_record_volunteer"
_CAMPAIGN_UK = "uk_intern_application_campaign_record_volunteer"
_CAMPAIGN_IX = "ix_t_internship_application_campaign_id"
_CAMPAIGN_RECORD_IX = "ix_t_internship_application_campaign_record_id"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260816_internship_e_m8 requires MySQL")


def _columns() -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(_TABLE)}


def _indexes() -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(_TABLE)}


def _unique_names() -> set[str]:
    insp = inspect(op.get_bind())
    names = {item["name"] for item in insp.get_unique_constraints(_TABLE) if item.get("name")}
    names.update(index["name"] for index in insp.get_indexes(_TABLE) if index.get("unique"))
    return names


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    if not inspect(bind).has_table(_TABLE):
        raise RuntimeError("t_internship_application must exist before internship E M8")

    columns = _columns()
    if "campaign_id" not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                "campaign_id",
                sa.BigInteger(),
                nullable=True,
                comment="→ t_internship_recruitment_campaign.id; NULL for legacy/self-arranged",
            ),
        )
    if "campaign_record_id" not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                "campaign_record_id",
                sa.BigInteger(),
                nullable=True,
                comment="→ t_internship_record.id; V3 campaign namespace only",
            ),
        )

    # Expand only: old binaries continue to require/populate physical record_id. Relaxing
    # NOT NULL is backward compatible; no existing row is rewritten into the V3 namespace.
    record = next(column for column in inspect(bind).get_columns(_TABLE) if column["name"] == "record_id")
    if not record.get("nullable"):
        op.alter_column(
            _TABLE,
            "record_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )

    unique_names = _unique_names()
    if _OLD_UK not in unique_names:
        raise RuntimeError(
            "legacy application uniqueness must remain present during M8 expand phase"
        )
    if _CAMPAIGN_UK not in unique_names:
        op.create_unique_constraint(
            _CAMPAIGN_UK,
            _TABLE,
            ["tenant_id", "campaign_record_id", "campaign_id", "volunteer_no"],
        )
    if _CAMPAIGN_IX not in _indexes():
        op.create_index(_CAMPAIGN_IX, _TABLE, ["campaign_id"])
    if _CAMPAIGN_RECORD_IX not in _indexes():
        op.create_index(_CAMPAIGN_RECORD_IX, _TABLE, ["campaign_record_id"])


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    if not inspect(bind).has_table(_TABLE):
        return

    columns = _columns()
    if "campaign_record_id" in columns:
        # N-1 schema can represent only one row per record/slot. Refuse destructive rollback once
        # multiple campaign rounds have used the same canonical record/slot.
        duplicate = bind.execute(sa.text("""
            SELECT tenant_id, campaign_record_id, volunteer_no, COUNT(*) AS row_count
            FROM t_internship_application
            WHERE campaign_record_id IS NOT NULL
            GROUP BY tenant_id, campaign_record_id, volunteer_no
            HAVING COUNT(*) > 1
            LIMIT 1
        """)).first()
        if duplicate:
            raise RuntimeError(
                "cannot downgrade internship E M8 after multiple campaign rounds exist for one record/slot"
            )

        # For a safe downgrade, project the single campaign row back into the legacy physical key.
        bind.execute(sa.text("""
            UPDATE t_internship_application
            SET record_id = campaign_record_id
            WHERE record_id IS NULL
              AND campaign_record_id IS NOT NULL
        """))

    unique_names = _unique_names()
    if _CAMPAIGN_UK in unique_names:
        op.drop_constraint(_CAMPAIGN_UK, _TABLE, type_="unique")
    if _CAMPAIGN_RECORD_IX in _indexes():
        op.drop_index(_CAMPAIGN_RECORD_IX, table_name=_TABLE)
    if _CAMPAIGN_IX in _indexes():
        op.drop_index(_CAMPAIGN_IX, table_name=_TABLE)

    columns = _columns()
    if "campaign_record_id" in columns:
        op.drop_column(_TABLE, "campaign_record_id")
    columns = _columns()
    if "campaign_id" in columns:
        op.drop_column(_TABLE, "campaign_id")

    # All surviving rows now have the legacy key again.
    record = next(column for column in inspect(bind).get_columns(_TABLE) if column["name"] == "record_id")
    if record.get("nullable"):
        op.alter_column(
            _TABLE,
            "record_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
