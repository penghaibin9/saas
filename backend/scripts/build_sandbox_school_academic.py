"""分阶段建设标准沙箱学校：阶段 2，教务运行与质量数据。

本阶段在已验收的 20K 学校主数据和角色权限底座上，按依赖顺序生成：

1. 学生学业成绩、补考背景和学业预警；
2. 学年学期、校历、课程、培养方案、注册、教学任务、课表、考务和成绩；
3. 32 个专业的课程快照收口；
4. 教材、教学评价和教学质量事实。

教务归档不在本步骤提前生成，待教务闭环和其他关联模块均验收后再单独执行。

用法：
  python scripts/build_sandbox_school_academic.py --dry-run
  python scripts/build_sandbox_school_academic.py --confirm

`--confirm` 可安全断点续跑：已通过验收的阶段只读校验后跳过，不重复写入。
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


def main() -> int:
    parser = argparse.ArgumentParser(description="建设标准沙箱学校教务演示数据")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只校验前置条件和展示计划")
    mode.add_argument("--confirm", action="store_true", help="执行教务阶段建设")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import (
        AaCourse,
        AaEvaluationBatch,
        AaTerm,
        AaTextbook,
        AcademicGrade,
        AcademicStudent,
        Tenant,
    )
    from app.services.sandbox_school_academic_affairs_seed import (
        seed_school_academic_affairs_20k,
        validate_academic_affairs_facts,
    )
    from app.services.sandbox_school_academic_quality_seed import (
        seed_school_academic_quality_20k,
        validate_school_academic_quality_20k,
    )
    from app.services.sandbox_school_academic_textbook_seed import (
        seed_school_academic_textbooks_20k,
        validate_school_academic_textbooks_20k,
    )
    from app.services.sandbox_school_domain_seed import (
        EXPECTED_ACADEMIC_STUDENTS,
        EXPECTED_GRADE_ROWS,
        _roster,
        _seed_academic,
    )
    from app.services.sandbox_school_master_seed import validate_school_master
    from app.services.sandbox_school_professional_runner import (
        professionalize_academic_fast,
        validate_professional_academic_snapshots,
    )
    from app.services.sandbox_school_role_reconcile import validate_school_roles_20k

    if not db_enabled():
        print("[sandbox-academic] 拒绝执行：DB_ENABLED=false")
        return 2

    tenant_id = SANDBOX_SCHOOL.tenant_id
    db = get_sessionmaker()()
    try:
        trial = db.get(Tenant, TRIAL_SCHOOL.tenant_id)
        target = db.get(Tenant, tenant_id)
        if trial is None or trial.tenant_code != TRIAL_SCHOOL.tenant_code:
            print("[sandbox-academic] 拒绝执行：004 / trial-school 身份异常")
            return 3
        if target is None or target.tenant_code != SANDBOX_SCHOOL.tenant_code:
            print("[sandbox-academic] 拒绝执行：007 / sandbox-school 身份异常")
            return 4

        master = validate_school_master(db, tenant_id)
        roles = validate_school_roles_20k(db, tenant_id)
        key_counts = {
            "academicStudents": _count(db, AcademicStudent, tenant_id),
            "academicGrades": _count(db, AcademicGrade, tenant_id),
            "terms": _count(db, AaTerm, tenant_id),
            "courses": _count(db, AaCourse, tenant_id),
            "textbooks": _count(db, AaTextbook, tenant_id),
            "evaluationBatches": _count(db, AaEvaluationBatch, tenant_id),
        }

        core_empty = key_counts["academicStudents"] == 0 and key_counts["academicGrades"] == 0
        core_complete = (
            key_counts["academicStudents"] == EXPECTED_ACADEMIC_STUDENTS
            and key_counts["academicGrades"] == EXPECTED_GRADE_ROWS
        )
        if not core_empty and not core_complete:
            print(
                "[sandbox-academic] 拒绝执行：学业核心数据处于非预期半成品状态，"
                f"students={key_counts['academicStudents']} grades={key_counts['academicGrades']}"
            )
            return 5

        affairs_empty = key_counts["terms"] == 0 and key_counts["courses"] == 0
        affairs_validation = None
        if not affairs_empty:
            try:
                affairs_validation = validate_academic_affairs_facts(db, tenant_id)
            except Exception as exc:
                print(f"[sandbox-academic] 拒绝执行：教务运行数据未通过断点验收：{exc}")
                return 6

        textbooks_empty = key_counts["textbooks"] == 0
        textbook_validation = None
        if not textbooks_empty:
            try:
                textbook_validation = validate_school_academic_textbooks_20k(db, tenant_id)
            except Exception as exc:
                print(f"[sandbox-academic] 拒绝执行：教材数据已存在但未通过验收：{exc}")
                return 7

        quality_empty = key_counts["evaluationBatches"] == 0
        quality_validation = None
        if not quality_empty:
            try:
                quality_validation = validate_school_academic_quality_20k(db, tenant_id)
            except Exception as exc:
                print(f"[sandbox-academic] 拒绝执行：教学质量数据已存在但未通过验收：{exc}")
                return 8

        stage_status = {
            "academicCore": "PENDING" if core_empty else "ACCEPTED",
            "academicAffairs": "PENDING" if affairs_empty else "ACCEPTED",
            "professionalCourseReconciliation": (
                "PENDING" if affairs_empty else "RECONCILE_IDEMPOTENTLY"
            ),
            "textbookManagement": "PENDING" if textbooks_empty else "ACCEPTED",
            "teachingQuality": "PENDING" if quality_empty else "ACCEPTED",
        }
        plan = {
            "tenantId": str(tenant_id),
            "tenantCode": target.tenant_code,
            "master": master,
            "roles": {"passed": roles.get("passed")},
            "currentKeyCounts": key_counts,
            "stageStatus": stage_status,
            "stages": [
                "ACADEMIC_STUDENT_GRADE_WARNING",
                "ACADEMIC_AFFAIRS_OPERATION",
                "PROFESSIONAL_COURSE_RECONCILIATION",
                "TEXTBOOK_MANAGEMENT",
                "TEACHING_QUALITY",
            ],
            "archive": "DEFERRED_TO_FINAL_CLOSURE",
        }
        print("[sandbox-academic] 建设计划：")
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))

        if args.dry_run:
            print("[sandbox-academic] dry-run 完成，未修改数据。")
            return 0

        if core_empty:
            roster = _roster(db, tenant_id, grades=("2024", "2025"))
            academic_core = _seed_academic(db, tenant_id, roster)
        else:
            academic_core = {
                "skipped": True,
                "reason": "ACCEPTED_CHECKPOINT",
                "academicStudents": key_counts["academicStudents"],
                "academicGrades": key_counts["academicGrades"],
            }

        if affairs_empty:
            academic_affairs = seed_school_academic_affairs_20k(db, tenant_id)
            affairs_validation = validate_academic_affairs_facts(db, tenant_id)
        else:
            academic_affairs = {"skipped": True, "reason": "ACCEPTED_CHECKPOINT"}
        if not affairs_validation.get("passed"):
            raise RuntimeError(f"教务运行基线验收失败：{affairs_validation}")

        # 教务阶段只做教务专业化，不提前触发实习和毕业设计数据。
        # 该函数仅对 canonical 名称和关系快照做幂等收口，可安全续跑。
        professional = professionalize_academic_fast(db, tenant_id)
        professional_validation = validate_professional_academic_snapshots(db, tenant_id)
        if not professional_validation.get("passed"):
            raise RuntimeError(f"专业课程快照验收失败：{professional_validation}")

        if textbooks_empty:
            textbooks = seed_school_academic_textbooks_20k(db, tenant_id)
            textbook_validation = validate_school_academic_textbooks_20k(db, tenant_id)
        else:
            textbooks = {"skipped": True, "reason": "ACCEPTED_CHECKPOINT"}
        if not textbook_validation.get("passed"):
            raise RuntimeError(f"教材数据验收失败：{textbook_validation}")

        if quality_empty:
            quality = seed_school_academic_quality_20k(db, tenant_id)
            quality_validation = validate_school_academic_quality_20k(db, tenant_id)
        else:
            quality = {"skipped": True, "reason": "ACCEPTED_CHECKPOINT"}
        if not quality_validation.get("passed"):
            raise RuntimeError(f"教学质量数据验收失败：{quality_validation}")

        result = {
            "academicCore": academic_core,
            "academicAffairs": academic_affairs,
            "professional": professional,
            "textbooks": textbooks,
            "quality": quality,
            "acceptance": {
                "academicAffairs": affairs_validation,
                "professionalSnapshots": professional_validation,
                "textbooks": textbook_validation,
                "quality": quality_validation,
            },
        }
        print("[sandbox-academic] 建设完成：")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
