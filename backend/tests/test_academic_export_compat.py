from __future__ import annotations

import io
from pathlib import Path

from openpyxl import Workbook

from app.core.config import settings
from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models.data_exchange import ExportJob
from app.models.file import FileObject
from app.modules.academic_affairs.routers.academic_affairs_bundle import build_router
from app.modules.academic_affairs.routers import academic_export_compat_router as compat_router
from app.modules.academic_affairs.services.academic_export_compat_service import task_backed_file_response
from app.services import storage

TENANT_ID = 1000000000000000001


def _effective_routes(routes):
    """FastAPI 0.137+ 将 include_router 保留为树；展开后继续验证真实路由顺序。"""
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:  # pragma: no cover - 兼容旧 FastAPI
        iter_route_contexts = None
    if iter_route_contexts is not None:
        yield from iter_route_contexts(routes)
        return
    for route in routes:
        if hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()
        else:
            yield route


def _xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["学号", "姓名"])
    sheet.append(["20260001", "测试学生"])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _user() -> dict:
    return {
        "tenantId": str(TENANT_ID),
        "userId": "81001",
        "realName": "教务导出测试",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "dataScope": "ALL",
        "permissions": ["*"],
    }


def test_task_backed_response_persists_file_job_and_download(db_mode, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "FILE_STORAGE_BACKEND", "local", raising=False)
    storage.reset_backend()
    user = _user()
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user(user)

    response = task_backed_file_response(
        content=_xlsx(),
        filename="compat_roster.xlsx",
        export_type="ACADEMIC_ROSTER",
        purpose="阶段七兼容导出验收",
        user=user,
        parameters={"status": "ACTIVE"},
    )
    assert response.headers["x-file-center-contract"] == "EXPORT_JOB"
    job_id = int(response.headers["x-export-job-id"])
    assert Path(response.path).exists()

    db = get_sessionmaker()()
    try:
        job = db.get(ExportJob, job_id)
        assert job is not None
        assert job.module_code == "ACADEMIC_AFFAIRS"
        assert job.adapter_type == "ACADEMIC_COMPAT_EXPORT"
        assert job.status == "SUCCEEDED"
        assert job.row_count == 1
        assert job.downloaded_count == 1
        assert job.expires_at is not None
        file_row = db.get(FileObject, int(job.file_object_id))
        assert file_row is not None
        assert file_row.status == "AVAILABLE"
        assert file_row.scan_status == "NOT_REQUIRED"
        assert file_row.file_name == "compat_roster.xlsx"
    finally:
        db.close()
        storage.reset_backend()
        set_current_user(None)
        set_tenant(None)


def test_all_high_frequency_legacy_exports_have_task_backed_adapters():
    expected = {
        ("/academic-affairs/roster/export", "POST"),
        ("/academic-affairs/registration/archive/{batchId}/export", "POST"),
        ("/academic-affairs/registration/unregistered/export", "POST"),
        ("/academic-affairs/schedule/export", "POST"),
        ("/academic-affairs/students/{studentId}/transcript/export", "POST"),
        ("/academic-affairs/grade-views/analysis/export", "POST"),
        ("/academic-affairs/stats/export", "POST"),
        ("/academic-affairs/selection/batches/{batchId}/conflict-report/export", "POST"),
        ("/academic-affairs/selection/archive/{batchId}/export", "POST"),
        ("/academic-affairs/makeup/stats/export", "POST"),
        ("/academic-affairs/evaluation/batches/{bid}/export", "POST"),
        ("/academic-affairs/quality/reports/export", "POST"),
        ("/academic-affairs/quality/archive/export", "GET"),
        ("/academic-affairs/archive/batches/{bid}/export", "GET"),
        ("/academic-affairs/archive/batches/{bid}/items/{category}/export", "GET"),
    }
    actual = {
        (route.path, method)
        for route in _effective_routes(compat_router.router.routes)
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert expected <= actual


def test_compatibility_routes_precede_historical_streaming_routes():
    router = build_router()
    watched = {
        "/academic-affairs/roster/export",
        "/academic-affairs/registration/archive/{batchId}/export",
        "/academic-affairs/schedule/export",
        "/academic-affairs/students/{studentId}/transcript/export",
        "/academic-affairs/stats/export",
        "/academic-affairs/archive/batches/{bid}/export",
    }
    effective = list(_effective_routes(router.routes))
    for path in watched:
        matches = [route for route in effective if getattr(route, "path", None) == path]
        assert len(matches) >= 2, path
        assert matches[0].endpoint.__module__.endswith("academic_export_compat_router"), path
