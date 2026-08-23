"""Read-only MySQL verifier for the real-browser internship batch lifecycle audit."""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, InternshipBatch

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
        raise SystemExit("internship batch verifier only accepts a local database")


def assert_order(actions: list[str], required_actions: list[str]) -> None:
    cursor = -1
    for action in required_actions:
        try:
            cursor = actions.index(action, cursor + 1)
        except ValueError as exc:
            raise AssertionError(f"missing/out-of-order batch audit action {action}: {actions}") from exc


def main() -> int:
    assert_safe_target()
    batch_id = int(required("E2E_INTERNSHIP_BATCH_ID"))
    batch_no = required("E2E_INTERNSHIP_BATCH_NO")
    batch_name = required("E2E_INTERNSHIP_BATCH_NAME")
    expected_remark = required("E2E_INTERNSHIP_BATCH_REMARK")

    db = get_sessionmaker()()
    try:
        row = db.get(InternshipBatch, batch_id)
        if not row or row.tenant_id != TENANT_ID or row.is_deleted:
            raise AssertionError("browser-created internship batch missing from MySQL")
        if row.batch_no != batch_no or row.batch_name != batch_name:
            raise AssertionError(
                f"batch identity mismatch: id={row.id} no={row.batch_no!r} name={row.batch_name!r}"
            )
        if row.status != "CLOSED":
            raise AssertionError(f"status={row.status}, expected CLOSED after browser lifecycle")
        if row.previous_status != "RUNNING":
            raise AssertionError(f"previous_status={row.previous_status}, expected RUNNING")
        if int(row.planned_count or 0) != 37:
            raise AssertionError(f"planned_count={row.planned_count}, expected browser-edited 37")
        if str(row.remark or "") != expected_remark:
            raise AssertionError("browser-edited remark was not persisted")

        stages = row.stage_config or []
        if not any(
            str(stage.get("code") or "") == "E2E_PREP"
            and str(stage.get("name") or "") == "浏览器岗前准备"
            for stage in stages if isinstance(stage, dict)
        ):
            raise AssertionError(f"browser stage config missing from MySQL: {stages}")

        rules = row.rules_config or {}
        checkin = rules.get("checkin") or {}
        if int(checkin.get("geofenceRadiusM") or 0) != 650:
            raise AssertionError(f"geofenceRadiusM={checkin.get('geofenceRadiusM')}, expected 650")
        evaluation = rules.get("evaluation") or {}
        weights = [
            float(evaluation.get("enterpriseWeight") or 0),
            float(evaluation.get("teacherWeight") or 0),
            float(evaluation.get("selfWeight") or 0),
        ]
        if abs(sum(weights) - 1.0) > 1e-9:
            raise AssertionError(f"evaluation weights not normalized to 1.0: {weights}")

        same_no = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == TENANT_ID,
            InternshipBatch.batch_no == batch_no,
            InternshipBatch.is_deleted.is_(False),
        )).all()
        if len(same_no) != 1 or same_no[0].id != batch_id:
            raise AssertionError(
                f"duplicate browser submit created extra batch rows: {[str(item.id) for item in same_no]}"
            )

        trails = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "BATCH",
            InternshipAuditTrail.target_id == batch_id,
        ).order_by(InternshipAuditTrail.id)).all()
        actions = [trail.action for trail in trails]
        assert_order(actions, ["CREATE", "UPDATE", "ACTIVATE", "CLOSE"])

        if not row.last_transition_at or not row.last_transition_by:
            raise AssertionError("batch transition actor/time missing after browser state transitions")

        evidence = {
            "tenantId": str(row.tenant_id),
            "batchId": str(row.id),
            "batchNo": row.batch_no,
            "batchName": row.batch_name,
            "status": row.status,
            "previousStatus": row.previous_status,
            "plannedCount": int(row.planned_count or 0),
            "version": int(row.version or 0),
            "stageConfig": stages,
            "checkinRule": checkin,
            "evaluationWeights": weights,
            "duplicateRowCount": len(same_no),
            "auditActions": actions,
            "lastTransitionBy": row.last_transition_by,
            "lastTransitionAt": row.last_transition_at,
        }
        print("[internship-batch-db-audit] DB_EVIDENCE_OK")
        print(json.dumps(evidence, ensure_ascii=False, default=str, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
