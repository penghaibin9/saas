"""重置体验沙箱租户 sandbox-school（其余租户绝不受影响）。
────────────────────────────────────────────────────────────
默认口径已经切换为售前标准学校：20,000 学生 + 真实组织/账号关系 + 六域业务事实 + 13A/13B 高频事实。

用法：
  python scripts/reset_sandbox_school.py --dry-run
  python scripts/reset_sandbox_school.py --confirm
  python scripts/reset_sandbox_school.py --confirm --profile standard-20k
  python scripts/reset_sandbox_school.py --confirm --profile legacy-100   # 仅开发兼容
  python scripts/reset_sandbox_school.py --dry-run --sqlite-dev           # 本地调试

安全设计：
  1. 只按 tenant_id == sandbox-school（1000000000000000007）操作；
  2. 执行前校验 tenant_code == sandbox-school，不符即拒绝；
  3. 禁止无租户条件删除 / 禁止 truncate / 不触碰 demo-school 与正式租户；
  4. 无 --confirm 一律不落库；删除前打印每张表将影响的行数；
  5. standard-20k 使用确定性虚构数据，不复制任何真实学校或真实个人数据；
  6. standard-20k 不再调用 generic DEMO marker 覆盖数据；
  7. 学校角色只复用正式内置角色模板，兼岗不重复造教职工账号；
  8. 教务课程、实习企业岗位、毕设导师选题统一按 32 专业画像对账；
  9. 大成绩表专业课改名走 SQL 集合更新，禁止 17 万级事实 ORM 全量物化；
  10. 导师工作量按真实学校负载对账：224 名实习导师、384 名毕设导师，全部由现有教职工兼岗；
  11. 重建后从事实表反算岗位/企业人数，并校验宿舍床位、资助、班级、风险、教务成绩与考场容量等关系。
连接：默认读取 backend/.env；--sqlite-dev 仅供本地调试，不作为 MySQL 正式验收。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROFILE_STANDARD_20K = "standard-20k"
PROFILE_LEGACY_100 = "legacy-100"


def main() -> int:
    ap = argparse.ArgumentParser(description="重置体验沙箱租户 sandbox-school")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="只统计不落库")
    g.add_argument("--confirm", action="store_true", help="真正删除并重建")
    ap.add_argument(
        "--profile",
        choices=(PROFILE_STANDARD_20K, PROFILE_LEGACY_100),
        default=PROFILE_STANDARD_20K,
        help="standard-20k=售前真实学校标准；legacy-100=旧开发兼容数据",
    )
    ap.add_argument("--sqlite-dev", action="store_true", help="使用本地 dev.db（默认读 .env）")
    args = ap.parse_args()

    if args.sqlite_dev:
        import _dev_env  # noqa: F401
    from app.db.session import db_enabled, get_sessionmaker
    if not db_enabled():
        print("[reset] 拒绝执行：DB_ENABLED=false（请检查 backend/.env 或加 --sqlite-dev）")
        return 2

    from sqlalchemy import select
    from app.models import Tenant
    from app.services.sandbox_service import (
        SANDBOX_CODE,
        SANDBOX_TID,
        reset_sandbox,
        sandbox_row_counts,
        seed_sandbox,
    )

    db = get_sessionmaker()()
    try:
        t = db.get(Tenant, SANDBOX_TID)
        if t is not None and (t.tenant_code or "") != SANDBOX_CODE:
            print(
                f"[reset] 拒绝执行：租户 {SANDBOX_TID} 的 code 是 {t.tenant_code!r}，"
                f"不是 {SANDBOX_CODE!r}"
            )
            return 3
        demo = db.scalars(select(Tenant).where(Tenant.tenant_code == "demo-school")).first()
        demo_before = None
        if demo is not None:
            from sqlalchemy import func
            from app.models import StudentProfile
            demo_before = db.scalar(
                select(func.count()).select_from(StudentProfile).where(
                    StudentProfile.tenant_id == demo.id
                )
            ) or 0

        counts = sandbox_row_counts(db)
        print("[reset] 目标租户：", SANDBOX_CODE, SANDBOX_TID)
        print("[reset] 数据档位：", args.profile)
        print("[reset] 将影响的数据（表 → 行数）：")
        print(json.dumps(counts, ensure_ascii=False, indent=2) if counts else "  （沙箱当前无业务数据）")
        if args.profile == PROFILE_STANDARD_20K:
            from app.services.sandbox_school_blueprint import blueprint_summary
            print("[reset] 目标学校规模：")
            print(json.dumps(blueprint_summary(), ensure_ascii=False, indent=2))

        if args.dry_run:
            if t is None:
                print("[reset] dry-run：沙箱租户尚未初始化；--confirm 将执行首次建站种子")
            print("[reset] dry-run 完成，未修改任何数据。")
            return 0

        if args.profile == PROFILE_STANDARD_20K:
            from app.services.sandbox_school_academic_affairs_reconcile import reconcile_exam_rooms
            from app.services.sandbox_school_academic_affairs_seed import (
                seed_school_academic_affairs_20k,
                validate_academic_affairs_facts,
            )
            from app.services.sandbox_school_affairs_runner import seed_school_affairs_20k
            from app.services.sandbox_school_affairs_seed import validate_affairs_facts
            from app.services.sandbox_school_domain_seed import (
                seed_school_domains_20k,
                validate_domain_facts,
            )
            from app.services.sandbox_school_master_seed import (
                rebuild_school_master_20k,
                validate_school_master,
            )
            from app.services.sandbox_school_mentor_workload import (
                reconcile_school_mentor_workload_20k,
                validate_school_mentor_workload_20k,
            )
            from app.services.sandbox_school_professional_reconcile import validate_professional_school_20k
            from app.services.sandbox_school_professional_runner import professionalize_school_20k
            from app.services.sandbox_school_reconcile import reconcile_internship_capacity
            from app.services.sandbox_school_role_reconcile import (
                reconcile_school_roles_20k,
                validate_school_roles_20k,
            )

            master = rebuild_school_master_20k(db)
            # 先建立基础角色拓扑并立即验收；后续导师工作量模块会合法扩展 ADVISOR 角色/范围。
            role_topology = reconcile_school_roles_20k(db, SANDBOX_TID)
            role_topology_acceptance = validate_school_roles_20k(db, SANDBOX_TID)

            domains = seed_school_domains_20k(db, SANDBOX_TID)
            academic_affairs = seed_school_academic_affairs_20k(db, SANDBOX_TID)

            # 大成绩事实的专业课名称由 professional_runner 用 SQL CASE 一次集合更新；
            # 实习/毕设先完成专业语义，再按专业规模重排真实导师负载。
            professional = professionalize_school_20k(db, SANDBOX_TID)
            mentor_workload = reconcile_school_mentor_workload_20k(db, SANDBOX_TID)

            exam_reconciliation = reconcile_exam_rooms(db, SANDBOX_TID)
            internship_reconciliation = reconcile_internship_capacity(db, SANDBOX_TID)
            affairs = seed_school_affairs_20k(db, SANDBOX_TID)

            acceptance = {
                "master": validate_school_master(db, SANDBOX_TID),
                "roleTopology": role_topology_acceptance,
                "mentorWorkload": validate_school_mentor_workload_20k(db, SANDBOX_TID),
                "domains": validate_domain_facts(db, SANDBOX_TID),
                "academicAffairs": validate_academic_affairs_facts(db, SANDBOX_TID),
                "professional": validate_professional_school_20k(db, SANDBOX_TID),
                "studentAffairs": validate_affairs_facts(db, SANDBOX_TID),
                "internshipReconciliation": internship_reconciliation,
                "examReconciliation": exam_reconciliation,
            }
            report = {
                "reseeded": {
                    "master": master,
                    "roleTopology": role_topology,
                    "mentorWorkload": mentor_workload,
                    "domains": domains,
                    "academicAffairs": academic_affairs,
                    "professional": professional,
                    "studentAffairs": affairs,
                    "acceptance": acceptance,
                }
            }
        else:
            report = (
                reset_sandbox(db, dry_run=False)
                if t is not None
                else {"reseeded": seed_sandbox(db)}
            )

        print("[reset] 已删除：", json.dumps(report.get("removed", {}), ensure_ascii=False))
        print(
            "[reset] 已重建：",
            json.dumps(report.get("reseeded", {}), ensure_ascii=False, default=str),
        )

        if demo is not None and demo_before is not None:
            from sqlalchemy import func
            from app.models import StudentProfile
            demo_after = db.scalar(
                select(func.count()).select_from(StudentProfile).where(
                    StudentProfile.tenant_id == demo.id
                )
            ) or 0
            print(
                f"[reset] 复核 demo-school 学生数：{demo_before} → {demo_after}"
                f"（{'OK 未受影响' if demo_before == demo_after else '异常！请立即检查'}）"
            )
            if demo_before != demo_after:
                return 4
        if args.profile == PROFILE_STANDARD_20K:
            print(
                "[reset] 完成：20K 标准学校已通过主数据/角色拓扑/导师工作量/"
                "六域/13A/13B/专业语义/跨表关系对账。"
            )
            print("[reset] 可见演示账号：admin2 / teacher2 / student2（密码 123456）")
            print("[reset] 其余背景账号用于真实规模与权限/查询容量，不在销售登录页公开。")
        else:
            print("[reset] 完成：legacy-100 开发兼容沙箱。账号：admin2 / teacher2 / student2（密码 123456）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
