"""internship production data invariants and sensitive-field hardening.

Revision ID: 20260803_internship_prod_hardening
Revises: 0161_access_governance
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260803_internship_prod_hardening"
down_revision = "0161_access_governance"
branch_labels = None
depends_on = None


def _soft_delete_duplicates(table: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        f"SELECT tenant_id, internship_id, MAX(id) AS keep_id FROM {table} "
        "WHERE is_deleted = 0 GROUP BY tenant_id, internship_id HAVING COUNT(*) > 1"
    )).mappings().all()
    for row in rows:
        bind.execute(sa.text(
            f"UPDATE {table} SET is_deleted = 1 WHERE tenant_id = :tenant_id "
            "AND internship_id = :internship_id AND id <> :keep_id AND is_deleted = 0"
        ), dict(row))


def upgrade() -> None:
    op.add_column("t_internship_complaint", sa.Column("internship_id", sa.BigInteger(), nullable=True))
    op.add_column("t_internship_complaint", sa.Column("complainant_contact_hash", sa.String(64), nullable=True))
    op.create_index("ix_internship_complaint_internship_id", "t_internship_complaint", ["internship_id"])
    op.create_index("ix_internship_complaint_contact_hash", "t_internship_complaint", ["complainant_contact_hash"])

    op.add_column("t_risk_record", sa.Column("source_type", sa.String(50), nullable=True))
    op.add_column("t_risk_record", sa.Column("source_id", sa.BigInteger(), nullable=True))
    op.add_column("t_risk_record", sa.Column("source_version", sa.Integer(), nullable=True))
    op.create_index("ix_risk_source", "t_risk_record", ["tenant_id", "source_type", "source_id"])

    op.add_column("t_internship_change_request", sa.Column(
        "record_version_snapshot", sa.Integer(), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE t_internship_change_request c "
        "JOIN t_internship_record r ON r.id=c.internship_id AND r.tenant_id=c.tenant_id "
        "SET c.record_version_snapshot=COALESCE(r.version, 0) "
        "WHERE c.record_version_snapshot IS NULL"
    ))
    op.alter_column("t_internship_change_request", "record_version_snapshot",
                    existing_type=sa.Integer(), nullable=False, server_default="0")
    complaints = bind.execute(sa.text(
        "SELECT id, student_id, batch_id, complainant_contact_encrypted "
        "FROM t_internship_complaint"
    )).mappings().all()
    from app.core.field_crypto import (
        decrypt_sensitive,
        encrypt_sensitive,
        hash_sensitive,
        looks_like_fernet,
    )
    for row in complaints:
        values = {}
        contact = row["complainant_contact_encrypted"]
        if contact:
            stored = str(contact)
            plain = decrypt_sensitive(
                stored,
                "internship_complaint_contact",
                allow_legacy_plaintext=True,
            )
            if plain is None:
                raise RuntimeError(
                    f"cannot decrypt complaint contact during migration: complaint_id={row['id']}"
                )
            if not looks_like_fernet(stored):
                values["encrypted"] = encrypt_sensitive(
                    plain, "internship_complaint_contact")
            values["contact_hash"] = hash_sensitive(
                plain, "internship_complaint_contact")
        if row["student_id"] and row["batch_id"]:
            rec = bind.execute(sa.text(
                "SELECT id FROM t_internship_record WHERE tenant_id = "
                "(SELECT tenant_id FROM t_internship_complaint WHERE id=:id) "
                "AND student_id=:student_id AND batch_id=:batch_id AND is_deleted=0 LIMIT 1"
            ), row).scalar()
            if rec:
                values["internship_id"] = rec
        if values:
            bind.execute(sa.text(
                "UPDATE t_internship_complaint SET "
                "complainant_contact_encrypted=COALESCE(:encrypted, complainant_contact_encrypted), "
                "complainant_contact_hash=COALESCE(:contact_hash, complainant_contact_hash), "
                "internship_id=COALESCE(:internship_id, internship_id) WHERE id=:id"
            ), {"id": row["id"], "encrypted": values.get("encrypted"),
                 "contact_hash": values.get("contact_hash"),
                 "internship_id": values.get("internship_id")})

    bind.execute(sa.text(
        "UPDATE t_risk_record SET source_type='COMPLAINT', "
        "source_id=CAST(SUBSTRING(risk_code, 9) AS UNSIGNED), source_version=0, "
        "source_module='complaint' WHERE risk_code LIKE 'INT-CPL-%' AND source_id IS NULL"
    ))

    _soft_delete_duplicates("t_internship_final_score")
    _soft_delete_duplicates("t_internship_archive")
    op.create_unique_constraint(
        "uk_internship_final_score_record", "t_internship_final_score",
        ["tenant_id", "internship_id"])
    op.create_unique_constraint(
        "uk_internship_archive_record", "t_internship_archive",
        ["tenant_id", "internship_id"])
    op.create_unique_constraint(
        "uk_risk_source", "t_risk_record",
        ["tenant_id", "source_type", "source_id", "risk_code"])


def downgrade() -> None:
    op.drop_column("t_internship_change_request", "record_version_snapshot")
    op.drop_constraint("uk_risk_source", "t_risk_record", type_="unique")
    op.drop_constraint("uk_internship_archive_record", "t_internship_archive", type_="unique")
    op.drop_constraint("uk_internship_final_score_record", "t_internship_final_score", type_="unique")
    op.drop_index("ix_risk_source", table_name="t_risk_record")
    op.drop_column("t_risk_record", "source_version")
    op.drop_column("t_risk_record", "source_id")
    op.drop_column("t_risk_record", "source_type")
    op.drop_index("ix_internship_complaint_contact_hash", table_name="t_internship_complaint")
    op.drop_index("ix_internship_complaint_internship_id", table_name="t_internship_complaint")
    op.drop_column("t_internship_complaint", "complainant_contact_hash")
    op.drop_column("t_internship_complaint", "internship_id")
