"""Read-only MySQL verification for the real-browser weekly-report return/resubmit journey."""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, WeeklyReport

TENANT_ID = 1000000000000000007


def required(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing to inspect production/staging database")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("weekly-report verifier only accepts a local database")


def main() -> int:
    assert_safe_target()
    report_id = int(required("E2E_INTERNSHIP_WEEKLY_ID"))
    expected_week = int(required("E2E_INTERNSHIP_WEEKLY_WEEK"))
    first_work = required("E2E_INTERNSHIP_WEEKLY_FIRST_WORK")
    final_work = required("E2E_INTERNSHIP_WEEKLY_FINAL_WORK")
    reject_reason = required("E2E_INTERNSHIP_WEEKLY_REJECT_REASON")

    db = get_sessionmaker()()
    try:
        row = db.get(WeeklyReport, report_id)
        if not row or row.tenant_id != TENANT_ID or row.is_deleted:
            raise AssertionError("browser-created weekly report missing from MySQL")
        if row.week_number != expected_week:
            raise AssertionError(f"week_number={row.week_number}, expected {expected_week}")
        if row.status != "APPROVED":
            raise AssertionError(f"status={row.status}, expected APPROVED")
        if int(row.report_version or 0) < 2:
            raise AssertionError(f"report_version={row.report_version}, expected >=2")
        if row.work_content != final_work:
            raise AssertionError("final work content does not match browser resubmit")

        trails = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "REPORT",
            InternshipAuditTrail.target_id == report_id,
        ).order_by(InternshipAuditTrail.id)).all()
        actions = [trail.action for trail in trails]
        required_actions = [
            "SUBMIT_VERSIONED", "REVIEW_RETURN", "RESUBMIT_VERSIONED", "REVIEW_APPROVE"
        ]
        for action in required_actions:
            if action not in actions:
                raise AssertionError(f"missing weekly audit action {action}: {actions}")

        returned = next((trail for trail in trails if trail.action == "REVIEW_RETURN"), None)
        detail = (returned.detail_json or {}) if returned else {}
        if str(detail.get("comment") or "") != reject_reason:
            raise AssertionError("REVIEW_RETURN did not preserve browser-entered rejection reason")
        snapshot = detail.get("snapshot") or {}
        if str(snapshot.get("work") or "") != first_work:
            raise AssertionError("REVIEW_RETURN snapshot did not preserve first-version work content")

        evidence = {
            "tenantId": str(row.tenant_id),
            "reportId": str(row.id),
            "internshipId": str(row.internship_id),
            "week": int(row.week_number),
            "status": row.status,
            "reportVersion": int(row.report_version or 0),
            "version": int(row.version or 0),
            "auditActions": actions,
            "returnComment": detail.get("comment"),
            "snapshotWork": snapshot.get("work"),
            "finalWork": row.work_content,
        }
        print("[internship-weekly-db-audit] DB_EVIDENCE_OK")
        print(json.dumps(evidence, ensure_ascii=False, default=str, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
