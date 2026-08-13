"""13A 真实学校数据编排器。

把学工高频种子按固定顺序执行；风险中枢使用“从真实来源池取足 300 条”策略，
不假设每个来源必须恰好有多少条，也不在来源不足时造 marker 记录。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.services.sandbox_school_affairs_seed import (
    EXPECTED_AFFAIRS_RISKS,
    _returning_roster,
    _seed_aid_and_funding,
    _seed_class_and_counselor,
    _seed_discipline,
    _seed_dorm_inventory,
    _seed_talks_and_family,
    validate_affairs_facts,
)
from app.services.sandbox_school_affairs_counselor_reconcile import (
    reconcile_counselor_assessments,
)
from app.services.sandbox_school_master_seed import _bulk_insert


def _seed_real_source_risks(db, tenant_id: int) -> dict:
    from app.models import (
        AcademicStudent,
        AcademicWarning,
        AffairsRiskRecord,
        CsDormException,
        CsServiceStudent,
        InternshipRecord,
        RiskRecord,
        SchoolClass,
        StudentProfile,
    )

    candidates: list[dict] = []

    academic = db.execute(
        select(AcademicWarning.id, AcademicStudent.student_id)
        .join(AcademicStudent, AcademicStudent.id == AcademicWarning.acad_student_id)
        .where(
            AcademicWarning.tenant_id == tenant_id,
            AcademicWarning.status == "PENDING_HANDLE",
            AcademicWarning.is_deleted.is_(False),
            AcademicStudent.is_deleted.is_(False),
        )
        .order_by(AcademicWarning.id)
        .limit(EXPECTED_AFFAIRS_RISKS)
    ).all()
    candidates.extend({
        "source": "ACADEMIC_WARNING",
        "ref": int(row.id),
        "student_id": int(row.student_id),
        "title": "学业预警待辅导员跟进",
    } for row in academic)

    dorm = db.execute(
        select(CsDormException.id, CsServiceStudent.student_id)
        .join(CsServiceStudent, CsServiceStudent.id == CsDormException.cs_student_id)
        .where(
            CsDormException.tenant_id == tenant_id,
            CsDormException.status.in_(("PENDING_HANDLE", "PROCESSING")),
            CsDormException.is_deleted.is_(False),
            CsServiceStudent.is_deleted.is_(False),
        )
        .order_by(CsDormException.id)
        .limit(EXPECTED_AFFAIRS_RISKS)
    ).all()
    candidates.extend({
        "source": "DORM",
        "ref": int(row.id),
        "student_id": int(row.student_id),
        "title": "宿舍异常需要跟进核实",
    } for row in dorm)

    internship = db.execute(
        select(RiskRecord.id, InternshipRecord.student_id)
        .join(InternshipRecord, InternshipRecord.id == RiskRecord.internship_id)
        .where(
            RiskRecord.tenant_id == tenant_id,
            RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
            RiskRecord.is_deleted.is_(False),
            InternshipRecord.is_deleted.is_(False),
        )
        .order_by(RiskRecord.id)
        .limit(EXPECTED_AFFAIRS_RISKS)
    ).all()
    candidates.extend({
        "source": "INTERNSHIP",
        "ref": int(row.id),
        "student_id": int(row.student_id),
        "title": "岗位实习风险需要继续处置",
    } for row in internship)

    # 优先保证来源多样：先每类轮流取，再用剩余真实来源补足。
    by_source: dict[str, list[dict]] = {}
    for row in candidates:
        by_source.setdefault(row["source"], []).append(row)
    selected: list[dict] = []
    source_order = ("ACADEMIC_WARNING", "DORM", "INTERNSHIP")
    cursor = 0
    while len(selected) < EXPECTED_AFFAIRS_RISKS:
        progressed = False
        for source in source_order:
            rows = by_source.get(source, [])
            if cursor < len(rows):
                selected.append(rows[cursor])
                progressed = True
                if len(selected) == EXPECTED_AFFAIRS_RISKS:
                    break
        if not progressed:
            break
        cursor += 1

    # 若短来源先耗尽，再从仍有余额的真实来源继续取满。
    if len(selected) < EXPECTED_AFFAIRS_RISKS:
        used = {(x["source"], x["ref"]) for x in selected}
        for row in candidates:
            key = (row["source"], row["ref"])
            if key in used:
                continue
            selected.append(row)
            used.add(key)
            if len(selected) == EXPECTED_AFFAIRS_RISKS:
                break

    if len(selected) < EXPECTED_AFFAIRS_RISKS:
        raise RuntimeError(
            f"学工风险真实来源不足: available={len(selected)}, required={EXPECTED_AFFAIRS_RISKS}"
        )

    student_ids = [x["student_id"] for x in selected]
    owner_by_student = {
        int(student_id): int(counselor_id)
        for student_id, counselor_id in db.execute(
            select(StudentProfile.id, SchoolClass.counselor_id)
            .join(SchoolClass, SchoolClass.id == StudentProfile.class_id)
            .where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.id.in_(student_ids),
                SchoolClass.counselor_id.is_not(None),
            )
        ).all()
    }
    rows = []
    for idx, item in enumerate(selected, 1):
        rows.append({
            "tenant_id": tenant_id,
            "student_id": item["student_id"],
            "source": item["source"],
            "source_ref_id": item["ref"],
            "risk_level": "HIGH" if idx % 20 == 0 else "MEDIUM",
            "title": item["title"],
            "detail": "风险详情保留在来源单据，学工风险中枢只保存引用、等级、责任人与处置状态。",
            "owner_id": owner_by_student.get(item["student_id"]),
            "deadline_at": datetime(2026, 8, 18, 18, 0),
            "assigned_at": datetime(2026, 8, 12, 9, 0),
            "status": "PROCESSING" if idx % 3 == 0 else "ASSIGNED",
            "is_archived": False,
        })
    _bulk_insert(db, AffairsRiskRecord, rows, chunk_size=500)
    db.commit()
    return {
        "riskRecords": len(rows),
        "sourceCounts": {
            source: sum(1 for x in selected if x["source"] == source)
            for source in source_order
        },
    }


def seed_school_affairs_20k(db, tenant_id: int) -> dict:
    roster = _returning_roster(db, tenant_id)
    if len(roster) != 13_000:
        raise RuntimeError(f"13A 老生基数应为 13000，实际 {len(roster)}")
    result = {
        "dorm": _seed_dorm_inventory(db, tenant_id),
        "classAndCounselor": _seed_class_and_counselor(db, tenant_id, roster),
    }
    # 主数据现在是 96 名辅导员/384 班；旧班级种子只覆盖 2024/2025 两届 64 名责任人。
    # 在继续生成其它学工事实前，把全校 96 名辅导员的年度+开学专项考评统一重建为 192 条。
    result["counselorAssessmentReconciliation"] = reconcile_counselor_assessments(db, tenant_id)
    result.update({
        "talkAndFamily": _seed_talks_and_family(db, tenant_id, roster),
        "aidAndFunding": _seed_aid_and_funding(db, tenant_id, roster),
        "discipline": _seed_discipline(db, tenant_id, roster),
        "riskHub": _seed_real_source_risks(db, tenant_id),
    })
    result["validation"] = validate_affairs_facts(db, tenant_id)
    return result
