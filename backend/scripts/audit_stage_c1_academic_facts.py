#!/usr/bin/env python3
"""Fail when any active tenant has unresolved Stage C1 academic fact reconciliation."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.core.context import set_tenant
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant
from app.modules.academic_affairs.services.academic_affairs_fact_reconciliation_service import (
    scan_current_projection,
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
        finally:
            tenant_db.close()
            set_tenant(None)

    print(json.dumps({"tenants": results, "unresolved": unresolved}, ensure_ascii=False, default=str))
    if unresolved:
        print(f"::error::Stage C1 academic fact reconciliation unresolved={unresolved}")
        return 1
    print("Stage C1 academic fact reconciliation OK: unresolved=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
