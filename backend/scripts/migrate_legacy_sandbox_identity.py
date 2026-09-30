"""将历史沙箱身份迁移到规范租户槽位，不删除任何业务数据。

历史本地库曾把 ``1000000000000000004`` 错当成 ``sandbox-school``，而当前
平台身份册已经固定：

- 1000000000000000004 / trial-school
- 1000000000000000007 / sandbox-school

本脚本只做一次原子身份切换：保留 004 上的全部既有数据和 ACTIVE 状态，将其
tenant_code 规范为 trial-school；随后创建空的 007 sandbox-school 租户。业务数据
重建由后续分阶段脚本完成。

用法：
  python scripts/migrate_legacy_sandbox_identity.py --dry-run
  python scripts/migrate_legacy_sandbox_identity.py --confirm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _tenant_view(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "tenantCode": row.tenant_code,
        "schoolName": row.school_name,
        "status": row.status,
        "isDeleted": bool(row.is_deleted),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="规范历史沙箱租户身份")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只校验和展示计划")
    mode.add_argument("--confirm", action="store_true", help="执行原子身份迁移")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import Tenant
    from app.services.sandbox_school_master_seed import SCHOOL_NAME, SCHOOL_SHORT_NAME

    if not db_enabled():
        print("[identity-migration] 拒绝执行：DB_ENABLED=false")
        return 2

    db = get_sessionmaker()()
    try:
        legacy = db.get(Tenant, TRIAL_SCHOOL.tenant_id)
        canonical = db.get(Tenant, SANDBOX_SCHOOL.tenant_id)
        trial_code_owner = db.scalars(
            select(Tenant).where(Tenant.tenant_code == TRIAL_SCHOOL.tenant_code)
        ).first()
        sandbox_code_owner = db.scalars(
            select(Tenant).where(Tenant.tenant_code == SANDBOX_SCHOOL.tenant_code)
        ).first()

        if legacy is None:
            print(f"[identity-migration] 拒绝执行：历史租户 {TRIAL_SCHOOL.tenant_id} 不存在")
            return 3
        if legacy.tenant_code not in {
            TRIAL_SCHOOL.tenant_code,
            SANDBOX_SCHOOL.tenant_code,
        }:
            print(
                "[identity-migration] 拒绝执行：004 槽位存在未知租户代码 "
                f"{legacy.tenant_code!r}"
            )
            return 4
        if trial_code_owner is not None and trial_code_owner.id != legacy.id:
            print(
                "[identity-migration] 拒绝执行：trial-school 已被其他租户占用："
                f"{trial_code_owner.id}"
            )
            return 5
        if canonical is not None and canonical.tenant_code != SANDBOX_SCHOOL.tenant_code:
            print(
                "[identity-migration] 拒绝执行：007 槽位存在非沙箱租户："
                f"{canonical.tenant_code!r}"
            )
            return 6
        if sandbox_code_owner is not None and sandbox_code_owner.id not in {
            legacy.id,
            SANDBOX_SCHOOL.tenant_id,
        }:
            print(
                "[identity-migration] 拒绝执行：sandbox-school 已被未知租户占用："
                f"{sandbox_code_owner.id}"
            )
            return 7

        plan = {
            "legacyBefore": _tenant_view(legacy),
            "canonicalBefore": _tenant_view(canonical),
            "actions": [
                {
                    "action": "RENAME_TENANT_CODE",
                    "tenantId": str(TRIAL_SCHOOL.tenant_id),
                    "from": legacy.tenant_code,
                    "to": TRIAL_SCHOOL.tenant_code,
                    "businessRows": "PRESERVED",
                    "status": "PRESERVED",
                },
                {
                    "action": "ENSURE_CANONICAL_SANDBOX",
                    "tenantId": str(SANDBOX_SCHOOL.tenant_id),
                    "tenantCode": SANDBOX_SCHOOL.tenant_code,
                    "schoolName": SCHOOL_NAME,
                },
            ],
        }
        print("[identity-migration] 计划：")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        if args.dry_run:
            print("[identity-migration] dry-run 完成，未修改任何数据。")
            return 0

        legacy.tenant_code = TRIAL_SCHOOL.tenant_code
        db.flush()

        if canonical is None:
            canonical = Tenant(
                id=SANDBOX_SCHOOL.tenant_id,
                tenant_code=SANDBOX_SCHOOL.tenant_code,
                school_name=SCHOOL_NAME,
                short_name=SCHOOL_SHORT_NAME,
                status="ACTIVE",
            )
            db.add(canonical)
        else:
            canonical.school_name = SCHOOL_NAME
            canonical.short_name = SCHOOL_SHORT_NAME
            canonical.status = "ACTIVE"
            canonical.is_deleted = False

        db.commit()
        print("[identity-migration] 完成：")
        print(
            json.dumps(
                {
                    "legacyAfter": _tenant_view(legacy),
                    "canonicalAfter": _tenant_view(canonical),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
