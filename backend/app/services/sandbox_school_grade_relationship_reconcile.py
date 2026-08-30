"""Repair sandbox historical-grade relationships without changing grades or scores.

The sandbox originally bulk-inserted ``AcademicGrade`` rows before the formal
academic-affairs catalog existed.  That produced convincing row counts but left
the grades detached from term, course and immutable publish evidence.  This
reconciler restores those identities using deterministic, uniquely resolvable
catalog facts and appends one policy/identity snapshot for every legacy publish.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import bindparam, case, func, select, text, update

from app.core.context import get_tenant, set_tenant
from app.core.tenant_identity import SANDBOX_SCHOOL


PROVENANCE_TYPE = "EFFECTIVE_GRADE_POLICY_SNAPSHOT"
SNAPSHOT_SOURCE_TYPE = "SANDBOX_DEMO_BACKFILL"


def _require_sandbox(db, tenant_id: int) -> None:
    from app.models import Tenant

    tenant = db.scalar(select(Tenant).where(Tenant.id == int(tenant_id)))
    if (
        tenant is None
        or int(tenant.id) != int(SANDBOX_SCHOOL.tenant_id)
        or tenant.tenant_code != SANDBOX_SCHOOL.tenant_code
    ):
        raise RuntimeError("拒绝执行：成绩关系修复只允许 sandbox-school")


def _ensure_grade_term(db, tenant_id: int) -> int:
    from app.models import AaTerm

    row = db.scalar(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2024-2025",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    ))
    if row is None:
        row = AaTerm(
            tenant_id=tenant_id,
            year_code="2024-2025",
            term_no=1,
            term_name="2024-2025学年第一学期",
            start_date=datetime(2024, 9, 2),
            end_date=datetime(2025, 1, 17),
            teaching_weeks=18,
            exam_week_start=17,
            is_current=False,
            status="ARCHIVED",
        )
        db.add(row)
        db.flush()
    return int(row.id)


def _ensure_high_math_course(db, tenant_id: int) -> int:
    from app.models import AaCourse, AaProgramCourse

    high_math = db.scalar(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.course_name == "高等数学",
        AaCourse.is_deleted.is_(False),
    ))
    if high_math is not None:
        return int(high_math.id)

    course = db.scalar(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.course_code == "PUB013",
        AaCourse.is_deleted.is_(False),
    ).with_for_update())
    if course is None:
        raise RuntimeError("课程库缺少可治理的 PUB013 公共课程")
    if course.course_name != "大学语文":
        raise RuntimeError(f"PUB013 课程语义不可安全替换: {course.course_name}")
    course.course_name = "高等数学"
    course.description = "全校统一公共基础课程，与历史成绩和培养方案使用同一稳定课程身份。"
    db.execute(update(AaProgramCourse).where(
        AaProgramCourse.tenant_id == tenant_id,
        AaProgramCourse.course_id == int(course.id),
        AaProgramCourse.is_deleted.is_(False),
    ).values(course_name="高等数学"))
    db.flush()
    return int(course.id)


def _course_candidates(db, tenant_id: int):
    from app.models import AaCourse, Major

    majors = list(db.execute(select(Major.code, Major.major_name).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all())
    courses = list(db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_deleted.is_(False),
    )).all())
    result = {}
    for major in majors:
        by_name = {}
        for course in courses:
            code = str(course.course_code or "")
            if not course.is_all_major and not code.startswith(f"{major.code}-"):
                continue
            by_name.setdefault(str(course.course_name), []).append(course)
        duplicates = {name: rows for name, rows in by_name.items() if len(rows) != 1}
        if duplicates:
            sample = ",".join(sorted(duplicates)[:5])
            raise RuntimeError(f"课程身份不唯一 major={major.major_name}: {sample}")
        result[str(major.major_name)] = {name: rows[0] for name, rows in by_name.items()}
    return result


def _map_grade_courses(db, tenant_id: int) -> int:
    from app.models import AcademicGrade, AcademicStudent

    catalog = _course_candidates(db, tenant_id)
    total = 0
    for major_name, by_name in catalog.items():
        names = tuple(by_name)
        if not names:
            continue
        course_id_case = case(
            {name: int(row.id) for name, row in by_name.items()},
            value=AcademicGrade.course_name,
            else_=AcademicGrade.course_id,
        )
        course_code_case = case(
            {name: str(row.course_code) for name, row in by_name.items()},
            value=AcademicGrade.course_name,
            else_=AcademicGrade.course_code,
        )
        course_version_case = case(
            {name: int(row.version or 1) for name, row in by_name.items()},
            value=AcademicGrade.course_name,
            else_=AcademicGrade.course_version,
        )
        students = select(AcademicStudent.id).where(
            AcademicStudent.tenant_id == tenant_id,
            AcademicStudent.major_name == major_name,
            AcademicStudent.is_deleted.is_(False),
        )
        result = db.execute(update(AcademicGrade).where(
            AcademicGrade.tenant_id == tenant_id,
            AcademicGrade.acad_student_id.in_(students),
            AcademicGrade.course_name.in_(names),
            AcademicGrade.course_id.is_(None),
            AcademicGrade.is_deleted.is_(False),
        ).values(
            course_id=course_id_case,
            course_code=course_code_case,
            course_version=course_version_case,
            attempt_no=func.coalesce(AcademicGrade.attempt_no, 1),
        ))
        total += int(result.rowcount or 0)
    return total


def _link_existing_snapshots(db, tenant_id: int) -> int:
    result = db.execute(text("""
        UPDATE t_acad_grade g
        JOIN (
            SELECT academic_grade_id,MAX(id) snapshot_id
              FROM t_aa_effective_grade_policy_snapshot
             WHERE tenant_id=:tenant_id AND is_deleted=0
             GROUP BY academic_grade_id
        ) snap ON snap.academic_grade_id=g.id
           SET g.source_biz_type='EFFECTIVE_GRADE_POLICY_SNAPSHOT',
               g.source_biz_id=snap.snapshot_id
         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND g.source='PUBLISH'
           AND g.grade_task_id IS NULL AND g.source_biz_id IS NULL
    """), {"tenant_id": tenant_id})
    return int(result.rowcount or 0)


def _append_missing_snapshots(db, tenant_id: int, *, chunk_size: int = 1000) -> int:
    from app.models import AcademicGrade
    from app.models.academic_affairs_effective_grade import (
        AaEffectiveGradePolicy,
        AaEffectiveGradePolicySnapshot,
    )
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        _canonical,
        _hash,
        identity_snapshot,
        policy_payload,
    )

    policy = db.scalar(select(AaEffectiveGradePolicy).where(
        AaEffectiveGradePolicy.tenant_id == tenant_id,
        AaEffectiveGradePolicy.status == "ACTIVE",
        AaEffectiveGradePolicy.is_deleted.is_(False),
    ).order_by(
        AaEffectiveGradePolicy.effective_from_term_id.desc(),
        AaEffectiveGradePolicy.policy_version.desc(),
    ).limit(1))
    if policy is None:
        raise RuntimeError("没有 ACTIVE 有效成绩策略，拒绝生成历史发布凭证")
    policy_json = policy_payload(policy)
    total = 0
    last_id = 0
    update_stmt = AcademicGrade.__table__.update().where(
        AcademicGrade.__table__.c.id == bindparam("_grade_id")
    ).values(
        source_biz_type=PROVENANCE_TYPE,
        source_biz_id=bindparam("_snapshot_id"),
        effective_policy_code=bindparam("_policy_code"),
        effective_policy_version=bindparam("_policy_version"),
        effective_attempt_strategy=bindparam("_attempt_strategy"),
        pass_line_snapshot=func.coalesce(AcademicGrade.__table__.c.pass_line_snapshot, 60),
        attempt_no=func.coalesce(AcademicGrade.__table__.c.attempt_no, 1),
    )
    while True:
        grades = list(db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == tenant_id,
            AcademicGrade.source == "PUBLISH",
            AcademicGrade.grade_task_id.is_(None),
            AcademicGrade.source_biz_id.is_(None),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
            AcademicGrade.id > last_id,
        ).order_by(AcademicGrade.id).limit(chunk_size)).all())
        if not grades:
            break
        snapshots = []
        for grade in grades:
            if grade.course_id is None or not str(grade.course_code or "").strip():
                raise RuntimeError(f"成绩缺少稳定课程身份 grade={grade.id}")
            identity = identity_snapshot(grade)
            decision = {
                "academicGradeId": str(grade.id),
                "studentId": str(grade.acad_student_id or ""),
                "score": grade.score,
                "passStatus": grade.pass_status,
                "recordStatus": grade.record_status,
                "gradeSource": grade.source,
                "examType": grade.exam_type,
                "effectivePolicyCode": str(policy.policy_code),
                "effectivePolicyVersion": int(policy.policy_version or 1),
                "attemptStrategy": str(policy.attempt_strategy or "").upper(),
                "passLineSnapshot": int(grade.pass_line_snapshot or 60),
                **identity,
            }
            payload_hash = _hash({"policy": policy_json, "decision": decision})
            snapshots.append(AaEffectiveGradePolicySnapshot(
                tenant_id=tenant_id,
                academic_grade_id=int(grade.id),
                event_key=f"PUBLISH:{SNAPSHOT_SOURCE_TYPE}:{int(grade.id)}"[:160],
                event_type="PUBLISH",
                source_biz_type=SNAPSHOT_SOURCE_TYPE,
                source_biz_id=int(grade.id),
                policy_code=str(policy.policy_code),
                policy_version=int(policy.policy_version or 1),
                policy_json=_canonical(policy_json),
                policy_hash=payload_hash,
                identity_type=identity["identityType"],
                identity_key=identity["identityKey"][:300],
                course_id=identity["courseId"],
                course_code=identity["courseCode"],
                course_version=identity["courseVersion"],
                attempt_no=identity["attemptNo"] or 1,
                grade_source=str(grade.source or "") or None,
                decision_json=_canonical(decision),
            ))
        db.add_all(snapshots)
        db.flush()
        db.execute(update_stmt, [{
            "_grade_id": int(grade.id),
            "_snapshot_id": int(snapshot.id),
            "_policy_code": str(policy.policy_code),
            "_policy_version": int(policy.policy_version or 1),
            "_attempt_strategy": str(policy.attempt_strategy or "").upper(),
        } for grade, snapshot in zip(grades, snapshots)])
        total += len(grades)
        last_id = int(grades[-1].id)
        db.commit()
    return total


def reconcile_sandbox_grade_relationships(db, tenant_id: int) -> dict:
    """Apply deterministic relationship repair and return acceptance counts."""
    from app.models import AcademicAuditTrail

    tenant_id = int(tenant_id)
    _require_sandbox(db, tenant_id)
    previous = get_tenant()
    set_tenant({"tenantId": str(tenant_id), "tenantCode": SANDBOX_SCHOOL.tenant_code})
    try:
        term_id = _ensure_grade_term(db, tenant_id)
        high_math_course_id = _ensure_high_math_course(db, tenant_id)
        course_rows_updated = _map_grade_courses(db, tenant_id)
        db.commit()
        existing_snapshots_linked = _link_existing_snapshots(db, tenant_id)
        db.commit()
        snapshots_appended = _append_missing_snapshots(db, tenant_id)

        broken_courses = int(db.execute(text("""
            SELECT COUNT(*) FROM t_acad_grade g
            LEFT JOIN t_aa_course c ON c.id=g.course_id AND c.tenant_id=g.tenant_id AND c.is_deleted=0
            WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND c.id IS NULL
        """), {"tenant_id": tenant_id}).scalar() or 0)
        broken_provenance = int(db.execute(text("""
            SELECT COUNT(*) FROM t_acad_grade g
            LEFT JOIN t_aa_grade_task gt
              ON gt.id=g.grade_task_id AND gt.tenant_id=g.tenant_id AND gt.is_deleted=0
            LEFT JOIN t_aa_effective_grade_policy_snapshot snap
              ON snap.id=g.source_biz_id AND snap.tenant_id=g.tenant_id
             AND snap.academic_grade_id=g.id AND snap.is_deleted=0
            WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND g.source='PUBLISH'
              AND gt.id IS NULL
              AND NOT (g.source_biz_type='EFFECTIVE_GRADE_POLICY_SNAPSHOT' AND snap.id IS NOT NULL)
        """), {"tenant_id": tenant_id}).scalar() or 0)
        if broken_courses or broken_provenance:
            raise RuntimeError(
                f"成绩关系修复后仍未闭合 courses={broken_courses} provenance={broken_provenance}"
            )
        db.add(AcademicAuditTrail(
            tenant_id=tenant_id,
            biz_type="SANDBOX_GRADE_RELATIONSHIP",
            action="RECONCILE",
            operator="sandbox-grade-reconcile",
            role_name="SYSTEM",
            detail=(
                f"courseRowsUpdated={course_rows_updated};"
                f"existingSnapshotsLinked={existing_snapshots_linked};"
                f"snapshotsAppended={snapshots_appended};termId={term_id};"
                f"highMathCourseId={high_math_course_id}"
            ),
            occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return {
            "gradeTermId": term_id,
            "highMathCourseId": high_math_course_id,
            "courseRowsUpdated": course_rows_updated,
            "existingSnapshotsLinked": existing_snapshots_linked,
            "snapshotsAppended": snapshots_appended,
            "brokenCourses": broken_courses,
            "brokenProvenance": broken_provenance,
        }
    finally:
        set_tenant(previous)
