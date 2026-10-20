from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.exact_file_version_read_port import (
    ExactFileVersionReadPort,
    IExactFileVersionReadPort,
    _ExactVersionRows,
)


class _Session:
    closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _tenant_context():
    set_tenant(101)
    yield
    set_tenant(None)


def _binding(**overrides):
    values = {
        "id": 401,
        "biz_type": "GRADUATION_MATERIAL",
        "biz_id": "9001",
        "relation_type": "FINAL",
        "module_code": "GRADUATION",
        "subject_type": "STUDENT",
        "subject_id": "7001",
        "batch_id": "8001",
        "asset_id": 201,
        "version_id": 301,
        "status": "SUPERSEDED",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _rows(*, sha: str = "a" * 64, exact_bindings=None):
    binding = _binding()
    return _ExactVersionRows(
        version=SimpleNamespace(id=301, version_no=2, is_current=False),
        asset=SimpleNamespace(id=201, sensitivity_level="sensitive"),
        file_object=SimpleNamespace(
            id=101,
            sha256=sha,
            mime_type="application/pdf",
            ext="pdf",
            size_bytes=1234,
            security_level="SENSITIVE",
        ),
        all_file_bindings=(binding,),
        exact_bindings=(binding,) if exact_bindings is None else tuple(exact_bindings),
    )


def _port(rows, *, allowed: bool = True, seen: dict | None = None):
    session = _Session()

    def loader(_db, tenant_id, version_id):
        assert tenant_id == 101
        assert version_id == 301
        return rows

    def authorizer(file_object, bindings, user, action, *, db):
        if seen is not None:
            seen.update({
                "fileObject": file_object,
                "bindings": bindings,
                "user": user,
                "action": action,
                "db": db,
            })
        return allowed

    return ExactFileVersionReadPort(
        session_factory=lambda: session,
        loader=loader,
        authorizer=authorizer,
    ), session


def test_exact_port_supports_authorized_historical_version() -> None:
    seen: dict = {}
    port, session = _port(_rows(), seen=seen)

    result = port.resolve(
        file_version_id=301,
        expected_sha256="A" * 64,
        action="compare",
        user={"userId": "77"},
    )

    assert isinstance(port, IExactFileVersionReadPort)
    assert result.file_version_id == 301
    assert result.file_object_id == 101
    assert result.version_no == 2
    assert result.source_sha256 == "a" * 64
    assert result.sensitivity_level == "SENSITIVE"
    assert result.source_binding_refs == ({
        "bindingId": 401,
        "bizType": "GRADUATION_MATERIAL",
        "bizId": "9001",
        "relationType": "FINAL",
        "moduleCode": "GRADUATION",
        "subjectType": "STUDENT",
        "subjectId": "7001",
        "batchId": "8001",
        "assetId": 201,
        "fileVersionId": 301,
        "status": "SUPERSEDED",
    },)
    assert seen["action"] == "preview"
    assert seen["user"] == {"userId": "77"}
    assert session.closed is True


def test_authorization_receives_only_the_exact_version_bindings() -> None:
    exact = _binding(id=401, version_id=301, status="SUPERSEDED")
    other = _binding(id=402, version_id=302, status="ACTIVE")
    rows = _rows(exact_bindings=(exact,))
    rows = _ExactVersionRows(
        version=rows.version,
        asset=rows.asset,
        file_object=rows.file_object,
        all_file_bindings=(exact, other),
        exact_bindings=(exact,),
    )
    seen: dict = {}
    port, _session = _port(rows, seen=seen)

    port.resolve(
        file_version_id=301,
        expected_sha256="a" * 64,
        action="preview",
        user={"userId": "77"},
    )

    assert [item.id for item in seen["bindings"]] == [401]


@pytest.mark.parametrize("rows", [None, _rows(exact_bindings=())])
def test_missing_deleted_cross_tenant_or_unbound_version_fails_closed(rows) -> None:
    port, session = _port(rows)
    with pytest.raises(AppException) as exc:
        port.resolve(
            file_version_id=301,
            expected_sha256="a" * 64,
            action="extract",
            user={"userId": "77"},
        )
    assert exc.value.code == "DATA_NOT_FOUND"
    assert session.closed is True


def test_wrong_sha_fails_before_authorization() -> None:
    seen: dict = {}
    port, _session = _port(_rows(sha="b" * 64), seen=seen)
    with pytest.raises(AppException) as exc:
        port.resolve(
            file_version_id=301,
            expected_sha256="a" * 64,
            action="preview",
            user={"userId": "77"},
        )
    assert exc.value.code == "DATA_NOT_FOUND"
    assert seen == {}


def test_revoked_source_authorization_denies_whole_read() -> None:
    port, _session = _port(_rows(), allowed=False)
    with pytest.raises(AppException) as exc:
        port.resolve(
            file_version_id=301,
            expected_sha256="a" * 64,
            action="derived-read",
            user={"userId": "77"},
        )
    assert exc.value.code == "DATA_NOT_FOUND"


@pytest.mark.parametrize(
    ("field", "value"),
    [("file_version_id", 0), ("expected_sha256", "bad"), ("action", "download-raw")],
)
def test_invalid_request_identity_is_rejected(field: str, value) -> None:
    payload = {
        "file_version_id": 301,
        "expected_sha256": "a" * 64,
        "action": "meta",
        "user": {"userId": "77"},
    }
    payload[field] = value
    port, _session = _port(_rows())
    with pytest.raises(AppException) as exc:
        port.resolve(**payload)
    assert exc.value.code == "VALIDATION_ERROR"


def test_no_tenant_context_is_rejected_before_opening_session() -> None:
    opened = False

    def factory():
        nonlocal opened
        opened = True
        return _Session()

    set_tenant(None)
    port = ExactFileVersionReadPort(session_factory=factory)
    with pytest.raises(AppException) as exc:
        port.resolve(
            file_version_id=301,
            expected_sha256="a" * 64,
            action="meta",
            user={"userId": "77"},
        )
    assert exc.value.code == "TENANT_CONTEXT_REQUIRED"
    assert opened is False


def test_plat_c_exact_read_port_contains_no_current_truth_writer() -> None:
    source = Path(
        "app/modules/platform/document_lifecycle/exact_file_version_read_port.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "FileVersion.is_current =",
        "FileAsset.current_version_id =",
        "FileBinding.is_current =",
        "material.current_version_id =",
    )
    assert not any(item in source for item in forbidden)
