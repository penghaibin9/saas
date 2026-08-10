"""P1：真实写路径缺租户上下文必须失败。"""
from __future__ import annotations

import asyncio

import pytest

from app.core.exceptions import AppException
from app.services import file_service, import_export_service
from app.services.file_service import _require_tenant_id


def test_file_require_tenant_without_context(monkeypatch):
    monkeypatch.setattr("app.services.file_service.db_enabled", lambda: True)
    monkeypatch.setattr("app.services.file_service.current_tenant_id", lambda: None)
    with pytest.raises(AppException) as ei:
        _require_tenant_id()
    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"


def test_file_facade_store_bytes_without_context_fails_before_legacy_write(monkeypatch):
    called = False

    def _unexpected_legacy_write(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(file_service, "current_tenant_id", lambda: None)
    monkeypatch.setattr(file_service, "_legacy_store_bytes", _unexpected_legacy_write)

    with pytest.raises(AppException) as ei:
        file_service.store_bytes(b"tenantless", "tenantless.txt")

    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"
    assert called is False


def test_file_facade_upload_without_context_fails_before_legacy_write(monkeypatch):
    called = False

    async def _unexpected_legacy_upload(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(file_service, "current_tenant_id", lambda: 0)
    monkeypatch.setattr(file_service, "_legacy_store_upload", _unexpected_legacy_upload)

    with pytest.raises(AppException) as ei:
        asyncio.run(file_service.store_upload(object()))

    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"
    assert called is False


def test_import_export_tid_without_context(monkeypatch):
    monkeypatch.setattr("app.services.import_export_service.current_tenant_id", lambda: None)
    with pytest.raises(AppException) as ei:
        import_export_service._tid()
    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"


def test_import_export_tid_with_context(monkeypatch):
    monkeypatch.setattr("app.services.import_export_service.current_tenant_id",
                        lambda: "1000000000000000099")
    assert import_export_service._tid() == 1000000000000000099
