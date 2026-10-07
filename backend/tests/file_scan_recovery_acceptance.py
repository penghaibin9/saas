#!/usr/bin/env python3
"""Real MySQL + real ClamAV recovery acceptance for one quarantined file."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

import file_scan_mysql_acceptance as base


def main() -> None:
    from app.core.context import set_current_user, set_tenant
    from app.services.clamav_client import ClamAVClient
    from app.services.file_scan_config import get_file_scan_config
    from app.services.file_scan_service import assert_file_ready_for_business
    from app.services.storage import reset_backend

    required = ("DATABASE_URL", "UPLOAD_DIR", "CLAMAV_HOST", "CLAMAV_PORT")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("missing recovery acceptance environment")

    set_tenant({"tenantId": base.TENANT_ID, "tenantCode": "file-stage1"})
    actor = {"userId": base.USER_ID, "userType": "SCHOOL_ADMIN", "permissions": ["*"]}
    set_current_user(actor)
    reset_backend()
    base.cleanup()
    base.ensure_acceptance_tenant()

    try:
        item = base.upload(
            "recovery.txt", b"clean payload that waits through scanner outage",
            "text/plain", "ATTACHMENT",
        )
        assert item["status"] == "QUARANTINED" and item["scanStatus"] == "PENDING"
        base.assert_gate(item["fileId"], "FILE_NOT_READY")

        config = get_file_scan_config()
        unavailable = ClamAVClient(replace(config, host="127.0.0.1", port=9, connect_timeout=0.1))
        failed = base.run_worker_until_result("security-runtime-outage", client=unavailable)
        assert failed.get("error"), failed
        after_outage = base.row(item["fileId"])
        assert after_outage.status == "QUARANTINED"
        assert after_outage.storage_zone == "QUARANTINE"
        assert after_outage.scan_status in {"PENDING", "ERROR"}

        recovered = base.run_worker_until_result(
            "security-runtime-recovered", client=ClamAVClient(config), timeout_seconds=6.0,
        )
        base.assert_scan_result(recovered, "CLEAN")
        final = base.row(item["fileId"])
        assert final.status == "AVAILABLE"
        assert final.storage_zone == "ACTIVE"
        assert final.scan_status == "CLEAN"
        assert_file_ready_for_business(item["fileId"], user=actor)

        output = Path(os.environ.get("SECURITY_RUNTIME_ARTIFACT_DIR", "artifacts/security-runtime"))
        output.mkdir(parents=True, exist_ok=True)
        (output / "clamav-recovery.json").write_text(json.dumps({
            "realMysql": True,
            "realClamavRecovery": True,
            "outageKeptFileQuarantined": True,
            "recoveredScanStatus": "CLEAN",
            "recoveredFileStatus": "AVAILABLE",
            "fixtureOnly": True,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("real ClamAV outage-to-recovery acceptance passed")
    finally:
        base.cleanup()
        shutil.rmtree(Path(os.environ["UPLOAD_DIR"]), ignore_errors=True)


if __name__ == "__main__":
    main()
