"""分阶段建设标准沙箱学校：阶段 1，学校主数据与身份底座。

本阶段只生成租户品牌、固定体验账号、背景教职工账号、角色、学院、专业、班级、
学生主档与辅导员范围，不生成教务、学工、实习、毕设或就业业务事实。

首次建设：
  python scripts/build_sandbox_school_master.py --dry-run
  python scripts/build_sandbox_school_master.py --confirm

安全约束：目标租户已有业务数据时默认拒绝重建。确需重建主数据必须显式增加
``--allow-rebuild``，并确保已经完成独立备份。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="建设标准沙箱学校主数据")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只检查目标与建设规模")
    mode.add_argument("--confirm", action="store_true", help="执行主数据建设")
    parser.add_argument(
        "--allow-rebuild",
        action="store_true",
        help="允许清理目标沙箱已有业务数据后重建；首次建设不需要",
    )
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import Tenant
    from app.services.sandbox_school_blueprint import blueprint_summary
    from app.services.sandbox_school_credentials import public_account_password_hashes
    from app.services.sandbox_school_master_seed import (
        rebuild_school_master_20k,
        validate_school_master,
    )
    from app.services.sandbox_service import sandbox_row_counts

    if not db_enabled():
        print("[sandbox-master] 拒绝执行：DB_ENABLED=false")
        return 2

    db = get_sessionmaker()()
    try:
        trial = db.get(Tenant, TRIAL_SCHOOL.tenant_id)
        target = db.get(Tenant, SANDBOX_SCHOOL.tenant_id)
        if trial is None or trial.tenant_code != TRIAL_SCHOOL.tenant_code:
            print("[sandbox-master] 拒绝执行：004 / trial-school 身份尚未规范")
            return 3
        if target is None or target.tenant_code != SANDBOX_SCHOOL.tenant_code:
            print("[sandbox-master] 拒绝执行：007 / sandbox-school 身份不存在或不匹配")
            return 4

        counts = sandbox_row_counts(db)
        plan = {
            "target": {
                "id": str(target.id),
                "tenantCode": target.tenant_code,
                "schoolName": target.school_name,
            },
            "currentNonEmptyTables": len(counts),
            "currentRows": sum(counts.values()),
            "blueprint": blueprint_summary(),
            "businessDomains": "NOT_INCLUDED_IN_THIS_STAGE",
        }
        print("[sandbox-master] 建设计划：")
        print(json.dumps(plan, ensure_ascii=False, indent=2))

        if args.dry_run:
            print("[sandbox-master] dry-run 完成，未修改任何数据。")
            return 0
        if counts and not args.allow_rebuild:
            print(
                "[sandbox-master] 拒绝执行：目标沙箱已有业务数据。"
                "如已完成独立备份并确认重建，请显式增加 --allow-rebuild。"
            )
            return 5

        # 在任何清理/写入前验证三份体验账号凭据，缺失、弱口令或复用均零写入失败。
        public_account_password_hashes()
        result = rebuild_school_master_20k(db)
        validation = validate_school_master(db, SANDBOX_SCHOOL.tenant_id)
        if not validation.get("passed"):
            raise RuntimeError(f"沙箱主数据验收失败：{validation}")

        print("[sandbox-master] 建设完成：")
        print(
            json.dumps(
                {"result": result, "validation": validation},
                ensure_ascii=False,
                indent=2,
                default=str,
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
