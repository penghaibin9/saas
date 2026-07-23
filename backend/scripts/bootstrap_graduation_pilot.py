"""毕业设计试点服一键编排：迁移 → 种子 → 多角色账号 → 学院 claim → 校验。

编排已有脚本，不重复造种子逻辑：

- alembic upgrade head
- _seed_graduation.seed_graduation（经 Session；幂等）
- _seed_graduation_org_scope（学院/专业 TeacherStudentScope + 学生 org 回填）
- e2e_bootstrap_graduation_accounts（组织 + 师生导入，需 API）
- e2e_verify_graduation_accounts（登录校验）

用法（在 backend 目录）：

  python scripts/bootstrap_graduation_pilot.py --dry-run
  python scripts/bootstrap_graduation_pilot.py --execute
  python scripts/bootstrap_graduation_pilot.py --execute --skip-accounts   # 仅迁移+种子
  python scripts/bootstrap_graduation_pilot.py --execute --accounts-only   # 仅账号（API 已起）

环境：

- MySQL：backend/.env（DB_ENABLED / DB_*），与 alembic 一致
- 账号步骤：API 默认 http://127.0.0.1:8000/api/v1（可用 E2E_API_BASE 覆盖）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

UAT_DOC = (
    "docs/06-开发施工与质量验收/施工记录/"
    "毕业设计中心-试点服升级与UAT验收清单-20260723.md"
)
GAP_DOC = (
    "docs/06-开发施工与质量验收/施工记录/"
    "毕业设计中心-生产级就绪与试点验收差距-20260723.md"
)
E2E_REPORT = (
    "docs/06-开发施工与质量验收/施工记录/"
    "毕业设计中心-全角色E2E业务验收报告-20260722.md"
)


def _py() -> str:
    return sys.executable


def _print_plan(*, skip_migrate: bool, skip_seed: bool, skip_accounts: bool, accounts_only: bool) -> None:
    print("=== 毕业设计试点编排计划 ===")
    steps = []
    if accounts_only:
        steps = [
            "（跳过迁移/种子）",
            "e2e_bootstrap_graduation_accounts.py — 组织 + 多角色导入",
            "_seed_graduation_org_scope — 学院/专业 claim 范围 + 学生 org 回填",
            "e2e_verify_graduation_accounts.py — 校验登录",
        ]
    else:
        if not skip_migrate:
            steps.append("alembic upgrade head")
        else:
            steps.append("（跳过）alembic upgrade head")
        if not skip_seed:
            steps.append("_seed_graduation.seed_graduation — 毕设域演示种子（幂等）")
            steps.append("_seed_graduation_org_scope — 学院/专业 claim（若账号已存在）")
        else:
            steps.append("（跳过）seed_graduation / org_scope")
        if not skip_accounts:
            steps.append("e2e_bootstrap_graduation_accounts.py — 组织 + 多角色导入（需 API）")
            steps.append("_seed_graduation_org_scope — 学院/专业 claim 范围 + 学生 org 回填")
            steps.append("e2e_verify_graduation_accounts.py — 校验登录")
        else:
            steps.append("（跳过）账号导入与校验")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s}")
    print()
    print("证据与清单：")
    print(f"  - {E2E_REPORT}")
    print(f"  - {GAP_DOC}")
    print(f"  - {UAT_DOC}")
    print(f"  - scripts/check/check-graduation-production-gates.mjs")
    print()


def _print_uat_next() -> None:
    print("=== 下一步：人工 UAT 勾选（摘要） ===")
    checklist = [
        "备份已确认 / 代码版本已部署",
        "A3–A7：迁移、种子、账号、Mock 闸门已勾选",
        "A8：学院秘书登录 JWT 含 collegeId；缺范围时 PC 有中文提示",
        "B1 批次规则与阶段",
        "B4 选题容量/冲突",
        "B5 任务书→开题批阅",
        "B7 成果→查重→评阅回避",
        "B8 答辩编排与评分",
        "B9 成绩发布",
        "B10 开风险阻断归档 → 关闭后归档",
        "C 类已知不阻断项已告知业务方",
        "D 签字栏：技术 / 业务 / 产品",
    ]
    for item in checklist:
        print(f"  [ ] {item}")
    print(f"\n完整清单见仓库：{UAT_DOC}")
    print("口径：签字前不称「已可验收上线」。")


def run_migrate() -> int:
    print("[pilot] alembic upgrade head ...")
    return subprocess.call([_py(), "-m", "alembic", "upgrade", "head"], cwd=str(BACKEND_DIR))


def run_seed() -> int:
    print("[pilot] seed_graduation ...")
    sys.path.insert(0, str(SCRIPTS_DIR))
    sys.path.insert(0, str(BACKEND_DIR))
    import _mysql_env  # noqa: F401
    from app.db.session import get_sessionmaker, reset_state
    from _seed_graduation import seed_graduation

    reset_state()
    db = get_sessionmaker()()
    try:
        result = seed_graduation(db)
        db.commit()
        print(f"[pilot] seed_graduation -> {result}")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[pilot] seed_graduation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def run_org_scope_seed() -> int:
    print("[pilot] seed_graduation_org_scope ...")
    sys.path.insert(0, str(SCRIPTS_DIR))
    sys.path.insert(0, str(BACKEND_DIR))
    import _mysql_env  # noqa: F401
    from app.db.session import get_sessionmaker, reset_state
    from _seed_graduation_org_scope import seed_graduation_org_scope

    reset_state()
    db = get_sessionmaker()()
    try:
        result = seed_graduation_org_scope(db)
        db.commit()
        print(f"[pilot] seed_graduation_org_scope -> {result}")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[pilot] seed_graduation_org_scope failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def run_accounts_bootstrap() -> int:
    print("[pilot] e2e_bootstrap_graduation_accounts ...")
    env = os.environ.copy()
    return subprocess.call(
        [_py(), str(SCRIPTS_DIR / "e2e_bootstrap_graduation_accounts.py")],
        cwd=str(BACKEND_DIR), env=env,
    )


def run_accounts_verify() -> int:
    print("[pilot] e2e_verify_graduation_accounts ...")
    return subprocess.call(
        [_py(), str(SCRIPTS_DIR / "e2e_verify_graduation_accounts.py")],
        cwd=str(BACKEND_DIR),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="毕业设计试点服：迁移 + 种子 + 多角色账号编排")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只打印计划与 UAT 摘要，不执行")
    mode.add_argument("--execute", action="store_true", help="按计划执行")
    parser.add_argument("--skip-migrate", action="store_true", help="跳过 alembic upgrade head")
    parser.add_argument("--skip-seed", action="store_true", help="跳过 seed_graduation")
    parser.add_argument("--skip-accounts", action="store_true", help="跳过账号导入与校验")
    parser.add_argument("--accounts-only", action="store_true", help="仅跑账号导入+校验（需 API）")
    args = parser.parse_args()

    if args.accounts_only and args.skip_accounts:
        print("不能同时 --accounts-only 与 --skip-accounts", file=sys.stderr)
        return 2

    _print_plan(
        skip_migrate=args.skip_migrate,
        skip_seed=args.skip_seed,
        skip_accounts=args.skip_accounts,
        accounts_only=args.accounts_only,
    )

    if args.dry_run:
        print("[dry-run] 未修改数据库、未调用 API。确认后使用 --execute。")
        _print_uat_next()
        return 0

    if args.accounts_only:
        rc = run_accounts_bootstrap()
        if rc != 0:
            return rc
        rc = run_org_scope_seed()
        if rc != 0:
            return rc
        rc = run_accounts_verify()
        _print_uat_next()
        return rc

    if not args.skip_migrate:
        rc = run_migrate()
        if rc != 0:
            print("[pilot] migrate failed", file=sys.stderr)
            return rc

    if not args.skip_seed:
        rc = run_seed()
        if rc != 0:
            return rc
        rc = run_org_scope_seed()
        if rc != 0:
            return rc

    if not args.skip_accounts:
        api = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8000/api/v1")
        print(f"[pilot] 账号步骤依赖 API：{api}（需已启动）")
        rc = run_accounts_bootstrap()
        if rc != 0:
            print("[pilot] accounts bootstrap failed — 请确认 API 已启动且 admin2 可用", file=sys.stderr)
            return rc
        rc = run_org_scope_seed()
        if rc != 0:
            return rc
        rc = run_accounts_verify()
        if rc != 0:
            print("[pilot] accounts verify failed", file=sys.stderr)
            return rc

    print("[pilot] 编排完成。")
    _print_uat_next()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
