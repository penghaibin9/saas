"""公共文件存储治理 worker。

默认每小时逐租户执行：历史保留期补算、过期上传会话两阶段清理、到期文件两阶段清理、异常快照。
任一租户失败会记账并继续下一个租户，不因单校配置问题阻塞全平台。

运行：python -m app.workers.file_governance_worker --once
"""
from __future__ import annotations

import argparse
import json
import logging
import time

from sqlalchemy import text

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.services.file_storage_cleanup_service import cleanup_expired
from app.services.file_storage_governance_service import anomaly_snapshot, backfill_retention
from app.services.file_upload_session_cleanup_service import expire_upload_sessions
from app.services.storage import reset_backend

log = logging.getLogger("file-governance-worker")


def _tenant_ids(explicit: int | None = None) -> list[int]:
    if explicit:
        return [int(explicit)]
    db = get_sessionmaker()()
    try:
        values = db.execute(text(
            "SELECT tenant_id FROM t_file_object "
            "UNION SELECT tenant_id FROM t_tenant_storage_quota "
            "UNION SELECT tenant_id FROM t_file_retention_policy "
            "ORDER BY tenant_id"
        )).scalars().all()
        return sorted({int(value) for value in values if int(value or 0) > 0})
    finally:
        db.close()


def process_tenant(tenant_id: int, *, dry_run: bool, limit: int) -> dict:
    set_tenant({"tenantId": str(tenant_id)})
    set_current_user({
        "userId": "0",
        "userType": "SYSTEM",
        "realName": "文件治理 Worker",
        "currentRoleCode": "SYSTEM_WORKER",
    })
    reset_backend()
    try:
        backfill = backfill_retention(tenant_id=tenant_id, limit=limit)
        sessions = expire_upload_sessions(tenant_id=tenant_id, limit=limit)
        cleanup = cleanup_expired(tenant_id=tenant_id, dry_run=dry_run, limit=limit)
        anomalies = anomaly_snapshot(tenant_id=tenant_id)
        status = "PARTIAL_FAILED" if sessions.get("failed") or cleanup.get("failed") else "SUCCEEDED"
        return {
            "tenantId": tenant_id,
            "status": status,
            "backfill": backfill,
            "uploadSessions": sessions,
            "cleanup": cleanup,
            "anomalies": anomalies,
        }
    finally:
        reset_backend()
        set_current_user(None)
        set_tenant(None)


def run(*, once: bool, tenant_id: int | None, dry_run: bool, limit: int, interval_seconds: int) -> int:
    failures = 0
    while True:
        ids = _tenant_ids(tenant_id)
        for value in ids:
            try:
                result = process_tenant(value, dry_run=dry_run, limit=limit)
                if result.get("status") != "SUCCEEDED":
                    failures += 1
                    log.error("governance partial failure: %s", json.dumps(result, ensure_ascii=False, default=str))
                else:
                    log.info("governance result: %s", json.dumps(result, ensure_ascii=False, default=str))
            except Exception as exc:  # noqa: BLE001 - one tenant must not stop others
                failures += 1
                log.exception("tenant %s governance failed: %s", value, exc)
        if once:
            return failures
        time.sleep(max(3600, interval_seconds))


def main() -> int:
    parser = argparse.ArgumentParser(description="跨租户文件保留、清理与异常治理 worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--dry-run", action="store_true", help="只预演到期文件；过期未完成上传仍按两阶段流程清理")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--interval-seconds", type=int, default=3600)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    failures = run(
        once=args.once,
        tenant_id=args.tenant_id,
        dry_run=args.dry_run,
        limit=max(1, min(args.limit, 5000)),
        interval_seconds=max(3600, args.interval_seconds),
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
