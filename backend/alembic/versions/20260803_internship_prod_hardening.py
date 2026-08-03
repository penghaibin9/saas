"""internship production data invariants and sensitive-field hardening.

Revision ID: 20260803_internship_prod_hardening
Revises: 0161_access_governance
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260803_internship_prod_hardening"
down_revision = "0161_access_governance"
branch_labels = None
depends_on = None

_MIGRATION_ACTOR = "20260803_internship_prod_hardening"


def _columns(bind, table: str) -> dict[str, dict]:
    return {str(item["name"]): item for item in inspect(bind).get_columns(table)}


def _index_columns(bind, table: str) -> set[tuple[str, ...]]:
    return {
        tuple(str(value) for value in (item.get("column_names") or ()))
        for item in inspect(bind).get_indexes(table)
    }


def _unique_columns(bind, table: str) -> set[tuple[str, ...]]:
    values = {
        tuple(str(value) for value in (item.get("column_names") or ()))
        for item in inspect(bind).get_unique_constraints(table)
    }
    values.update(
        tuple(str(value) for value in (item.get("column_names") or ()))
        for item in inspect(bind).get_indexes(table)
        if item.get("unique")
    )
    return values


def _ensure_column(bind, table: str, column: sa.Column) -> None:
    if column.name not in _columns(bind, table):
        op.add_column(table, column)


def _ensure_index(bind, name: str, table: str, columns: list[str]) -> None:
    if tuple(columns) not in _index_columns(bind, table):
        op.create_index(name, table, columns)


def _ensure_unique(bind, name: str, table: str, columns: list[str]) -> None:
    if tuple(columns) not in _unique_columns(bind, table):
        op.create_unique_constraint(name, table, columns)


def _constraint_names(bind, table: str) -> set[str]:
    names = {
        str(item.get("name"))
        for item in inspect(bind).get_unique_constraints(table)
        if item.get("name")
    }
    names.update(
        str(item.get("name"))
        for item in inspect(bind).get_indexes(table)
        if item.get("name")
    )
    return names


def _write_dedup_audit(
    bind,
    *,
    tenant_id: int,
    target_id: int,
    target_type: str,
    detail: dict,
) -> None:
    bind.execute(sa.text(
        "INSERT INTO t_internship_audit_trail "
        "(tenant_id, target_id, target_type, action, operator_name, detail_json, "
        "occurred_at, created_at, updated_at, is_deleted) "
        "VALUES (:tenant_id, :target_id, :target_type, 'MIGRATION_DEDUPLICATE', "
        ":operator_name, :detail_json, UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP(), 0)"
    ), {
        "tenant_id": tenant_id,
        "target_id": target_id,
        "target_type": target_type,
        "operator_name": _MIGRATION_ACTOR,
        "detail_json": json.dumps(detail, ensure_ascii=False),
    })


def _normalize_record_duplicates(table: str, target_type: str) -> None:
    """Preserve duplicate rows while freeing the natural key for a real DB unique constraint.

    Soft-deleting a duplicate is not sufficient because MySQL unique indexes still include
    soft-deleted rows. The retained row keeps the real internship_id; historical duplicates
    keep their stable primary keys and payloads but receive a unique negative tombstone key.
    An append-only audit row stores the original key and deletion flag for a reversible downgrade.
    """
    bind = op.get_bind()
    groups = bind.execute(sa.text(
        f"SELECT tenant_id, internship_id, "
        "COALESCE(MAX(CASE WHEN is_deleted=0 THEN id END), MAX(id)) AS keep_id "
        f"FROM {table} GROUP BY tenant_id, internship_id HAVING COUNT(*) > 1"
    )).mappings().all()
    for group in groups:
        duplicates = bind.execute(sa.text(
            f"SELECT id, is_deleted FROM {table} "
            "WHERE tenant_id=:tenant_id AND internship_id=:internship_id AND id<>:keep_id "
            "ORDER BY id"
        ), dict(group)).mappings().all()
        for row in duplicates:
            _write_dedup_audit(
                bind,
                tenant_id=int(group["tenant_id"]),
                target_id=int(row["id"]),
                target_type=target_type,
                detail={
                    "table": table,
                    "originalInternshipId": int(group["internship_id"]),
                    "originalIsDeleted": bool(row["is_deleted"]),
                    "keptId": int(group["keep_id"]),
                    "tombstoneInternshipId": -int(row["id"]),
                },
            )
            bind.execute(sa.text(
                f"UPDATE {table} SET internship_id=:tombstone_id, is_deleted=1 "
                "WHERE tenant_id=:tenant_id AND id=:id"
            ), {
                "tenant_id": int(group["tenant_id"]),
                "id": int(row["id"]),
                "tombstone_id": -int(row["id"]),
            })


def _normalize_risk_source_duplicates() -> None:
    bind = op.get_bind()
    groups = bind.execute(sa.text(
        "SELECT tenant_id, source_type, source_id, risk_code, "
        "COALESCE(MAX(CASE WHEN is_deleted=0 THEN id END), MAX(id)) AS keep_id "
        "FROM t_risk_record "
        "WHERE source_type IS NOT NULL AND source_id IS NOT NULL "
        "GROUP BY tenant_id, source_type, source_id, risk_code HAVING COUNT(*) > 1"
    )).mappings().all()
    for group in groups:
        duplicates = bind.execute(sa.text(
            "SELECT id, is_deleted FROM t_risk_record "
            "WHERE tenant_id=:tenant_id AND source_type=:source_type "
            "AND source_id=:source_id AND risk_code=:risk_code AND id<>:keep_id "
            "ORDER BY id"
        ), dict(group)).mappings().all()
        for row in duplicates:
            _write_dedup_audit(
                bind,
                tenant_id=int(group["tenant_id"]),
                target_id=int(row["id"]),
                target_type="RISK",
                detail={
                    "table": "t_risk_record",
                    "originalSourceType": str(group["source_type"]),
                    "originalSourceId": int(group["source_id"]),
                    "riskCode": str(group["risk_code"]),
                    "originalIsDeleted": bool(row["is_deleted"]),
                    "keptId": int(group["keep_id"]),
                    "tombstoneSourceId": -int(row["id"]),
                },
            )
            bind.execute(sa.text(
                "UPDATE t_risk_record SET source_id=:tombstone_id, is_deleted=1 "
                "WHERE tenant_id=:tenant_id AND id=:id"
            ), {
                "tenant_id": int(group["tenant_id"]),
                "id": int(row["id"]),
                "tombstone_id": -int(row["id"]),
            })


def _restore_deduplicated_rows(bind, table: str, target_type: str) -> None:
    audits = bind.execute(sa.text(
        "SELECT target_id, detail_json FROM t_internship_audit_trail "
        "WHERE target_type=:target_type AND action='MIGRATION_DEDUPLICATE' "
        "AND operator_name=:operator_name ORDER BY id"
    ), {
        "target_type": target_type,
        "operator_name": _MIGRATION_ACTOR,
    }).mappings().all()
    for audit in audits:
        detail = audit["detail_json"] or {}
        if isinstance(detail, str):
            detail = json.loads(detail)
        if detail.get("table") != table:
            continue
        bind.execute(sa.text(
            f"UPDATE {table} SET internship_id=:internship_id, is_deleted=:is_deleted "
            "WHERE id=:id"
        ), {
            "internship_id": int(detail["originalInternshipId"]),
            "is_deleted": bool(detail.get("originalIsDeleted")),
            "id": int(audit["target_id"]),
        })


def _restore_risk_source_duplicates(bind) -> None:
    audits = bind.execute(sa.text(
        "SELECT target_id, detail_json FROM t_internship_audit_trail "
        "WHERE target_type='RISK' AND action='MIGRATION_DEDUPLICATE' "
        "AND operator_name=:operator_name ORDER BY id"
    ), {"operator_name": _MIGRATION_ACTOR}).mappings().all()
    for audit in audits:
        detail = audit["detail_json"] or {}
        if isinstance(detail, str):
            detail = json.loads(detail)
        if detail.get("table") != "t_risk_record":
            continue
        bind.execute(sa.text(
            "UPDATE t_risk_record SET source_type=:source_type, source_id=:source_id, "
            "is_deleted=:is_deleted WHERE id=:id"
        ), {
            "source_type": str(detail["originalSourceType"]),
            "source_id": int(detail["originalSourceId"]),
            "is_deleted": bool(detail.get("originalIsDeleted")),
            "id": int(audit["target_id"]),
        })


def _score_scope_key(batch_id) -> str:
    return f"BATCH:{int(batch_id)}" if batch_id is not None else "TENANT_DEFAULT"


def _normalize_score_config_scopes(bind) -> None:
    rows = bind.execute(sa.text(
        "SELECT id, tenant_id, batch_id FROM t_internship_score_config "
        "WHERE status='ACTIVE' AND is_deleted=0 "
        "ORDER BY tenant_id, batch_id, id DESC"
    )).mappings().all()
    kept: set[tuple[int, int | None]] = set()
    for row in rows:
        group = (int(row["tenant_id"]), int(row["batch_id"]) if row["batch_id"] is not None else None)
        if group in kept:
            bind.execute(sa.text(
                "UPDATE t_internship_score_config SET status='RETIRED', "
                "active_scope_key=NULL WHERE id=:id"
            ), {"id": int(row["id"])})
            continue
        kept.add(group)
        bind.execute(sa.text(
            "UPDATE t_internship_score_config SET active_scope_key=:scope_key WHERE id=:id"
        ), {"scope_key": _score_scope_key(row["batch_id"]), "id": int(row["id"])})
    bind.execute(sa.text(
        "UPDATE t_internship_score_config SET active_scope_key=NULL "
        "WHERE status<>'ACTIVE' OR is_deleted<>0"
    ))


def upgrade() -> None:
    bind = op.get_bind()

    # 0148 material-center migration already introduced complaint.internship_id on the
    # authoritative chain. Keep this migration safe for both fully upgraded and older
    # installations instead of blindly adding the column a second time.
    _ensure_column(bind, "t_internship_complaint", sa.Column(
        "internship_id", sa.BigInteger(), nullable=True))
    _ensure_column(bind, "t_internship_complaint", sa.Column(
        "complainant_contact_hash", sa.String(64), nullable=True))
    contact_column = _columns(bind, "t_internship_complaint").get(
        "complainant_contact_encrypted")
    if contact_column is not None and getattr(contact_column.get("type"), "length", 0) != 500:
        op.alter_column(
            "t_internship_complaint",
            "complainant_contact_encrypted",
            existing_type=contact_column["type"],
            type_=sa.String(500),
            existing_nullable=bool(contact_column.get("nullable", True)),
        )
    _ensure_index(
        bind,
        "ix_internship_complaint_internship_id",
        "t_internship_complaint",
        ["internship_id"],
    )
    _ensure_index(
        bind,
        "ix_internship_complaint_contact_hash",
        "t_internship_complaint",
        ["complainant_contact_hash"],
    )

    _ensure_column(bind, "t_risk_record", sa.Column(
        "source_type", sa.String(50), nullable=True))
    _ensure_column(bind, "t_risk_record", sa.Column(
        "source_id", sa.BigInteger(), nullable=True))
    _ensure_column(bind, "t_risk_record", sa.Column(
        "source_version", sa.Integer(), nullable=True))
    _ensure_index(
        bind,
        "ix_risk_source",
        "t_risk_record",
        ["tenant_id", "source_type", "source_id"],
    )

    _ensure_column(bind, "t_internship_change_request", sa.Column(
        "record_version_snapshot", sa.Integer(), nullable=True))
    _ensure_column(bind, "t_internship_score_config", sa.Column(
        "active_scope_key", sa.String(80), nullable=True))
    _normalize_score_config_scopes(bind)
    _ensure_unique(
        bind,
        "uk_intern_score_cfg_active_scope",
        "t_internship_score_config",
        ["tenant_id", "active_scope_key"],
    )
    bind.execute(sa.text(
        "UPDATE t_internship_change_request c "
        "JOIN t_internship_record r ON r.id=c.internship_id AND r.tenant_id=c.tenant_id "
        "SET c.record_version_snapshot=COALESCE(r.version, 0) "
        "WHERE c.record_version_snapshot IS NULL"
    ))
    snapshot_column = _columns(bind, "t_internship_change_request").get(
        "record_version_snapshot")
    if snapshot_column is not None and snapshot_column.get("nullable", True):
        op.alter_column(
            "t_internship_change_request",
            "record_version_snapshot",
            existing_type=snapshot_column["type"],
            nullable=False,
            server_default="0",
        )

    complaints = bind.execute(sa.text(
        "SELECT id, tenant_id, student_id, batch_id, complainant_contact_encrypted "
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
                "SELECT id FROM t_internship_record "
                "WHERE tenant_id=:tenant_id AND student_id=:student_id "
                "AND batch_id=:batch_id AND is_deleted=0 LIMIT 1"
            ), row).scalar()
            if rec:
                values["internship_id"] = rec
        if values:
            bind.execute(sa.text(
                "UPDATE t_internship_complaint SET "
                "complainant_contact_encrypted=COALESCE(:encrypted, complainant_contact_encrypted), "
                "complainant_contact_hash=COALESCE(:contact_hash, complainant_contact_hash), "
                "internship_id=COALESCE(:internship_id, internship_id) WHERE id=:id"
            ), {
                "id": row["id"],
                "encrypted": values.get("encrypted"),
                "contact_hash": values.get("contact_hash"),
                "internship_id": values.get("internship_id"),
            })

    bind.execute(sa.text(
        "UPDATE t_risk_record SET source_type='COMPLAINT', "
        "source_id=CAST(SUBSTRING(risk_code, 9) AS UNSIGNED), source_version=0, "
        "source_module='complaint' WHERE risk_code LIKE 'INT-CPL-%' AND source_id IS NULL"
    ))

    _normalize_record_duplicates("t_internship_final_score", "SCORE")
    _normalize_record_duplicates("t_internship_archive", "ARCHIVE")
    _normalize_risk_source_duplicates()
    _ensure_unique(
        bind,
        "uk_internship_final_score_record",
        "t_internship_final_score",
        ["tenant_id", "internship_id"],
    )
    _ensure_unique(
        bind,
        "uk_internship_archive_record",
        "t_internship_archive",
        ["tenant_id", "internship_id"],
    )
    _ensure_unique(
        bind,
        "uk_risk_source",
        "t_risk_record",
        ["tenant_id", "source_type", "source_id", "risk_code"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    if "uk_intern_score_cfg_active_scope" in _constraint_names(
        bind, "t_internship_score_config"
    ):
        op.drop_constraint(
            "uk_intern_score_cfg_active_scope",
            "t_internship_score_config",
            type_="unique",
        )
    if "active_scope_key" in _columns(bind, "t_internship_score_config"):
        op.drop_column("t_internship_score_config", "active_scope_key")

    for table, name in (
        ("t_risk_record", "uk_risk_source"),
        ("t_internship_archive", "uk_internship_archive_record"),
        ("t_internship_final_score", "uk_internship_final_score_record"),
    ):
        if name in _constraint_names(bind, table):
            op.drop_constraint(name, table, type_="unique")

    _restore_risk_source_duplicates(bind)
    _restore_deduplicated_rows(bind, "t_internship_archive", "ARCHIVE")
    _restore_deduplicated_rows(bind, "t_internship_final_score", "SCORE")

    if "ix_risk_source" in _constraint_names(bind, "t_risk_record"):
        op.drop_index("ix_risk_source", table_name="t_risk_record")
    for column in ("source_version", "source_id", "source_type"):
        if column in _columns(bind, "t_risk_record"):
            op.drop_column("t_risk_record", column)

    if "record_version_snapshot" in _columns(bind, "t_internship_change_request"):
        op.drop_column("t_internship_change_request", "record_version_snapshot")

    names = _constraint_names(bind, "t_internship_complaint")
    if "ix_internship_complaint_contact_hash" in names:
        op.drop_index(
            "ix_internship_complaint_contact_hash",
            table_name="t_internship_complaint",
        )
    if "complainant_contact_hash" in _columns(bind, "t_internship_complaint"):
        op.drop_column("t_internship_complaint", "complainant_contact_hash")
    # internship_id is retained because an earlier authoritative migration owns it.
