"""为已存在学校补齐 SaaS 预设角色模板（幂等、无删除）。

这是租户开通流程的补偿脚本：早期已建学校可能没有 t_role 记录，
导致后续「导入老师和学生」无法把教师绑定到标准角色。

默认不执行，必须明确指定学校或 --all-active；平台运营租户永远跳过。
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant
from app.services.saas_role_service import ensure_builtin_roles

PLATFORM_TENANT_CODE = "platform"


def run(*, tenant_codes: list[str], all_active: bool) -> list[dict]:
    if not db_enabled():
        raise RuntimeError("数据库未启用，无法初始化学校角色模板")
    db = get_sessionmaker()()
    try:
        stmt = select(Tenant).where(Tenant.is_deleted.is_(False))
        if all_active:
            stmt = stmt.where(Tenant.status == "ACTIVE")
        elif tenant_codes:
            stmt = stmt.where(Tenant.tenant_code.in_(tuple(tenant_codes)))
        else:
            raise ValueError("请指定 --tenant-code，或明确传入 --all-active")
        tenants = [t for t in db.scalars(stmt.order_by(Tenant.id)).all()
                   if t.tenant_code != PLATFORM_TENANT_CODE]
        if not tenants:
            raise ValueError("未找到可初始化的学校租户")
        reports = []
        for tenant in tenants:
            report = ensure_builtin_roles(db, tenant.id)
            reports.append({"tenantCode": tenant.tenant_code, "tenantId": str(tenant.id), **report})
        db.commit()
        return reports
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="补齐学校 SaaS 预设角色模板（幂等）")
    parser.add_argument("--tenant-code", action="append", default=[], help="学校租户编码；可重复传入")
    parser.add_argument("--all-active", action="store_true", help="初始化全部 ACTIVE 学校租户（不含 platform）")
    args = parser.parse_args()
    try:
        reports = run(tenant_codes=args.tenant_code, all_active=args.all_active)
    except Exception as exc:
        print(f"[role-template-backfill] failed: {exc}", file=sys.stderr)
        return 1
    for report in reports:
        print(f"[role-template-backfill] {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
