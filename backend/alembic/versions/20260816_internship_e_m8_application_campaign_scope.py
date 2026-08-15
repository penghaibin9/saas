"""E integration M8: scope formal POSITION applications to recruitment campaign.

Revision ID: 20260816_internship_e_m8
Revises: 20260815_internship_e_m7

The legacy application ledger historically allowed one row per record/volunteer slot. V3 can run
multiple recruitment rounds against the same InternshipRecord, so canonical POSITION slots need an
explicit campaign discriminator. Existing immutable snapshots are the primary backfill authority;
remaining draft rows are backfilled only when their campaign-owned position and volunteer group
agree. Legacy/self-arranged rows intentionally remain campaign_id=NULL.
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
_CAMPAIGN_UK = "uk_intern_application_record_campaign_volunteer"
_LEGACY_UK = "uk_intern_application_legacy_record_volunteer"
_CAMPAIGN_IX = "ix_t_internship_application_campaign_id"


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

    # Immutable submitted material is the strongest campaign authority.
    op.execute(sa.text("""
        UPDATE t_internship_application AS a
        INNER JOIN t_internship_application_material_snapshot AS s
          ON s.id = a.material_snapshot_id
         AND s.tenant_id = a.tenant_id
        SET a.campaign_id = s.campaign_id
        WHERE a.campaign_id IS NULL
          AND a.application_type = 'POSITION'
          AND a.material_snapshot_id IS NOT NULL
    """))

    # Draft / withdrawn V3 rows have no snapshot yet. Backfill only when the position's campaign
    # and the record's volunteer-group campaign are the same fact; otherwise leave NULL fail-safe.
    op.execute(sa.text("""
        UPDATE t_internship_application AS a
        INNER JOIN t_internship_position AS p
          ON p.id = a.position_id
         AND p.tenant_id = a.tenant_id
         AND p.is_deleted = 0
        INNER JOIN t_internship_volunteer_group AS g
          ON g.tenant_id = a.tenant_id
         AND g.record_id = a.record_id
         AND g.campaign_id = p.campaign_id
         AND g.is_deleted = 0
        SET a.campaign_id = p.campaign_id
        WHERE a.campaign_id IS NULL
          AND a.application_type = 'POSITION'
          AND p.campaign_id IS NOT NULL
    """))

    columns = _columns()
    if "legacy_record_id" not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                "legacy_record_id",
                sa.BigInteger(),
                sa.Computed("CASE WHEN campaign_id IS NULL THEN record_id ELSE NULL END", persisted=True),
                nullable=True,
                comment="legacy NULL-campaign uniqueness key",
            ),
        )

    unique_names = _unique_names()
    if _OLD_UK in unique_names:
        op.drop_constraint(_OLD_UK, _TABLE, type_="unique")
        unique_names.discard(_OLD_UK)
    if _CAMPAIGN_UK not in unique_names:
        op.create_unique_constraint(
            _CAMPAIGN_UK,
            _TABLE,
            ["tenant_id", "record_id", "campaign_id", "volunteer_no"],
        )
    unique_names = _unique_names()
    if _LEGACY_UK not in unique_names:
        op.create_unique_constraint(
            _LEGACY_UK,
            _TABLE,
            ["tenant_id", "legacy_record_id", "volunteer_no"],
        )
    if _CAMPAIGN_IX not in _indexes():
        op.create_index(_CAMPAIGN_IX, _TABLE, ["campaign_id"])


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    if not inspect(bind).has_table(_TABLE):
        return

    # The N-1 constraint cannot represent two rounds for the same record/slot. Refuse a destructive
    # rollback instead of silently deleting or coalescing immutable application history.
    duplicate = bind.execute(sa.text("""
        SELECT tenant_id, record_id, volunteer_no, COUNT(*) AS row_count
        FROM t_internship_application
        GROUP BY tenant_id, record_id, volunteer_no
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if duplicate:
        raise RuntimeError(
            "cannot downgrade internship E M8 after multiple campaign rounds exist for one record/slot"
        )

    unique_names = _unique_names()
    if _CAMPAIGN_UK in unique_names:
        op.drop_constraint(_CAMPAIGN_UK, _TABLE, type_="unique")
    unique_names = _unique_names()
    if _LEGACY_UK in unique_names:
        op.drop_constraint(_LEGACY_UK, _TABLE, type_="unique")
    if _OLD_UK not in _unique_names():
        op.create_unique_constraint(
            _OLD_UK,
            _TABLE,
            ["tenant_id", "record_id", "volunteer_no"],
        )
    if _CAMPAIGN_IX in _indexes():
        op.drop_index(_CAMPAIGN_IX, table_name=_TABLE)

    columns = _columns()
    if "legacy_record_id" in columns:
        op.drop_column(_TABLE, "legacy_record_id")
    columns = _columns()
    if "campaign_id" in columns:
        op.drop_column(_TABLE, "campaign_id")
