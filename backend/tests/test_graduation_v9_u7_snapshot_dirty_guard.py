from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_u7_dirty_identity_blocks_structured_snapshot_before_any_file_write():
    text = (ROOT / "backend/app/modules/graduation/materials/snapshot_service.py").read_text(encoding="utf-8")
    guard = text.index("assert_archive_identity_writable(student)")
    first_file_write = text.index("file_service.store_bytes(")
    register_write = text.index("register_generated_snapshot(")
    assert guard < first_file_write < register_write
    assert "graduation_archive_data_quality import assert_archive_identity_writable" in text
