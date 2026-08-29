"""GD-018 canonical V2 filing side-effect contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v2_manifest_writer_preserves_archive_audit_and_risk_refresh():
    manifest = _text("backend/app/modules/graduation/materials/manifest_service.py")

    assert "graduation_archive_service as archive_service" in manifest
    assert "archive_service._audit(" in manifest
    assert '"核验归档"' in manifest
    assert "notify_risk_rescan(db, student.id)" in manifest

    # These side effects belong to the first successful freeze transaction, not
    # the idempotent early-return path for an already frozen manifest.
    audit_pos = manifest.index("archive_service._audit(")
    commit_pos = manifest.index("db.commit()", audit_pos)
    assert audit_pos < commit_pos
