from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from app.services.streaming_archive_service import add_json, add_path, temporary_zip

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_graduation_legacy_packages_delegate_to_authoritative_export_job():
    source = _read(
        "backend/app/modules/graduation/services/graduation_material_center_service.py"
    )
    assert "from app.modules.graduation.materials import" in source
    assert "export_service" in source
    assert "export_service.create_student_export_job(" in source
    assert "export_service.create_export_job(" in source
    assert source.count("export_service.run_export_job(") >= 2
    assert ".read_bytes(" not in source
    assert "io.BytesIO()" not in source


def test_internship_package_delegates_to_streaming_manifest_implementation():
    core = _read(
        "backend/app/modules/internship/services/internship_material_center_service.py"
    )
    streaming = _read(
        "backend/app/modules/internship/services/internship_streaming_package_service.py"
    )
    assert "internship_streaming_package_service" in core
    assert "return stream_package(internship_id, user=user)" in core
    assert ".read_bytes(" not in core
    assert "io.BytesIO()" not in core
    assert "temporary_zip(" in streaming
    assert "add_path(" in streaming
    assert "expected_sha256=item.sha256_snapshot" in streaming
    assert "expected_size=int(item.size_snapshot or 0)" in streaming
    assert "store_generated_path(" in streaming
    assert ".read_bytes(" not in streaming
    assert "io.BytesIO()" not in streaming


def test_generated_path_boundary_hashes_and_copies_in_chunks():
    source = _read("backend/app/services/generated_file_path_service.py")
    assert "CHUNK_SIZE = 1024 * 1024" in source
    assert "while True:" in source
    assert "reader.read(CHUNK_SIZE)" in source
    assert "validate_content_path(" in source
    assert ".read_bytes(" not in source


def test_streaming_zip_writes_large_entry_without_whole_file_read(tmp_path):
    body = (b"streaming-archive-block-" * 131072) + b"tail"
    source = tmp_path / "large.bin"
    source.write_bytes(body)
    expected = hashlib.sha256(body).hexdigest()
    zip_path, archive = temporary_zip(prefix="streaming-cutover-test-")
    try:
        digest, size = add_path(
            archive,
            "materials/large.bin",
            source,
            expected_sha256=expected,
            expected_size=len(body),
        )
        add_json(archive, "manifest.json", {"sha256": digest, "sizeBytes": size})
        archive.close()
        with zipfile.ZipFile(zip_path, "r") as check:
            assert check.read("materials/large.bin") == body
            assert "manifest.json" in check.namelist()
        assert digest == expected
        assert size == len(body)
    finally:
        try:
            archive.close()
        finally:
            zip_path.unlink(missing_ok=True)
