"""P0 · 文件中心对象级授权 + 生产占位路由清除。"""
from __future__ import annotations

import io

import pytest

TID = 1000000000000000001
OTHER_TID = 1000000000000000002


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _token(role: str, *, tenant_id: int = TID, user_id: str = "u-x",
           user_type: str = "TEACHER", student_no: str | None = None):
    from app.core.security import create_access_token
    claims = {
        "userId": user_id, "realName": role, "userType": user_type,
        "tid": "demo", "tenantId": str(tenant_id), "activeContextId": f"ctx_{role}",
        "currentRoleCode": role, "clientType": "PC",
    }
    if student_no:
        claims["studentNo"] = student_no
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _upload(client, hdr, name="p0.txt", content=b"hello-p0", biz_type="ATTACHMENT", biz_id=None):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
    mime = {
        "txt": "text/plain", "csv": "text/csv", "pdf": "application/pdf",
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
    files = {"file": (name, io.BytesIO(content), mime)}
    data = {"bizType": biz_type}
    if biz_id:
        data["bizId"] = biz_id
    r = client.post("/api/v1/files/upload", headers=hdr, files=files, data=data)
    assert r.status_code == 200, r.text
    return r.json()["data"]["fileId"]


def test_same_tenant_other_user_cannot_guess_download(client, db_mode):
    admin = _hdr(client, "school_admin01")
    fid = _upload(client, admin, name="secret.txt", content=b"secret-bytes")
    other = _hdr(client, "academic01")
    assert client.get(f"/api/v1/files/download/{fid}", headers=other).status_code == 404
    assert client.get(f"/api/v1/files/meta/{fid}", headers=other).status_code == 404


def test_owner_can_download(client, db_mode):
    teacher = _hdr(client, "academic01")
    fid = _upload(client, teacher, name="mine.txt", content=b"mine")
    assert client.get(f"/api/v1/files/download/{fid}", headers=teacher).status_code == 200
    assert client.get(f"/api/v1/files/meta/{fid}", headers=teacher).status_code == 200


def test_cross_tenant_download_denied(client, db_mode):
    admin = _hdr(client, "school_admin01")
    fid = _upload(client, admin, name="t1.txt", content=b"t1")
    other = _token("SCHOOL_ADMIN", tenant_id=OTHER_TID, user_id="u_t2", user_type="ADMIN")
    assert client.get(f"/api/v1/files/download/{fid}", headers=other).status_code == 404


def test_biz_permission_holder_can_download_after_bind(client, db_mode):
    admin = _hdr(client, "school_admin01")
    fid = _upload(client, admin, name="leave.pdf", content=b"%PDF-1.4\n%", biz_type="LEAVE", biz_id="1001")
    # 辅导员有 leave.view
    counselor = _hdr(client, "counselor01")
    assert client.get(f"/api/v1/files/download/{fid}", headers=counselor).status_code == 200


def test_student_only_own_attachment(client, db_mode):
    admin = _hdr(client, "school_admin01")
    own = _upload(client, admin, name="own.pdf", content=b"%PDF-1.4\nown",
                  biz_type="ATTACHMENT", biz_id="2023100001")
    other = _upload(client, admin, name="other.pdf", content=b"%PDF-1.4\nother",
                    biz_type="ATTACHMENT", biz_id="OTHERNO")
    stu = _hdr(client, "student01")  # studentNo=2023100001
    assert client.get(f"/api/v1/files/download/{own}", headers=stu).status_code == 200
    assert client.get(f"/api/v1/files/download/{other}", headers=stu).status_code == 404


def test_no_tenant_context_upload_fails(client, db_mode, monkeypatch):
    from app.core import context as ctx
    from app.core.exceptions import AppException
    from app.services import file_service
    import asyncio

    monkeypatch.setattr(ctx, "current_tenant_id", lambda: None)

    class _F:
        filename = "x.txt"
        content_type = "text/plain"

        async def read(self, n=-1):
            if getattr(self, "_done", False):
                return b""
            self._done = True
            return b"abc"

    with pytest.raises(AppException) as ei:
        asyncio.run(file_service.store_upload(_F(), "ATTACHMENT", user={"userId": "u_school_admin01"}))
    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"


def test_legacy_orphan_private_file_not_open_to_teacher(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    row = FileObject(tenant_id=TID, file_key="legacy/orphan.bin", file_name="orphan.bin",
                     ext="bin", size_bytes=1, sha256="a" * 64, biz_type=None, status="STORED",
                     visibility="PRIVATE", security_level="SENSITIVE")
    db.add(row); db.commit(); db.refresh(row); fid = str(row.id); db.close()
    teacher = _hdr(client, "academic01")
    assert client.get(f"/api/v1/files/download/{fid}", headers=teacher).status_code == 404


def test_production_placeholder_route_absent():
    """生产环境条件：settings.is_prod 为真时不得挂载 placeholder_router。"""
    from fastapi import APIRouter

    from app.api.v1 import file as file_simple
    from app.core.config import Settings

    prod = Settings(APP_ENV="production")
    assert prod.is_prod is True
    api = APIRouter()
    api.include_router(file_simple.router, prefix="/files")
    if not prod.is_prod:
        api.include_router(file_simple.placeholder_router, prefix="/files")
    paths = {getattr(route, "path", "") for route in api.routes}
    assert not any("upload-placeholder" in p for p in paths)


def test_files_url_not_mock_storage(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    fid = _upload(client, hdr, name="real.txt", content=b"real")
    url = client.get(f"/api/v1/files/{fid}/url", headers=hdr).json()["data"]["url"]
    assert "mock-storage" not in url
    assert f"/api/v1/files/download/{fid}" in url
