from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import UniqueConstraint

from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.exact_file_version_read_port import ExactSourceVersion
from app.modules.platform.document_lifecycle.file_job_dag import (
    _assert_credential_free,
    prepare_compare_job,
    prepare_extract_job,
)
from app.modules.platform.document_lifecycle.models import (
    DocumentCompareResult,
    FileDerivedArtifact,
    StudentLifecycleFact,
)


class _Port:
    def __init__(self):
        self.calls = []

    def resolve(self, *, file_version_id, expected_sha256, action, user):
        self.calls.append((file_version_id, expected_sha256, action, user))
        return ExactSourceVersion(
            tenant_id=101,
            asset_id=200 + file_version_id,
            file_version_id=file_version_id,
            file_object_id=100 + file_version_id,
            version_no=1,
            source_sha256=expected_sha256.lower(),
            mime_type="text/plain",
            ext="txt",
            size_bytes=10,
            sensitivity_level="PERSONAL",
            source_binding_refs=(),
        )


def test_extract_job_pins_only_immutable_source_identity() -> None:
    port = _Port()
    spec = prepare_extract_job(
        file_version_id=1,
        expected_sha256="a" * 64,
        user={"userId": "8", "accessToken": "must-not-be-copied"},
        port=port,
    )
    assert spec.job_type == "DOCUMENT_EXTRACT"
    assert spec.file_id == 101
    assert spec.payload["source"]["file_version_id"] == 1
    assert spec.payload["source"]["source_sha256"] == "a" * 64
    assert "accessToken" not in str(spec.payload)
    assert port.calls == [(1, "a" * 64, "extract", {"userId": "8", "accessToken": "must-not-be-copied"})]


def test_compare_is_directional_and_authorizes_both_sources() -> None:
    port = _Port()
    forward = prepare_compare_job(
        left_file_version_id=1,
        left_expected_sha256="a" * 64,
        right_file_version_id=2,
        right_expected_sha256="b" * 64,
        user={"userId": "8"},
        port=port,
    )
    reverse = prepare_compare_job(
        left_file_version_id=2,
        left_expected_sha256="b" * 64,
        right_file_version_id=1,
        right_expected_sha256="a" * 64,
        user={"userId": "8"},
        port=port,
    )
    assert forward.dedupe_key != reverse.dedupe_key
    assert forward.payload["left"]["file_version_id"] == 1
    assert forward.payload["right"]["file_version_id"] == 2
    assert [call[2] for call in port.calls] == ["compare", "compare", "compare", "compare"]


@pytest.mark.parametrize("key", ["accessToken", "refresh_cookie", "previewTicket", "storageUrl", "userSession"])
def test_job_payload_guard_rejects_credentials_and_temporary_access(key: str) -> None:
    with pytest.raises(AppException) as exc:
        _assert_credential_free({"source": {key: "secret"}})
    assert exc.value.code == "VALIDATION_ERROR"


def test_private_models_freeze_directional_and_dedupe_identity() -> None:
    def unique_columns(model):
        return {
            tuple(column.name for column in constraint.columns)
            for constraint in model.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }

    assert (
        "tenant_id", "left_file_version_id", "left_source_sha256",
        "right_file_version_id", "right_source_sha256", "algorithm_code", "algorithm_version",
    ) in unique_columns(DocumentCompareResult)
    assert (
        "tenant_id", "source_file_version_id", "source_sha256", "derivative_kind",
        "extractor_code", "extractor_version",
    ) in unique_columns(FileDerivedArtifact)
    assert ("tenant_id", "dedupe_key") in unique_columns(StudentLifecycleFact)
    assert "is_deleted" not in StudentLifecycleFact.__table__.c
    assert "version" not in StudentLifecycleFact.__table__.c


def test_plat_c_private_layer_has_no_source_current_writer_or_raw_route() -> None:
    root = Path("app/modules/platform/document_lifecycle")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = (
        "FileVersion.is_current =",
        "FileAsset.current_version_id =",
        "FileBinding.is_current =",
        '"/admin/',
        '"/pages/',
    )
    assert not any(item in source for item in forbidden)
