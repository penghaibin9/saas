"""Stage 1 real MySQL + real ClamAV acceptance; executed as a standalone script in Actions."""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import zipfile
from dataclasses import replace
from pathlib import Path

from sqlalchemy import delete, select

EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)
TENANT_ID = 990000000000000025
USER_ID = 990000000000000026


class AsyncUpload:
    def __init__(self, filename: str, data: bytes, content_type: str):
        self.filename = filename
        self.content_type = content_type
        self._stream = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def docx_bytes() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document>Hello</document>")
    return out.getvalue()


def zip_bytes() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("evidence/readme.txt", "clean evidence")
    return out.getvalue()


def upload(filename: str, data: bytes, content_type: str, biz_type: str) -> dict:
    from app.services.file_service import store_upload
    return asyncio.run(store_upload(
        AsyncUpload(filename, data, content_type),
        biz_type,
        user={"userId": USER_ID, "userType": "SCHOOL_ADMIN", "permissions": ["*"]},
    ))


def row(file_id: str):
    from app.db.session import get_sessionmaker
    from app.models.file import FileObject
    db = get_sessionmaker()()
    try:
        return db.get(FileObject, int(file_id))
    finally:
        db.close()


def assert_gate(file_id: str, code: str) -> None:
    from app.core.exceptions import AppException
    from app.services.file_scan_service import assert_file_ready_for_business
    try:
        assert_file_ready_for_business(
            file_id,
            user={"userId": USER_ID, "userType": "SCHOOL_ADMIN", "permissions": ["*"]},
        )
    except AppException as exc:
        assert exc.code == code, (exc.code, exc.message)
    else:
        raise AssertionError(f"expected gate error {code}")


def cleanup() -> None:
    from app.db.session import get_sessionmaker
    from app.models.file import FileJob, FileObject, FileScanRecord, FileUploadSession
    db = get_sessionmaker()()
    try:
        db.execute(delete(FileScanRecord).where(FileScanRecord.tenant_id == TENANT_ID))
        db.execute(delete(FileJob).where(FileJob.tenant_id == TENANT_ID))
        db.execute(delete(FileUploadSession).where(FileUploadSession.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()


def main() -> None:
    required = ("DATABASE_URL", "UPLOAD_DIR", "CLAMAV_HOST", "CLAMAV_PORT")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing acceptance env: {missing}")

    from app.core.context import set_current_user, set_tenant
    from app.services.clamav_client import ClamAVClient
    from app.services.file_scan_config import get_file_scan_config
    from app.services.file_scan_service import assert_file_ready_for_business, process_next_scan_job
    from app.services.storage import reset_backend

    set_tenant({"tenantId": TENANT_ID, "tenantCode": "file-stage1"})
    actor = {"userId": USER_ID, "userType": "SCHOOL_ADMIN", "permissions": ["*"]}
    set_current_user(actor)
    reset_backend()
    cleanup()

    try:
        infected = upload("eicar.txt", EICAR, "text/plain", "ATTACHMENT")
        assert infected["status"] == "QUARANTINED"
        assert infected["scanStatus"] == "PENDING"
        assert_gate(infected["fileId"], "FILE_NOT_READY")
        result = process_next_scan_job("acceptance-real-clamav")
        assert result["scanStatus"] == "INFECTED", result
        infected_row = row(infected["fileId"])
        assert infected_row.status == "REJECTED"
        assert infected_row.scan_status == "INFECTED"
        assert_gate(infected["fileId"], "FILE_REJECTED")

        office = upload(
            "clean.docx",
            docx_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "GRADUATION_MATERIAL",
        )
        assert office["status"] == "QUARANTINED"
        assert_gate(office["fileId"], "FILE_NOT_READY")
        result = process_next_scan_job("acceptance-real-clamav")
        assert result["scanStatus"] == "CLEAN", result
        office_row = row(office["fileId"])
        assert office_row.status == "AVAILABLE"
        assert office_row.storage_zone == "ACTIVE"
        assert_file_ready_for_business(office["fileId"], user=actor)

        package = upload("evidence.zip", zip_bytes(), "application/zip", "ARCHIVE_PACKAGE")
        assert package["status"] == "QUARANTINED"
        result = process_next_scan_job("acceptance-real-clamav")
        assert result["scanStatus"] == "CLEAN", result
        assert row(package["fileId"]).status == "AVAILABLE"

        outage = upload("outage.txt", b"clean but scanner unavailable", "text/plain", "ATTACHMENT")
        base = get_file_scan_config()
        unavailable = ClamAVClient(replace(base, host="127.0.0.1", port=9, connect_timeout=0.1))
        result = process_next_scan_job("acceptance-outage", client=unavailable)
        assert result.get("error"), result
        outage_row = row(outage["fileId"])
        assert outage_row.status == "QUARANTINED"
        assert outage_row.storage_zone == "QUARANTINE"
        assert outage_row.scan_status in {"PENDING", "ERROR"}
        expected = "FILE_NOT_READY" if outage_row.scan_status == "PENDING" else "FILE_SCAN_UNAVAILABLE"
        assert_gate(outage["fileId"], expected)

        print("Stage 1 MySQL + ClamAV acceptance passed")
    finally:
        cleanup()
        shutil.rmtree(Path(os.environ["UPLOAD_DIR"]), ignore_errors=True)


if __name__ == "__main__":
    main()
