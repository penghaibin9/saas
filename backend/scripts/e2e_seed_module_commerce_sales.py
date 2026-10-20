"""Create isolated M3 sales identities only; all catalog/order writes occur in UI."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.db.session import get_sessionmaker
from app.models import PlatformConfig, Tenant
from app.modules.platform.services.platform_access_governance_legacy import DUTY_CAPABILITIES
from e2e_seed_control_plane_role_projection import PLATFORM_TENANT_ID, _browser_session, _platform_user
from e2e_seed_playwright_tenants import assert_safe_target


def main() -> None:
    assert_safe_target()
    head = os.environ.get("E2E_EXPECTED_SHA", "")
    if len(head) < 7:
        raise RuntimeError("E2E_EXPECTED_SHA is required")
    schools = []
    with get_sessionmaker()() as db:
        if db.get(Tenant, PLATFORM_TENANT_ID) is None:
            db.add(Tenant(id=PLATFORM_TENANT_ID, tenant_code="platform", school_name="平台运营中心", status="ACTIVE"))
        for offset in (1, 2):
            tid = 1000000000000047000 + offset
            code = f"m3-sales-e2e-{offset}"
            tenant = db.get(Tenant, tid)
            if tenant and tenant.tenant_code != code:
                raise RuntimeError("Sales test tenant id collision")
            if not tenant:
                db.add(Tenant(id=tid, tenant_code=code, school_name=f"商业销售验收学校{offset}",
                              deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE"))
                db.add(PlatformConfig(tenant_id=tid, config_type="TENANT_META", config_key="-",
                                      config_json={"status": "trial", "packageCode": "trial", "environment": "test"},
                                      enabled=True, status="ACTIVE"))
            schools.append({"tenantId": str(tid), "tenantCode": code})
        user = _platform_user(db, "PLATFORM_COMMERCIAL", "e2e_sales_commercial", "商业销售验收经办人")
        db.commit()
        session = _browser_session(db, user, role_code="PLATFORM_COMMERCIAL", channel="platform",
                                   client_type="PLATFORM_PC", head_sha=head,
                                   patterns=sorted(f"platform.{p}" for p in DUTY_CAPABILITIES["PLATFORM_COMMERCIAL"]),
                                   session_suffix="m3-sales")
        db.commit()
    output = Path(__file__).resolve().parents[2] / "e2e/runtime-fixtures/module-commerce-sales.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"head": head, "schools": schools, "session": session}, ensure_ascii=False), encoding="utf-8")
    print("M3 isolated sales identities ready; credentials kept in ignored local fixture.")


if __name__ == "__main__":
    main()
