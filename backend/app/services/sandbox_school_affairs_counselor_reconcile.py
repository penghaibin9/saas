"""20K 售前学校 · 辅导员考评周期对账。

主数据把学校收敛为 96 名辅导员（384 班、每人约 4 班）后，旧 13A 种子仍只会给
2024/2025 两届在校老生的 64 名辅导员生成一个历史学期考评。这里不把辅导员人数改回
不现实的 192，而是按当前 96 名责任辅导员重建两类可解释的管理考评：
- 2025-2026 学年年度综合考评；
- 2026-2027 学年开学准备专项考评。

每名辅导员两个周期各一条，共 192 条；班级数和学生覆盖均从真实 SchoolClass / StudentProfile
关系统计，不造孤立 marker。
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.services.sandbox_school_master_seed import _bulk_insert

EXPECTED_COUNSELORS = 96
EXPECTED_ASSESSMENTS = 192


def reconcile_counselor_assessments(db, tenant_id: int) -> dict:
    from app.models import (
        AffairsCounselorAssessment,
        AffairsCounselorAssessmentPeriod,
        SchoolClass,
        StudentProfile,
        User,
    )

    stats = list(db.execute(
        select(
            SchoolClass.counselor_id,
            func.count(func.distinct(SchoolClass.id)).label("class_count"),
            func.count(StudentProfile.id).label("student_count"),
        )
        .join(StudentProfile, StudentProfile.class_id == SchoolClass.id)
        .where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.grade.in_(("2024", "2025", "2026")),
            SchoolClass.counselor_id.is_not(None),
            SchoolClass.is_deleted.is_(False),
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        .group_by(SchoolClass.counselor_id)
        .order_by(SchoolClass.counselor_id)
    ).all())
    if len(stats) != EXPECTED_COUNSELORS:
        raise RuntimeError(f"20K 辅导员责任人数异常: expected={EXPECTED_COUNSELORS} actual={len(stats)}")
    if any(int(row.class_count) != 4 for row in stats):
        bad = [(int(row.counselor_id), int(row.class_count)) for row in stats if int(row.class_count) != 4]
        raise RuntimeError(f"20K 辅导员班级负载异常: {bad[:10]}")

    counselor_ids = [int(row.counselor_id) for row in stats]
    names = {
        int(uid): name
        for uid, name in db.execute(select(User.id, User.real_name).where(
            User.tenant_id == tenant_id,
            User.id.in_(counselor_ids),
            User.is_deleted.is_(False),
        )).all()
    }
    if len(names) != EXPECTED_COUNSELORS:
        raise RuntimeError(f"辅导员账号关系不完整: expected={EXPECTED_COUNSELORS} actual={len(names)}")

    # 旧种子的单周期记录属于同一固定 sandbox-school，先按租户清掉再重建两套一致口径。
    db.execute(delete(AffairsCounselorAssessment).where(
        AffairsCounselorAssessment.tenant_id == tenant_id,
    ))
    db.execute(delete(AffairsCounselorAssessmentPeriod).where(
        AffairsCounselorAssessmentPeriod.tenant_id == tenant_id,
    ))
    db.flush()

    annual = AffairsCounselorAssessmentPeriod(
        tenant_id=tenant_id,
        period_name="2025-2026学年辅导员年度综合考评",
        semester="2025-2026",
        status="PUBLISHED",
        remark="按当前责任班级、学生覆盖、谈心谈话、风险闭环、资助与宿舍工作形成年度综合考评。",
    )
    opening = AffairsCounselorAssessmentPeriod(
        tenant_id=tenant_id,
        period_name="2026-2027学年开学准备专项考评",
        semester="2026-2027-1-PREP",
        status="PUBLISHED",
        remark="覆盖老生返校、新生迎新、宿舍入住、重点学生交接与班级开学准备工作。",
    )
    db.add_all([annual, opening])
    db.flush()

    rows: list[dict] = []
    periods = (
        (annual, "ANNUAL", datetime(2026, 7, 15, 10, 0)),
        (opening, "OPENING_PREP", datetime(2026, 8, 12, 16, 0)),
    )
    for period, kind, scored_at in periods:
        ranked = []
        for idx, stat in enumerate(stats, 1):
            if kind == "ANNUAL":
                auto = Decimal(str(82 + (idx % 12)))
                college = Decimal(str(81 + ((idx * 5) % 14)))
            else:
                auto = Decimal(str(84 + (idx % 10)))
                college = Decimal(str(83 + ((idx * 3) % 12)))
            total = (auto * Decimal("0.6") + college * Decimal("0.4")).quantize(Decimal("0.1"))
            ranked.append((total, stat, auto, college))
        ranked.sort(key=lambda item: (-item[0], int(item[1].counselor_id)))

        for rank_no, (total, stat, auto, college) in enumerate(ranked, 1):
            uid = int(stat.counselor_id)
            student_count = int(stat.student_count)
            class_count = int(stat.class_count)
            if kind == "ANNUAL":
                metrics = {
                    "studentCoverage": student_count,
                    "classCount": class_count,
                    "talkRecords": 8 + rank_no % 9,
                    "riskClosures": 2 + rank_no % 6,
                    "familyContacts": 3 + rank_no % 5,
                    "aidFollowups": 4 + rank_no % 7,
                    "dormVisits": 5 + rank_no % 6,
                }
            else:
                metrics = {
                    "studentCoverage": student_count,
                    "classCount": class_count,
                    "returningReadiness": 92 + rank_no % 8,
                    "orientationReadiness": 90 + rank_no % 10,
                    "dormReadiness": 91 + rank_no % 9,
                    "riskHandoverCompleted": 3 + rank_no % 7,
                    "classMeetingPrepared": class_count,
                }
            rows.append({
                "tenant_id": tenant_id,
                "period_id": int(period.id),
                "counselor_id": uid,
                "counselor_name": names[uid],
                "class_count": class_count,
                "student_count": student_count,
                "metrics_json": json.dumps(metrics, ensure_ascii=False),
                "auto_score": auto,
                "college_score": college,
                "total_score": total,
                "rank_no": rank_no,
                "status": "SCORED",
                "scored_by": "学生工作处",
                "scored_at": scored_at,
            })

    _bulk_insert(db, AffairsCounselorAssessment, rows, chunk_size=500)
    db.commit()
    if len(rows) != EXPECTED_ASSESSMENTS:
        raise RuntimeError(f"辅导员考评记录异常: expected={EXPECTED_ASSESSMENTS} actual={len(rows)}")
    return {
        "counselors": EXPECTED_COUNSELORS,
        "periods": 2,
        "assessments": len(rows),
        "classesPerCounselor": 4,
        "averageStudentsPerCounselor": round(
            sum(int(row.student_count) for row in stats) / EXPECTED_COUNSELORS, 2
        ),
    }
