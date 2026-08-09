#!/usr/bin/env python3
"""Fail when any tenant has unresolved Stage C1 academic fact reconciliation."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.core.context import set_tenant
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant
from app.modules.academic_affairs.services.academic_affairs_fact_reconciliation_service import (
    scan_current_projection,
)

EVIDENCE_PATH = Path("test-results/stage-c1-reconciliation.json")
ANNOTATION_FILE = "backend/scripts/audit_stage_c1_academic_facts.py"


def _compact(value, limit: int = 4):
    if isinstance(value, list):
        return value[:limit]
    return value


def _write_evidence(payload: dict) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, default=str, indent=2), encoding="utf-8"
    )


def _error_annotation(title: str, message: str) -> None:
    # file/line is intentional: GitHub persists file-scoped workflow commands as
    # check-run annotations, while generic ::error output is not reliably queryable.
    safe_title = str(title).replace("\n", " ")
    safe_message = str(message).replace("\n", " ")
    print(
        f"::error file={ANNOTATION_FILE},line=1,col=1,title={safe_title}::{safe_message}"
    )


def main() -> int:
    if not db_enabled():
        raise RuntimeError("Stage C1 reconciliation audit requires DB_ENABLED=true")
    db = get_sessionmaker()()
    try:
        tenant_ids = [int(x) for x in db.scalars(select(Tenant.id)).all()]
    finally:
        db.close()

    unresolved = 0
    results = []
    for tenant_id in tenant_ids:
        set_tenant({"tenantId": str(tenant_id)})
        tenant_db = get_sessionmaker()()
        try:
            result = scan_current_projection(tenant_db)
            results.append(result)
            unresolved += int(result["unresolved"])
            if int(result["unresolved"]):
                details = result.get("details") or {}
                diagnostic = {
                    "tenantId": result.get("tenantId"),
                    "activeProfiles": result.get("activeProfiles"),
                    "missingCurrentFact": result.get("missingCurrentFact"),
                    "overlappingCurrentFact": result.get("overlappingCurrentFact"),
                    "projectionDrift": result.get("projectionDrift"),
                    "missingStudentIds": _compact(details.get("missingStudentIds") or []),
                    "overlapStudentIds": _compact(details.get("overlapStudentIds") or []),
                    "drifts": _compact(details.get("drifts") or []),
                }
                _error_annotation(
                    "Stage C1 academic fact reconciliation",
                    json.dumps(diagnostic, ensure_ascii=False, default=str),
                )
        finally:
            tenant_db.close()
            set_tenant(None)

    payload = {"tenants": results, "unresolved": unresolved}
    _write_evidence(payload)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if unresolved:
        _error_annotation(
            "Stage C1 academic fact reconciliation total",
            f"unresolved={unresolved}",
        )
        return 1
    print("Stage C1 academic fact reconciliation OK: unresolved=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
