"""分阶段建设标准沙箱学校：阶段 3，迎新与学工全过程数据。

本阶段在已验收的主数据和教务数据上，按依赖顺序生成：

1. 2026 级数字迎新、绿色通道、材料和异常；
2. 2024/2025 级在校生服务档案、请假、宿舍异常、心理关注和事务工单；
3. 宿舍资源、班级干部、辅导员考评、谈心家校、奖助、违纪和风险中枢。

统一消息和待办包含实习业务引用，不在实习数据建成前提前生成。

用法：
  python scripts/build_sandbox_school_student_affairs.py --dry-run
  python scripts/build_sandbox_school_student_affairs.py --confirm
"""
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


def _validate_orientation(db, tenant_id: int) -> dict:
    from app.models import (
        GreenChannelApplication,
        OrientationBatch,
        OrientationException,
        OrientationExceptionFollowup,
        OrientationMaterial,
        OrientationStudent,
    )

    report = {
        "batches": _count(db, OrientationBatch, tenant_id),
        "students": _count(db, OrientationStudent, tenant_id),
        "greenChannels": _count(db, GreenChannelApplication, tenant_id),
        "materials": _count(db, OrientationMaterial, tenant_id),
        "exceptions": _count(db, OrientationException, tenant_id),
        "followups": _count(db, OrientationExceptionFollowup, tenant_id),
    }
    expected = {
        "batches": 1,
        "students": 7000,
        "greenChannels": 613,
        "materials": 1225,
        "exceptions": 140,
        "followups": 70,
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if mismatches:
        raise RuntimeError(f"20K 数字迎新验收失败: {mismatches}")
    report["passed"] = True
    return report


def _validate_campus(db, tenant_id: int) -> dict:
    from app.models import (
        CsDormException,
        CsDormRecord,
        CsGrant,
        CsLeave,
        CsMentalRecord,
        CsServiceStudent,
        CsWorkOrder,
    )
    from app.services.sandbox_school_domain_seed import (
        EXPECTED_CAMPUS_STUDENTS,
        EXPECTED_DORM_ROWS,
    )

    report = {
        "students": _count(db, CsServiceStudent, tenant_id),
        "dormRecords": _count(db, CsDormRecord, tenant_id),
        "leaves": _count(db, CsLeave, tenant_id),
        "grants": _count(db, CsGrant, tenant_id),
        "dormExceptions": _count(db, CsDormException, tenant_id),
        "mentalCare": _count(db, CsMentalRecord, tenant_id),
        "workOrders": _count(db, CsWorkOrder, tenant_id),
    }
    expected = {
        "students": EXPECTED_CAMPUS_STUDENTS,
        "dormRecords": EXPECTED_DORM_ROWS,
        "leaves": 1625,
        "grants": 1857,
        "dormExceptions": 130,
        "mentalCare": 65,
        "workOrders": 325,
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if mismatches:
        raise RuntimeError(f"20K 在校生服务基线验收失败: {mismatches}")
    report["passed"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="建设标准沙箱学校迎新与学工演示数据")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只校验前置条件和展示计划")
    mode.add_argument("--confirm", action="store_true", help="执行迎新与学工阶段建设")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import (
        AffairsRiskRecord,
        CsServiceStudent,
        DormBuilding,
        OrientationStudent,
        Tenant,
        UnifiedMessage,
        UnifiedTodo,
    )
    from app.services.sandbox_school_academic_affairs_seed import validate_academic_affairs_facts
    from app.services.sandbox_school_affairs_runner import seed_school_affairs_20k
    from app.services.sandbox_school_affairs_seed import validate_affairs_facts
    from app.services.sandbox_school_domain_seed import _roster, _seed_campus, _seed_orientation
    from app.services.sandbox_school_master_seed import validate_school_master
    from app.services.sandbox_school_role_reconcile import validate_school_roles_20k

    if not db_enabled():
        print("[sandbox-student-affairs] 拒绝执行：DB_ENABLED=false")
        return 2

    tenant_id = SANDBOX_SCHOOL.tenant_id
    db = get_sessionmaker()()
    try:
        trial = db.get(Tenant, TRIAL_SCHOOL.tenant_id)
        target = db.get(Tenant, tenant_id)
        if trial is None or trial.tenant_code != TRIAL_SCHOOL.tenant_code:
            print("[sandbox-student-affairs] 拒绝执行：004 / trial-school 身份异常")
            return 3
        if target is None or target.tenant_code != SANDBOX_SCHOOL.tenant_code:
            print("[sandbox-student-affairs] 拒绝执行：007 / sandbox-school 身份异常")
            return 4

        master = validate_school_master(db, tenant_id)
        roles = validate_school_roles_20k(db, tenant_id)
        academic = validate_academic_affairs_facts(db, tenant_id)
        key_counts = {
            "orientationStudents": _count(db, OrientationStudent, tenant_id),
            "campusStudents": _count(db, CsServiceStudent, tenant_id),
            "dormBuildings": _count(db, DormBuilding, tenant_id),
            "affairsRisks": _count(db, AffairsRiskRecord, tenant_id),
            "unifiedMessages": _count(db, UnifiedMessage, tenant_id),
            "unifiedTodos": _count(db, UnifiedTodo, tenant_id),
        }
        plan = {
            "tenantId": str(tenant_id),
            "tenantCode": target.tenant_code,
            "masterPassed": master.get("passed"),
            "rolesPassed": roles.get("passed"),
            "academicPassed": academic.get("passed"),
            "currentKeyCounts": key_counts,
            "stages": [
                "DIGITAL_ORIENTATION_2026",
                "CAMPUS_STUDENT_SERVICE_2024_2025",
                "STUDENT_AFFAIRS_FULL_PROCESS",
            ],
            "unifiedCommunication": "DEFERRED_UNTIL_INTERNSHIP_EXISTS",
        }
        print("[sandbox-student-affairs] 建设计划：")
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
        if args.dry_run:
            if any(key_counts.values()):
                print("[sandbox-student-affairs] dry-run 发现已有学工关键数据，执行前需单独断点审计。")
            else:
                print("[sandbox-student-affairs] dry-run 完成，前置与空库条件通过。")
            return 0
        if any(key_counts.values()):
            print("[sandbox-student-affairs] 拒绝执行：学工关键表已有数据，不允许覆盖或重复写入。")
            return 5

        roster_2026 = _roster(db, tenant_id, grades=("2026",))
        roster_returning = _roster(db, tenant_id, grades=("2024", "2025"))
        if len(roster_2026) != 7000 or len(roster_returning) != 13000:
            raise RuntimeError(
                f"20K 学工学生范围异常：incoming={len(roster_2026)} returning={len(roster_returning)}"
            )

        orientation = _seed_orientation(db, tenant_id, roster_2026)
        orientation_validation = _validate_orientation(db, tenant_id)
        campus = _seed_campus(db, tenant_id, roster_returning)
        campus_validation = _validate_campus(db, tenant_id)
        affairs = seed_school_affairs_20k(db, tenant_id)
        affairs_validation = validate_affairs_facts(db, tenant_id)

        result = {
            "orientation": orientation,
            "campus": campus,
            "affairs": affairs,
            "acceptance": {
                "orientation": orientation_validation,
                "campus": campus_validation,
                "affairs": affairs_validation,
            },
            "unifiedCommunication": "DEFERRED_UNTIL_INTERNSHIP_EXISTS",
        }
        print("[sandbox-student-affairs] 建设完成：")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
