"""只读验收 sandbox-school 的 20K 售前标准学校数据。

用法：
  cd backend
  python scripts/check_sandbox_20k_school.py
  python scripts/check_sandbox_20k_school.py --sqlite-dev   # 仅开发调试

脚本不插入、不更新、不删除任何数据。失败返回非 0，适合部署后 smoke / runbook。
当 test-results/sandbox-20k/rebuild.log 存在时，同时强制校验全量重建耗时/内存预算，
避免大事实表被 ORM 全量物化却仍然“数据验收绿”。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _internship_capacity_audit(db, tenant_id: int) -> dict:
    from sqlalchemy import func, select
    from app.models import EmpCompany, InternshipPosition, InternshipRecord

    assigned = int(db.scalar(
        select(func.count()).select_from(InternshipRecord).where(
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.destination_type == "ASSIGNED",
            InternshipRecord.position_id.is_not(None),
            InternshipRecord.enterprise_id.is_not(None),
            InternshipRecord.is_deleted.is_(False),
        )
    ) or 0)
    allocated = int(db.scalar(
        select(func.coalesce(func.sum(InternshipPosition.allocated_count), 0)).where(
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.is_deleted.is_(False),
        )
    ) or 0)
    company_interns = int(db.scalar(
        select(func.coalesce(func.sum(EmpCompany.intern_count), 0)).where(
            EmpCompany.tenant_id == tenant_id,
            EmpCompany.is_deleted.is_(False),
        )
    ) or 0)
    over_capacity = int(db.scalar(
        select(func.count()).select_from(InternshipPosition).where(
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.allocated_count > InternshipPosition.headcount,
            InternshipPosition.is_deleted.is_(False),
        )
    ) or 0)
    passed = assigned == allocated == company_interns and over_capacity == 0
    return {
        "assignedRecords": assigned,
        "positionAllocated": allocated,
        "companyInternCount": company_interns,
        "positionsOverCapacity": over_capacity,
        "passed": passed,
    }


def _exam_capacity_audit(db, tenant_id: int) -> dict:
    from sqlalchemy import func, select
    from app.models import AaExamCourse, AaExamRoom, AaExamRoomStudent

    rooms = int(db.scalar(select(func.count()).select_from(AaExamRoom).where(
        AaExamRoom.tenant_id == tenant_id,
        AaExamRoom.is_deleted.is_(False),
    )) or 0)
    seats = int(db.scalar(select(func.count()).select_from(AaExamRoomStudent).where(
        AaExamRoomStudent.tenant_id == tenant_id,
        AaExamRoomStudent.is_deleted.is_(False),
    )) or 0)
    over_capacity = int(db.scalar(select(func.count()).select_from(AaExamRoom).where(
        AaExamRoom.tenant_id == tenant_id,
        AaExamRoom.planned_count > AaExamRoom.capacity,
        AaExamRoom.is_deleted.is_(False),
    )) or 0)
    course_count = int(db.scalar(select(func.count()).select_from(AaExamCourse).where(
        AaExamCourse.tenant_id == tenant_id,
        AaExamCourse.is_deleted.is_(False),
    )) or 0)
    unique_course_students = int(db.scalar(select(func.count()).select_from(
        select(AaExamRoomStudent.exam_course_id, AaExamRoomStudent.student_id)
        .where(
            AaExamRoomStudent.tenant_id == tenant_id,
            AaExamRoomStudent.is_deleted.is_(False),
        )
        .distinct()
        .subquery()
    )) or 0)
    passed = rooms >= course_count and seats == unique_course_students and over_capacity == 0
    return {
        "examCourses": course_count,
        "examRooms": rooms,
        "examSeats": seats,
        "uniqueCourseStudents": unique_course_students,
        "roomsOverCapacity": over_capacity,
        "passed": passed,
    }


def _rebuild_budget_audit() -> dict | None:
    log_path = Path("test-results/sandbox-20k/rebuild.log")
    if not log_path.exists():
        return None
    from scripts.check_sandbox_20k_rebuild_budget import (
        MAX_RSS_MIB,
        MAX_SECONDS,
        check_budget,
    )
    metrics = check_budget(log_path)
    return {
        **metrics,
        "maxSeconds": MAX_SECONDS,
        "maxRssMiB": MAX_RSS_MIB,
        "passed": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="只读验收 20K 售前演示学校数据")
    ap.add_argument("--sqlite-dev", action="store_true", help="仅本地开发调试；正式验收使用 MySQL")
    args = ap.parse_args()
    if args.sqlite_dev:
        import _dev_env  # noqa: F401

    try:
        rebuild_budget = _rebuild_budget_audit()
    except (ValueError, RuntimeError) as exc:
        print("[20k-check] FAIL 20K重建资源预算", str(exc))
        return 7

    from app.db.session import db_enabled, get_sessionmaker
    if not db_enabled():
        print("[20k-check] DB_ENABLED=false，无法验收真实数据库")
        return 2

    from app.models import Tenant
    from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID
    from app.services.sandbox_school_academic_affairs_seed import validate_academic_affairs_facts
    from app.services.sandbox_school_affairs_seed import validate_affairs_facts
    from app.services.sandbox_school_domain_validation import validate_core_domain_facts_20k
    from app.services.sandbox_school_employment_seed import validate_employment_facts_20k
    from app.services.sandbox_school_graduation_process_seed import validate_school_graduation_process_20k
    from app.services.sandbox_school_master_seed import validate_school_master
    from app.services.sandbox_school_mentor_workload import validate_school_mentor_workload_20k
    from app.services.sandbox_school_professional_reconcile import validate_professional_school_20k

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, SANDBOX_TID)
        if tenant is None or (tenant.tenant_code or "") != SANDBOX_CODE:
            print(f"[20k-check] 目标租户不正确：{getattr(tenant, 'tenant_code', None)!r}")
            return 3

        try:
            master = validate_school_master(db, SANDBOX_TID)
            mentor_workload = validate_school_mentor_workload_20k(db, SANDBOX_TID)
            graduation_process = validate_school_graduation_process_20k(db, SANDBOX_TID)
            domains = validate_core_domain_facts_20k(db, SANDBOX_TID)
            academic_affairs = validate_academic_affairs_facts(db, SANDBOX_TID)
            professional = validate_professional_school_20k(db, SANDBOX_TID)
            employment = validate_employment_facts_20k(db, SANDBOX_TID)
            affairs = validate_affairs_facts(db, SANDBOX_TID)
        except RuntimeError as exc:
            print("[20k-check] FAIL", str(exc))
            return 4

        internship = _internship_capacity_audit(db, SANDBOX_TID)
        exam = _exam_capacity_audit(db, SANDBOX_TID)
        report = {
            "tenantId": str(SANDBOX_TID),
            "tenantCode": SANDBOX_CODE,
            "schoolName": tenant.school_name,
            "rebuildBudget": rebuild_budget,
            "master": master,
            "mentorWorkload": mentor_workload,
            "graduationProcess": graduation_process,
            "domains": domains,
            "academicAffairs": academic_affairs,
            "professional": professional,
            "employment": employment,
            "studentAffairs": affairs,
            "internshipReconciliation": internship,
            "examReconciliation": exam,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        if not internship["passed"]:
            print("[20k-check] FAIL 实习岗位/企业/学生人数不一致")
            return 5
        if not exam["passed"]:
            print("[20k-check] FAIL 考场容量/座位唯一性不一致")
            return 6
        print("[20k-check] PASS 20K 售前标准学校数据、导师工作量、毕设时间线与就业域验收通过")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
