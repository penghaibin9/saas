"""P1：真实写路径缺租户上下文必须失败。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services import file_service_legacy, import_export_service
from app.services.file_service import _require_tenant_id


def test_file_require_tenant_without_context(monkeypatch):
    # file_service is now a facade that re-exports the legacy function object.
    # The function's globals still live in file_service_legacy, so patch the
    # authoritative module rather than a facade attribute that it never reads.
    monkeypatch.setattr(file_service_legacy, "current_tenant_id", lambda: None)
    with pytest.raises(AppException) as ei:
        _require_tenant_id()
    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"


def test_import_export_tid_without_context(monkeypatch):
    monkeypatch.setattr("app.services.import_export_service.current_tenant_id", lambda: None)
    with pytest.raises(AppException) as ei:
        import_export_service._tid()
    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"


def test_import_export_tid_with_context(monkeypatch):
    monkeypatch.setattr("app.services.import_export_service.current_tenant_id",
                        lambda: "1000000000000000099")
    assert import_export_service._tid() == 1000000000000000099
