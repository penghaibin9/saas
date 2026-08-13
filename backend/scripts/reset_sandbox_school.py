"""重置体验沙箱租户 sandbox-school（其余租户绝不受影响）。
────────────────────────────────────────────────────────────
默认口径已经切换为售前标准学校：20,000 学生 + 真实组织/账号关系 + 六域业务事实 + 13A/13B 高频事实。

用法：
  python scripts/reset_sandbox_school.py --dry-run
  python scripts/reset_sandbox_school.py --confirm
  python scripts/reset_sandbox_school.py --confirm --profile standard-20k
  python scripts/reset_sandbox_school.py --confirm --profile legacy-100   # 仅小型开发 fixture 兼容
  python scripts/reset_sandbox_school.py --dry-run --sqlite-dev           # 本地调试

安全设计：
  1. 只按 tenant_id == sandbox-school（1000000000000000007）操作；
  2. 执行前校验 tenant_code == sandbox-school，不符即拒绝；
  3. 禁止无租户条件删除 / 禁止 truncate / 不触碰 demo-school 与正式租户；
  4. 无 --confirm 一律不落库；删除前打印每张表将影响的行数；
  5. standard-20k 使用确定性虚构数据，不复制任何真实学校或真实个人数据；
  6. standard-20k 不再调用 generic DEMO marker 覆盖数据，并自动清理历史 reset 保留账号表里的已知旧假身份；
  7. 已识别为 standard-20k / standard-20k-damaged 的试点校禁止回灌 legacy-100；
  8. 学校角色只复用正式内置角色模板，兼岗不重复造教职工账号；
  9. 教务课程、教学任务/课表/考务快照、教材、实习岗位、毕设题目统一按 32 专业画像对账；
  10. 大成绩表专业课改名走 SQL 集合更新，禁止 17 万级事实 ORM 全量物化；
  11. 导师工作量按真实学校负载对账：224 名实习导师、384 名毕设导师，全部由现有教职工兼岗；
  12. 就业域复用同一届 6,400 学生、80 家企业与 160 个专业岗位，禁止另造就业企业/学生真值；
  13. 毕设过程按 2026-08-13 时间真值生成：只允许选题、任务书、开题与早期指导，禁止提前出现中期/答辩/成绩/归档；
  14. 教材按 2026 秋季开学准备态生成：选用/审核/征订可有数据，正式学生发放与收费必须保持 0；
  15. 评教与教学质量只回填已结束的 2025-2026-2；2026 秋季尚未开学，严禁提前生成评教结果；
  16. 学生评教保持匿名，教学质量不自动生成教学事故认定，只生成督导/巡课/检查与整改事实；
  17. 2025-2026-2 教务归档必须复用正式十三域策略全部 PASS 后才允许落 ARCHIVED；2026 秋季归档必须为 0；
  18. 13B 验收分两层：基础 seed 先锁 196课程/20K当前注册基线，历史结账后再锁750课程/33K注册/完整教学闭环终态；
  19. 专业语义同样分两层：基础阶段锁 32×6 核心课，完整培养方案阶段锁 32×23 专业/实践课逐门代码、名称、类别；
  20. 重建后从事实表反算岗位/企业人数，并校验旧假身份、专业课快照、宿舍床位、资助、班级、风险、教务成绩与考场容量等关系。
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
    from app.services.sandbox_school_profile import (
        PROFILE_STANDARD,
        PROFILE_STANDARD_DAMAGED,
        classify_sandbox_profile,
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

        current_profile = classify_sandbox_profile(db, SANDBOX_TID)
        counts = sandbox_row_counts(db)
        print("[reset] 目标租户：", SANDBOX_CODE, SANDBOX_TID)
        print("[reset] 当前档位：", json.dumps(current_profile, ensure_ascii=False))
        print("[reset] 目标数据档位：", args.profile)
        print("[reset] 将影响的数据（表 → 行数）：")
        print(json.dumps(counts, ensure_ascii=False, indent=2) if counts else "  （沙箱当前无业务数据）")
        if args.profile == PROFILE_STANDARD_20K:
            from app.services.sandbox_school_blueprint import blueprint_summary
            print("[reset] 目标学校规模：")
            print(json.dumps(blueprint_summary(), ensure_ascii=False, indent=2))
        elif current_profile["profile"] in {PROFILE_STANDARD, PROFILE_STANDARD_DAMAGED}:
            print(
                "[reset] 拒绝执行：当前已经属于 standard-20k 试点族，禁止回灌 legacy-100。"
                "如需恢复试点数据，请选择 standard-20k。"
            )
            return 5

        if args.dry_run:
            if t is None:
                print("[reset] dry-run：沙箱租户尚未初始化；--confirm 将执行首次建站种子")
            print("[reset] dry-run 完成，未修改任何数据。")
            return 0

        if args.profile == PROFILE_STANDARD_20K:
            from app.services.sandbox_school_academic_affairs_reconcile import reconcile_exam_rooms
            from app.services.sandbox_school_academic_affairs_seed import seed_school_academic_affairs_20k
            from app.services.sandbox_school_academic_archive_seed import (
                seed_school_academic_archive_20k,
                validate_school_academic_archive_20k,
            )
            from app.services.sandbox_school_academic_quality_seed import (
                seed_school_academic_quality_20k,
                validate_school_academic_quality_20k,
            )
            from app.services.sandbox_school_academic_textbook_seed import (
                seed_school_academic_textbooks_20k,
                validate_school_academic_textbooks_20k,
            )
            from app.services.sandbox_school_affairs_runner import seed_school_affairs_20k
            from app.services.sandbox_school_affairs_seed import validate_affairs_facts
            from app.services.sandbox_school_curriculum_closure import validate_school_academic_final_20k
            from app.services.sandbox_school_domain_seed import seed_school_domains_20k
            from app.services.sandbox_school_domain_validation import validate_core_domain_facts_20k
            from app.services.sandbox_school_employment_seed import (
                seed_school_employment_20k,
                validate_employment_facts_20k,
            )
            from app.services.sandbox_school_graduation_process_seed import (
                seed_school_graduation_process_20k,
                validate_school_graduation_process_20k,
            )
            from app.services.sandbox_school_legacy_cleanup import (
                clean_legacy_identity_residue,
                validate_no_legacy_identity_residue,
            )
            from app.services.sandbox_school_master_seed import (
                rebuild_school_master_20k,
                validate_school_master,
            )
            from app.services.sandbox_school_mentor_workload import (
                reconcile_school_mentor_workload_20k,
                validate_school_mentor_workload_20k,
            )
            from app.services.sandbox_school_professional_final_validation import (
                validate_professional_school_final_20k,
            )
            from app.services.sandbox_school_professional_runner import (
                professionalize_school_20k,
                validate_professional_academic_snapshots,
            )
            from app.services.sandbox_school_reconcile import reconcile_internship_capacity
            from app.services.sandbox_school_role_reconcile import (
                reconcile_school_roles_20k,
                validate_school_roles_20k,
            )

            master = rebuild_school_master_20k(db)
            legacy_identity_cleanup = clean_legacy_identity_residue(db, SANDBOX_TID)
            legacy_identity_acceptance = validate_no_legacy_identity_residue(db, SANDBOX_TID)

            role_topology = reconcile_school_roles_20k(db, SANDBOX_TID)
            role_topology_acceptance = validate_school_roles_20k(db, SANDBOX_TID)

            domains = seed_school_domains_20k(db, SANDBOX_TID)
            academic_affairs = seed_school_academic_affairs_20k(db, SANDBOX_TID)
            academic_affairs_baseline = academic_affairs.get("validation") or {}
            if not academic_affairs_baseline.get("passed"):
                raise RuntimeError(f"20K 13B 基础阶段验收未通过: {academic_affairs_baseline}")

            # 所有教务课程快照先统一成 32 专业真实课程，再生成会保存课程名快照的教材和评教事实。
            professional = professionalize_school_20k(db, SANDBOX_TID)
            professional_baseline = professional.get("validation") or {}
            if not professional_baseline.get("passed"):
                raise RuntimeError(f"20K 专业核心画像基础验收未通过: {professional_baseline}")
            professional_academic_snapshots = validate_professional_academic_snapshots(db, SANDBOX_TID)
            academic_textbooks = seed_school_academic_textbooks_20k(db, SANDBOX_TID)
            academic_quality = seed_school_academic_quality_20k(db, SANDBOX_TID)

            # 历史学期结账必须由正式十三域归档策略给出 PASS；任何一域未闭环都中止 20K 重建。
            academic_archive = seed_school_academic_archive_20k(db, SANDBOX_TID)

            mentor_workload = reconcile_school_mentor_workload_20k(db, SANDBOX_TID)
            graduation_process = seed_school_graduation_process_20k(db, SANDBOX_TID)
            employment = seed_school_employment_20k(db, SANDBOX_TID)

            exam_reconciliation = reconcile_exam_rooms(db, SANDBOX_TID)
            internship_reconciliation = reconcile_internship_capacity(db, SANDBOX_TID)
            affairs = seed_school_affairs_20k(db, SANDBOX_TID)

            acceptance = {
                "master": validate_school_master(db, SANDBOX_TID),
                "legacyIdentityResidue": legacy_identity_acceptance,
                "roleTopology": role_topology_acceptance,
                "mentorWorkload": validate_school_mentor_workload_20k(db, SANDBOX_TID),
                "graduationProcess": validate_school_graduation_process_20k(db, SANDBOX_TID),
                "domains": validate_core_domain_facts_20k(db, SANDBOX_TID),
                "academicAffairsBaseline": academic_affairs_baseline,
                "academicAffairsFinal": validate_school_academic_final_20k(db, SANDBOX_TID),
                "professionalBaseline": professional_baseline,
                "professionalFinal": validate_professional_school_final_20k(db, SANDBOX_TID),
                "professionalAcademicSnapshots": professional_academic_snapshots,
                "academicTextbooks": validate_school_academic_textbooks_20k(db, SANDBOX_TID),
                "academicQuality": validate_school_academic_quality_20k(db, SANDBOX_TID),
                "academicArchive": validate_school_academic_archive_20k(db, SANDBOX_TID),
                "employment": validate_employment_facts_20k(db, SANDBOX_TID),
                "studentAffairs": validate_affairs_facts(db, SANDBOX_TID),
                "internshipReconciliation": internship_reconciliation,
                "examReconciliation": exam_reconciliation,
            }
            report = {
                "reseeded": {
                    "master": master,
                    "legacyIdentityCleanup": legacy_identity_cleanup,
                    "roleTopology": role_topology,
                    "mentorWorkload": mentor_workload,
                    "graduationProcess": graduation_process,
                    "domains": domains,
                    "academicAffairs": academic_affairs,
                    "professional": professional,
                    "professionalAcademicSnapshots": professional_academic_snapshots,
                    "academicTextbooks": academic_textbooks,
                    "academicQuality": academic_quality,
                    "academicArchive": academic_archive,
                    "employment": employment,
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
                "[reset] 完成：20K 标准学校已通过旧假身份清零/主数据/角色拓扑/导师工作量/"
                "毕设早期过程/就业/专业核心与完整课程双阶段/教材准备/历史评教与教学质量/"
                "历史十三域归档/基础13B与完整13B双阶段/六域/13A/跨表关系对账。"
            )
            print("[reset] 可见体验账号：admin2 / teacher2 / student2（密码 123456）")
            print("[reset] 其余背景账号用于真实规模与权限/查询容量，不在销售登录页公开。")
        else:
            print("[reset] 完成：legacy-100 开发兼容沙箱。账号：admin2 / teacher2 / student2（密码 123456）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
