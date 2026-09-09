"""分阶段建设标准沙箱学校：阶段 4，岗位实习核心全过程数据。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _count(db, model, tenant_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id,
        model.is_deleted.is_(False),
    )) or 0)


def _validate(db, tenant_id: int) -> dict:
    from app.models import (
        AttendanceException, EmpCompany, InternshipBatch, InternshipCheckin,
        InternshipPosition, InternshipRecord, RiskRecord, WeeklyReport,
    )

    report = {
        "batches": _count(db, InternshipBatch, tenant_id),
        "companies": _count(db, EmpCompany, tenant_id),
        "positions": _count(db, InternshipPosition, tenant_id),
        "records": _count(db, InternshipRecord, tenant_id),
        "weeklyReports": _count(db, WeeklyReport, tenant_id),
        "checkins": _count(db, InternshipCheckin, tenant_id),
        "exceptions": _count(db, AttendanceException, tenant_id),
        "risks": _count(db, RiskRecord, tenant_id),
    }
    expected = {
        "batches": 1, "companies": 80, "positions": 160, "records": 6400,
        "weeklyReports": 4480, "checkins": 28000, "exceptions": 112, "risks": 56,
    }
    mismatches = {k: {"expected": v, "actual": report[k]} for k, v in expected.items()
                  if report[k] != v}
    if mismatches:
        raise RuntimeError(f"岗位实习核心数据验收失败: {mismatches}")
    report["passed"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="建设标准沙箱学校岗位实习演示数据")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import InternshipRecord, Tenant
    from app.services.sandbox_school_domain_seed import _roster, _seed_internship
    from app.services.sandbox_school_internship_mentor_reconcile import reconcile_internship_mentor_workload
    from app.services.sandbox_school_mentor_pool import mentor_user_pools
    from app.services.sandbox_school_professional_reconcile import _professionalize_internship
    from app.services.sandbox_school_reconcile import reconcile_internship_capacity

    if not db_enabled():
        return 2
    tenant_id = SANDBOX_SCHOOL.tenant_id
    db = get_sessionmaker()()
    try:
        trial, target = db.get(Tenant, TRIAL_SCHOOL.tenant_id), db.get(Tenant, tenant_id)
        if trial is None or trial.tenant_code != TRIAL_SCHOOL.tenant_code:
            return 3
        if target is None or target.tenant_code != SANDBOX_SCHOOL.tenant_code:
            return 4
        current = _count(db, InternshipRecord, tenant_id)
        print(json.dumps({"tenantId": str(tenant_id), "currentRecords": current,
                          "targetRecords": 6400, "oldTenantProtected": True}, ensure_ascii=False))
        if args.dry_run:
            return 0 if current == 0 else 5
        if current:
            return 5

        roster = _roster(db, tenant_id, grades=("2024",))
        if len(roster) != 6400:
            raise RuntimeError(f"2024级学生范围异常: {len(roster)}")
        seeded = _seed_internship(db, tenant_id, roster)
        professional = _professionalize_internship(db, tenant_id)
        internship_users, _ = mentor_user_pools(db, tenant_id)
        mentors = reconcile_internship_mentor_workload(db, tenant_id, internship_users)
        capacity = reconcile_internship_capacity(db, tenant_id)
        acceptance = _validate(db, tenant_id)
        print(json.dumps({"seeded": seeded, "professional": professional,
                          "mentors": mentors, "capacity": capacity,
                          "acceptance": acceptance}, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
