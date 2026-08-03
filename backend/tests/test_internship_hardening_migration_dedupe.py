from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import bindparam, select, text

from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, InternshipFinalScore

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/alembic/versions/20260803_internship_prod_hardening.py"
UNIQUE_NAME = "uk_internship_final_score_record"
TENANT_ID = 1000000000000099937
INTERNSHIP_ID = 1000000000000099938
STUDENT_ID = 1000000000000099939


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "internship_prod_hardening_migration_test",
        MIGRATION,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_unique(db) -> bool:
    return db.execute(text(
        "SELECT 1 FROM information_schema.statistics "
        "WHERE table_schema=DATABASE() AND table_name='t_internship_final_score' "
        "AND index_name=:name AND non_unique=0 LIMIT 1"
    ), {"name": UNIQUE_NAME}).first() is not None


def test_score_dedupe_preserves_rows_audits_and_downgrades(db_mode, monkeypatch):
    db = get_sessionmaker()()
    created_ids: list[int] = []
    try:
        if _has_unique(db):
            db.execute(text(
                f"ALTER TABLE t_internship_final_score DROP INDEX {UNIQUE_NAME}"
            ))
            db.commit()

        first = InternshipFinalScore(
            tenant_id=TENANT_ID,
            internship_id=INTERNSHIP_ID,
            student_id=STUDENT_ID,
            status="PENDING_CALC",
        )
        second = InternshipFinalScore(
            tenant_id=TENANT_ID,
            internship_id=INTERNSHIP_ID,
            student_id=STUDENT_ID,
            status="PENDING_REVIEW",
        )
        db.add_all([first, second])
        db.commit()
        db.refresh(first)
        db.refresh(second)
        created_ids = [int(first.id), int(second.id)]

        migration = _load_migration()
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        migration._normalize_record_duplicates(
            "t_internship_final_score",
            "SCORE",
        )
        db.commit()

        rows = db.scalars(select(InternshipFinalScore).where(
            InternshipFinalScore.id.in_(created_ids),
        ).order_by(InternshipFinalScore.id)).all()
        assert len(rows) == 2
        keep = max(rows, key=lambda row: int(row.id))
        tombstone = min(rows, key=lambda row: int(row.id))
        assert int(keep.internship_id) == INTERNSHIP_ID
        assert keep.is_deleted is False
        assert int(tombstone.internship_id) == -int(tombstone.id)
        assert tombstone.is_deleted is True

        audit = db.scalar(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "SCORE",
            InternshipAuditTrail.target_id == tombstone.id,
            InternshipAuditTrail.action == "MIGRATION_DEDUPLICATE",
        ))
        assert audit is not None
        assert int((audit.detail_json or {})["originalInternshipId"]) == INTERNSHIP_ID
        assert int((audit.detail_json or {})["keptId"]) == int(keep.id)

        migration._restore_deduplicated_rows(
            db.connection(),
            "t_internship_final_score",
            "SCORE",
        )
        db.commit()
        db.expire_all()
        restored = db.scalars(select(InternshipFinalScore).where(
            InternshipFinalScore.id.in_(created_ids),
        ).order_by(InternshipFinalScore.id)).all()
        assert [int(row.internship_id) for row in restored] == [
            INTERNSHIP_ID,
            INTERNSHIP_ID,
        ]
        assert all(row.is_deleted is False for row in restored)
    finally:
        if created_ids:
            audit_delete = text(
                "DELETE FROM t_internship_audit_trail "
                "WHERE tenant_id=:tenant_id AND target_type='SCORE' "
                "AND target_id IN :target_ids AND action='MIGRATION_DEDUPLICATE'"
            ).bindparams(bindparam("target_ids", expanding=True))
            score_delete = text(
                "DELETE FROM t_internship_final_score WHERE id IN :target_ids"
            ).bindparams(bindparam("target_ids", expanding=True))
            db.execute(audit_delete, {
                "tenant_id": TENANT_ID,
                "target_ids": created_ids,
            })
            db.execute(score_delete, {"target_ids": created_ids})
            db.commit()
        if not _has_unique(db):
            db.execute(text(
                f"ALTER TABLE t_internship_final_score "
                f"ADD CONSTRAINT {UNIQUE_NAME} UNIQUE (tenant_id, internship_id)"
            ))
            db.commit()
        db.close()
