from __future__ import annotations

import inspect
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.api.v1.file import UploadSessionCreate
from app.services.storage import production
from app.services.storage import finalize as finalize_service
from app.services.storage import promotion
from app.services.storage.keys import assert_exact_object_key, build_object_key


def test_zone_key_is_random_tenant_scoped_and_hides_filename():
    key = build_object_key(
        zone="QUARANTINE",
        tenant_id=17,
        ext="docx",
        now=datetime(2026, 7, 31),
    )
    assert key.startswith("quarantine/17/2026/07/")
    assert key.endswith(".docx")
    assert "论文" not in key
    assert len(key.split("/")[-1].split(".")[0]) == 32


def test_sts_scope_rejects_wildcards_parent_escape_and_foreign_tenant():
    assert assert_exact_object_key(
        "quarantine/17/2026/07/abc.docx",
        zone="QUARANTINE",
        tenant_id=17,
    ).endswith("abc.docx")
    for invalid in (
        "quarantine/17/*",
        "quarantine/17/2026/../other.docx",
        "quarantine/18/2026/07/abc.docx",
        "clean/17/2026/07/abc.docx",
    ):
        with pytest.raises(Exception):
            assert_exact_object_key(invalid, zone="QUARANTINE", tenant_id=17)


def test_upload_session_contract_forbids_frontend_storage_authority_fields():
    body = UploadSessionCreate(
        fileName="paper.docx",
        sizeBytes=1024,
        bizType="GRADUATION_MATERIAL",
        clientType="ADMIN_PC",
        idempotencyKey="01234567",
    )
    assert body.fileName == "paper.docx"
    with pytest.raises(ValidationError):
        UploadSessionCreate(
            fileName="paper.docx",
            sizeBytes=1024,
            bizType="GRADUATION_MATERIAL",
            clientType="ADMIN_PC",
            idempotencyKey="01234567",
            objectKey="clean/17/forged.docx",
        )


def test_sts_credentials_are_exact_short_lived_and_server_only():
    source = inspect.getsource(production._credential_for_exact_key)
    assert '"allow_prefix": [object_key]' in source
    assert '"allow_prefix": ["*"]' not in source
    assert "_STS_SECONDS = 900" in inspect.getsource(production)
    assert "tmpSecretKey" in source


def test_complete_session_heads_size_and_etag_before_file_object():
    source = inspect.getsource(production.complete_upload_session)
    assert "head_object(object_key)" in source
    assert "FILE_UPLOAD_SIZE_MISMATCH" in source
    assert "FILE_UPLOAD_ETAG_MISMATCH" in source
    assert 'storage_zone="QUARANTINE"' in source
    assert "enqueue_file_scan" in source


def test_promotion_prepare_never_deletes_authoritative_source():
    source = inspect.getsource(promotion.prepare_file_object_promotion)
    assert "copy_object" in source
    assert "sizeBytes" in source
    assert "backend.delete(source_key)" not in source
    assert '"cleanupSourceAfterCommit"' in source


def test_finalize_commits_metadata_before_source_cleanup():
    source = inspect.getsource(finalize_service.finalize_scan_storage)
    commit_index = source.index("db.commit()", source.index("prepare_file_object_promotion"))
    cleanup_index = source.index("cleanup_promoted_source", source.index("prepare_file_object_promotion"))
    assert commit_index < cleanup_index
    assert "sourceCleanupPending" in source
    assert "readyForBusiness" in source


def test_cleanup_failure_is_debt_not_target_rollback():
    source = inspect.getsource(promotion.cleanup_promoted_source)
    assert '"sourceCleanupPending": True' in source
    assert "raise" not in source.split("def cleanup_promoted_source", 1)[1]
