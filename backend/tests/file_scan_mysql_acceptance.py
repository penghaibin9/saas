"""Stage 1 real MySQL + real ClamAV acceptance; executed as a standalone script in Actions."""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import time
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


def queue_snapshot() -> list[dict]:
    from app.db.session import get_sessionmaker
    from app.models.file import FileJob
    db = get_sessionmaker()()
    try:
        jobs = db.scalars(select(FileJob).where(
            FileJob.tenant_id == TENANT_ID,
            FileJob.is_deleted.is_(False),
        ).order_by(FileJob.id)).all()
        return [{
            "id": item.id,
            "fileId": item.file_id,
            "status": item.status,
            "attempts": item.attempts,
            "maxAttempts": item.max_attempts,
            "availableAt": item.available_at.isoformat() if item.available_at else None,
            "lockedAt": item.locked_at.isoformat() if item.locked_at else None,
            "lastError": item.last_error,
        } for item in jobs]
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
        # 冻结中心对尚未可用、已拒绝或扫描异常的对象允许统一收敛为 404，
        # 防止通过业务提交/绑定入口枚举文件；下方仍以数据库状态严格校验真实扫描结论。
        accepted = {code, "DATA_NOT_FOUND"}
        assert exc.code in accepted, (exc.code, exc.message, sorted(accepted))
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


def run_worker_until_result(worker_id: str, *, client=None, timeout_seconds: float = 3.0) -> dict:
    """模拟常驻 worker 的真实轮询，兼容 MySQL DATETIME 秒级精度。"""
    from app.services.file_scan_service import process_next_scan_job

    deadline = time.monotonic() + timeout_seconds
    last = {"processed": False, "reason": "not-started"}
    while time.monotonic() < deadline:
        last = process_next_scan_job(worker_id, client=client)
        if last.get("processed") or last.get("error"):
            return last
        time.sleep(0.2)
    return last


def assert_scan_result(result: dict, expected: str) -> None:
    assert result.get("scanStatus") == expected, (
        f"expected {expected}, worker returned: {result!r}; queue={queue_snapshot()!r}"
    )


def main() -> None:
    required = ("DATABASE_URL", "UPLOAD_DIR", "CLAMAV_HOST", "CLAMAV_PORT")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing acceptance env: {missing}")

    from app.core.context import set_current_user, set_tenant
    from app.services.clamav_client import ClamAVClient
    from app.services.file_scan_config import get_file_scan_config
    from app.services.file_scan_service import assert_file_ready_for_business
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
        result = run_worker_until_result("acceptance-real-clamav")
        assert_scan_result(result, "INFECTED")
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
        assert office["scanRequired"] is True
        assert_gate(office["fileId"], "FILE_NOT_READY")
        result = run_worker_until_result("acceptance-real-clamav")
        assert_scan_result(result, "CLEAN")
        office_row = row(office["fileId"])
        assert office_row.status == "AVAILABLE"
        assert office_row.storage_zone == "ACTIVE"
        assert_file_ready_for_business(office["fileId"], user=actor)

        package = upload("evidence.zip", zip_bytes(), "application/zip", "ARCHIVE_PACKAGE")
        assert package["status"] == "QUARANTINED"
        assert package["scanRequired"] is True
        result = run_worker_until_result("acceptance-real-clamav")
        assert_scan_result(result, "CLEAN")
        assert row(package["fileId"]).status == "AVAILABLE"

        outage = upload("outage.txt", b"clean but scanner unavailable", "text/plain", "ATTACHMENT")
        base = get_file_scan_config()
        unavailable = ClamAVClient(replace(base, host="127.0.0.1", port=9, connect_timeout=0.1))
        result = run_worker_until_result("acceptance-outage", client=unavailable)
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
