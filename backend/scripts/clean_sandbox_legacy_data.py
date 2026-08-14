"""清理 sandbox-school 中仍残留的高置信旧假身份数据。

默认只审计；--confirm 才删除。只允许 standard-20k 或 standard-20k-damaged，
绝不把 legacy-100 / unknown 当成试点校直接处理。

业务表里的旧假事实由 standard-20k 全量重建按 tenant 清空；本脚本专门处理历史 reset
刻意保留的 t_user/t_user_role 中旧 seed 身份，方便已有试点库不必为了几个旧账号重灌全校。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser(description="审计/清理 standard-20k 沙箱旧假身份残留")
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--dry-run", action="store_true", help="只审计，不修改（默认）")
    g.add_argument("--confirm", action="store_true", help="确认删除高置信旧种子身份")
    ap.add_argument("--sqlite-dev", action="store_true", help="仅本地开发调试；正式清洗使用 MySQL")
    args = ap.parse_args()

    if args.sqlite_dev:
        import _dev_env  # noqa: F401

    from app.db.session import db_enabled, get_sessionmaker
    if not db_enabled():
        print("[legacy-clean] DB_ENABLED=false，拒绝执行")
        return 2

    from app.services.sandbox_service import SANDBOX_TID, _assert_target_is_sandbox
    from app.services.sandbox_school_legacy_cleanup import (
        clean_legacy_identity_residue,
        legacy_identity_report,
    )
    from app.services.sandbox_school_profile import (
        PROFILE_STANDARD,
        PROFILE_STANDARD_DAMAGED,
        classify_sandbox_profile,
    )

    db = get_sessionmaker()()
    try:
        _assert_target_is_sandbox(db)
        profile = classify_sandbox_profile(db, SANDBOX_TID)
        if profile["profile"] not in {PROFILE_STANDARD, PROFILE_STANDARD_DAMAGED}:
            print("[legacy-clean] 拒绝：当前不是 standard-20k 试点族，避免误清开发/未知数据")
            print(json.dumps(profile, ensure_ascii=False, indent=2))
            return 3

        before = legacy_identity_report(db, SANDBOX_TID)
        print("[legacy-clean] 当前档位：")
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        print("[legacy-clean] 高置信旧假身份残留：")
        print(json.dumps(before, ensure_ascii=False, indent=2))

        if not args.confirm:
            print("[legacy-clean] dry-run 完成；未修改任何数据。确认后使用 --confirm。")
            return 0

        result = clean_legacy_identity_residue(db, SANDBOX_TID)
        print("[legacy-clean] 清洗完成：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
