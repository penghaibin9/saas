"""P1：真实写路径缺租户上下文必须失败。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services import import_export_service
from app.services.file_service import _require_tenant_id


def test_file_require_tenant_without_context(monkeypatch):
    monkeypatch.setattr("app.services.file_service.db_enabled", lambda: True)
    monkeypatch.setattr("app.services.file_service.current_tenant_id", lambda: None)
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
