from __future__ import annotations

import inspect
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.api.v1.file import UploadSessionCreate
from app.services.storage import production
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


def test_promotion_copy_verifies_before_source_delete():
    source = inspect.getsource(production.promote_file_object)
    assert source.index("copy_object") < source.index("sizeBytes") < source.index("backend.delete(source_key)")
