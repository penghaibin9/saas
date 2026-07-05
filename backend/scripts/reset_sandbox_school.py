"""重置体验沙箱租户 sandbox-school（其余租户绝不受影响）。
────────────────────────────────────────────────────────────
用法：
  python scripts/reset_sandbox_school.py --dry-run    # 只统计将删除的数据量，不落库
  python scripts/reset_sandbox_school.py --confirm    # 真正删除并重建
  python scripts/reset_sandbox_school.py --dry-run --sqlite-dev  # 本地 dev.db 调试用

安全设计：
  1. 只按 tenant_id == sandbox-school（1000000000000000004）逐表条件删除；
  2. 执行前校验库内该租户的 tenant_code 必须等于 sandbox-school，不符即拒绝；
  3. 禁止无租户条件删除 / 禁止 truncate / 不触碰 demo-school 与正式租户；
  4. 无 --confirm 一律不落库；删除前打印每张表将影响的行数。
连接：默认读取 backend/.env（服务器 MySQL 即生产配置）；--sqlite-dev 强制本地 dev.db。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # backend/


def main() -> int:
    ap = argparse.ArgumentParser(description="重置体验沙箱租户 sandbox-school")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="只统计不落库")
    g.add_argument("--confirm", action="store_true", help="真正删除并重建")
    ap.add_argument("--sqlite-dev", action="store_true", help="使用本地 dev.db（默认读 .env）")
    args = ap.parse_args()

    if args.sqlite_dev:
        import _dev_env  # noqa: F401  强制 DB_ENABLED=true + sqlite dev.db
    from app.db.session import db_enabled, get_sessionmaker
    if not db_enabled():
        print("[reset] 拒绝执行：DB_ENABLED=false（请检查 backend/.env 或加 --sqlite-dev）")
        return 2

    from sqlalchemy import select
    from app.models import Tenant
    from app.services.sandbox_service import (SANDBOX_CODE, SANDBOX_TID, reset_sandbox,
                                              sandbox_row_counts, seed_sandbox)

    db = get_sessionmaker()()
    try:
        # 安全校验：目标租户必须存在且 code == sandbox-school（防 ID 被挪用）
        t = db.get(Tenant, SANDBOX_TID)
        if t is not None and (t.tenant_code or "") != SANDBOX_CODE:
            print(f"[reset] 拒绝执行：租户 {SANDBOX_TID} 的 code 是 {t.tenant_code!r}，"
                  f"不是 {SANDBOX_CODE!r}")
            return 3
        demo = db.scalars(select(Tenant).where(Tenant.tenant_code == "demo-school")).first()
        demo_before = None
        if demo is not None:
            from sqlalchemy import func
            from app.models import StudentProfile
            demo_before = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == demo.id)) or 0

        counts = sandbox_row_counts(db)
        print("[reset] 目标租户：", SANDBOX_CODE, SANDBOX_TID)
        print("[reset] 将影响的数据（表 → 行数）：")
        print(json.dumps(counts, ensure_ascii=False, indent=2) if counts else "  （沙箱当前无业务数据）")

        if args.dry_run:
            if t is None:
                print("[reset] dry-run：沙箱租户尚未初始化；--confirm 将执行首次建站种子")
            print("[reset] dry-run 完成，未修改任何数据。")
            return 0

        report = reset_sandbox(db, dry_run=False) if t is not None else {"reseeded": seed_sandbox(db)}
        print("[reset] 已删除：", json.dumps(report.get("removed", {}), ensure_ascii=False))
        print("[reset] 已重建：", json.dumps(report.get("reseeded", {}), ensure_ascii=False))

        # 复核：demo-school 学生数不变
        if demo is not None and demo_before is not None:
            from sqlalchemy import func
            from app.models import StudentProfile
            demo_after = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == demo.id)) or 0
            print(f"[reset] 复核 demo-school 学生数：{demo_before} → {demo_after}"
                  f"（{'OK 未受影响' if demo_before == demo_after else '异常！请立即检查'}）")
            if demo_before != demo_after:
                return 4
        print("[reset] 完成。沙箱账号：admin2 / teacher2 / student2（密码 123456）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
