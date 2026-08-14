"""sandbox-school · 历史教务归档前置事实补齐。

只服务 standard-20k 售前学校，不修改生产教务 service：
- 96 份培养方案补正式 major+grade ACTIVE 绑定；
- 2025-2026-2 生成 2024/2025 两届 13,000 人真实学期注册明细；
- 历史课表保持 PUBLISHED，由归档批次承担 ARCHIVED 语义；
- 2025-2026-2 的 52,000 条 AcademicGrade 补稳定课程身份与不可变有效成绩策略快照。

这些数据都在正式十三域归档 policy 运行前生成；policy 本身不放宽、不 monkeypatch。
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import case, func, select, update

from app.core.context import get_tenant, set_tenant
from app.services.sandbox_school_master_seed import _bulk_insert
from app.services.sandbox_school_professional_catalog import professional_profile
from app.services.sandbox_school_professional_reconcile import (
    ADVANCED_MAJOR_COURSE_LABELS,
    _major_specs,
)

HISTORICAL_TERM_CODE = "2025-2026-2"
EXPECTED_PROGRAM_BINDINGS = 96
EXPECTED_SPRING_REGISTRATIONS = 13_000
EXPECTED_HISTORICAL_GRADE_ROWS = 52_000
POLICY_CODE = "LATEST_FORMAL_SOURCE_V1"
POLICY_VERSION = 1
ATTEMPT_STRATEGY = "LATEST_ATTEMPT"


def _term(db, tenant_id: int):
    from app.models import AaTerm

    term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2025-2026",
        AaTerm.term_no == 2,
        AaTerm.is_deleted.is_(False),
    )).one_or_none()
    if term is None:
        raise RuntimeError("历史归档补齐缺少 2025-2026-2 学期")
    return term


def _seed_program_bindings(db, tenant_id: int) -> dict:
    from app.models import AaProgram, AaProgramBinding

    existing = int(db.scalar(select(func.count()).select_from(AaProgramBinding).where(
        AaProgramBinding.tenant_id == tenant_id,
        AaProgramBinding.is_deleted.is_(False),
    )) or 0)
    if existing:
        if existing != EXPECTED_PROGRAM_BINDINGS:
            raise RuntimeError(f"培养方案绑定已有异常数据 expected={EXPECTED_PROGRAM_BINDINGS} actual={existing}")
        return {"programBindings": existing, "created": 0}

    programs = list(db.execute(select(
        AaProgram.id, AaProgram.major_id, AaProgram.grade_year,
    ).where(
        AaProgram.tenant_id == tenant_id,
        AaProgram.status == "ENABLED",
        AaProgram.is_deleted.is_(False),
    ).order_by(AaProgram.major_id, AaProgram.grade_year)).all())
    if len(programs) != EXPECTED_PROGRAM_BINDINGS:
        raise RuntimeError(
            f"培养方案主档无法形成 32专业×3年级绑定 expected={EXPECTED_PROGRAM_BINDINGS} actual={len(programs)}"
        )

    rows = []
    for program in programs:
        grade = str(program.grade_year or "")
        rows.append({
            "tenant_id": tenant_id,
            "program_id": int(program.id),
            "major_id": int(program.major_id),
            "grade_year": grade,
            "class_id": None,
            "bound_at": datetime(int(grade), 7, 15, 9, 0),
            "status": "ACTIVE",
        })
    _bulk_insert(db, AaProgramBinding, rows, chunk_size=500)
    db.commit()
    return {"programBindings": len(rows), "created": len(rows)}


def _seed_spring_registration(db, tenant_id: int, term_id: int) -> dict:
    from app.models import AaRegistration, AaRegistrationBatch, StudentProfile

    batch = db.scalars(select(AaRegistrationBatch).where(
        AaRegistrationBatch.tenant_id == tenant_id,
        AaRegistrationBatch.term_id == int(term_id),
        AaRegistrationBatch.batch_name == "2025-2026学年第二学期在校生学期注册",
        AaRegistrationBatch.is_deleted.is_(False),
    )).one_or_none()
    if batch is None:
        batch = AaRegistrationBatch(
            tenant_id=tenant_id,
            batch_name="2025-2026学年第二学期在校生学期注册",
            register_type="SEMESTER",
            term_id=int(term_id),
            window_start=datetime(2026, 2, 16, 8, 0),
            window_end=datetime(2026, 2, 27, 18, 0),
            scope_json='{"grades":["2024","2025"],"mode":"SEMESTER_CONFIRM"}',
            status="ARCHIVED",
        )
        db.add(batch)
        db.flush()

    current = int(db.scalar(select(func.count()).select_from(AaRegistration).where(
        AaRegistration.tenant_id == tenant_id,
        AaRegistration.batch_id == int(batch.id),
        AaRegistration.is_deleted.is_(False),
    )) or 0)
    if current not in {0, EXPECTED_SPRING_REGISTRATIONS}:
        raise RuntimeError(
            f"历史春季注册明细异常 expected=0/{EXPECTED_SPRING_REGISTRATIONS} actual={current}"
        )
    if current == 0:
        students = list(db.execute(select(
            StudentProfile.id, StudentProfile.grade,
        ).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.grade.in_(("2024", "2025")),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.student_no)).all())
        if len(students) != EXPECTED_SPRING_REGISTRATIONS:
            raise RuntimeError(
                f"春季注册学生基数异常 expected={EXPECTED_SPRING_REGISTRATIONS} actual={len(students)}"
            )
        rows = [{
            "tenant_id": tenant_id,
            "batch_id": int(batch.id),
            "student_id": int(student.id),
            "precheck_json": '{"studentStatus":"PASS","finance":"PASS","discipline":"PASS"}',
            "register_at": datetime(2026, 2, 20, 9, 0),
            "status": "REGISTERED",
            "eligibility_status": "ELIGIBLE",
            "eligibility_note": "在校学籍、缴费与学期注册资格核验通过",
            "eligibility_checked_at": datetime(2026, 2, 19, 15, 0),
        } for student in students]
        _bulk_insert(db, AaRegistration, rows, chunk_size=1000)
        db.commit()
        current = len(rows)
    return {"springRegistrationBatchId": int(batch.id), "springRegistrations": current}


def _normalize_historical_schedule(db, tenant_id: int, term_id: int) -> dict:
    from app.models import AaScheduleBatch

    batches = list(db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == tenant_id,
        AaScheduleBatch.term_id == int(term_id),
        AaScheduleBatch.is_deleted.is_(False),
    )).all())
    if len(batches) != 1:
        raise RuntimeError(f"历史正式课表批次异常 expected=1 actual={len(batches)}")
    batch = batches[0]
    before = str(batch.status or "")
    if before not in {"PUBLISHED", "ARCHIVED"}:
        raise RuntimeError(f"历史课表存在非正式状态: {before}")
    if before == "ARCHIVED":
        batch.status = "PUBLISHED"
        db.commit()
    return {"scheduleBatchId": int(batch.id), "statusBefore": before, "statusAfter": "PUBLISHED"}


def _course_identity_catalog(db, tenant_id: int) -> dict[str, dict[str, tuple[int | None, str]]]:
    """major_name -> canonical course name -> (course_id?, stable course_code)."""
    from app.models import AaCourse, Major

    major_rows = list(db.execute(select(Major.id, Major.code, Major.major_name).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all())
    if len(major_rows) != 32:
        raise RuntimeError(f"成绩课程身份治理专业基数异常: {len(major_rows)}")

    course_rows = list(db.execute(select(
        AaCourse.id, AaCourse.course_code, AaCourse.course_name,
    ).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_deleted.is_(False),
    )).all())
    course_by_code = {str(row.course_code): row for row in course_rows}

    result: dict[str, dict[str, tuple[int | None, str]]] = {}
    for major in major_rows:
        profile = professional_profile(str(major.major_name))
        by_name: dict[str, tuple[int | None, str]] = {}
        for index, name in enumerate(profile.core_courses, 1):
            code = f"{major.code}-{index:02d}"
            row = course_by_code.get(code)
            if row is None:
                raise RuntimeError(f"正式课程库缺少 {code} ({name})")
            by_name[str(name)] = (int(row.id), code)
        for offset, label in enumerate(ADVANCED_MAJOR_COURSE_LABELS, len(profile.core_courses) + 1):
            # 后三门是历史方案课程：当前课程库未保留版本行，使用稳定历史课程代码，禁止冒充其它 course_id。
            by_name[f"{major.major_name}{label}"] = (None, f"{major.code}-{offset:02d}")
        if len(by_name) != 9:
            raise RuntimeError(f"专业课程身份目录异常 major={major.major_name} count={len(by_name)}")
        result[str(major.major_name)] = by_name
    return result


def _ensure_effective_policy(db, tenant_id: int, term_id: int):
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    policy = db.scalars(select(AaEffectiveGradePolicy).where(
        AaEffectiveGradePolicy.tenant_id == tenant_id,
        AaEffectiveGradePolicy.policy_code == POLICY_CODE,
        AaEffectiveGradePolicy.policy_version == POLICY_VERSION,
        AaEffectiveGradePolicy.is_deleted.is_(False),
    )).one_or_none()
    if policy is None:
        policy = AaEffectiveGradePolicy(
            tenant_id=tenant_id,
            policy_code=POLICY_CODE,
            policy_version=POLICY_VERSION,
            active_scope_key=str(term_id),
            attempt_strategy=ATTEMPT_STRATEGY,
            makeup_strategy="CAP_AND_OVERRIDE",
            makeup_cap=60,
            retake_strategy="REPLACE_IF_PASSED",
            recognition_priority=75,
            effective_from_term_id=int(term_id),
            status="ACTIVE",
            activated_at=datetime(2026, 2, 1, 9, 0),
        )
        db.add(policy)
        db.flush()
    return policy


def _normalize_grade_identities(db, tenant_id: int, term_id: int) -> dict:
    from app.models import AcademicGrade, AcademicStudent
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicySnapshot
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        _canonical,
        _hash,
        identity_snapshot,
        policy_payload,
    )

    catalog = _course_identity_catalog(db, tenant_id)
    policy = _ensure_effective_policy(db, tenant_id, term_id)

    students_by_major = {
        major_name: select(AcademicStudent.id).where(
            AcademicStudent.tenant_id == tenant_id,
            AcademicStudent.major_name == major_name,
            AcademicStudent.is_deleted.is_(False),
        )
        for major_name in catalog
    }
    updated = 0
    for major_name, by_name in catalog.items():
        name_to_code = {name: code for name, (_course_id, code) in by_name.items()}
        name_to_course_id = {name: course_id for name, (course_id, _code) in by_name.items() if course_id is not None}
        names = tuple(name_to_code)
        if not names:
            continue
        code_case = case(name_to_code, value=AcademicGrade.course_name, else_=AcademicGrade.course_code)
        id_case = case(name_to_course_id, value=AcademicGrade.course_name, else_=AcademicGrade.course_id)
        res = db.execute(update(AcademicGrade).where(
            AcademicGrade.tenant_id == tenant_id,
            AcademicGrade.term == HISTORICAL_TERM_CODE,
            AcademicGrade.acad_student_id.in_(students_by_major[major_name]),
            AcademicGrade.course_name.in_(names),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).values(
            course_id=id_case,
            course_code=code_case,
            course_version=1,
            attempt_no=1,
            effective_policy_code=POLICY_CODE,
            effective_policy_version=POLICY_VERSION,
            effective_attempt_strategy=ATTEMPT_STRATEGY,
            pass_line_snapshot=60,
        ))
        updated += int(res.rowcount or 0)
    db.commit()
    if updated != EXPECTED_HISTORICAL_GRADE_ROWS:
        raise RuntimeError(
            f"历史成绩稳定课程身份更新异常 expected={EXPECTED_HISTORICAL_GRADE_ROWS} actual={updated}"
        )

    existing_snapshots = int(db.scalar(select(func.count()).select_from(AaEffectiveGradePolicySnapshot).where(
        AaEffectiveGradePolicySnapshot.tenant_id == tenant_id,
        AaEffectiveGradePolicySnapshot.event_type == "PUBLISH",
        AaEffectiveGradePolicySnapshot.source_biz_type == "SANDBOX_ARCHIVE_BACKFILL",
        AaEffectiveGradePolicySnapshot.is_deleted.is_(False),
    )) or 0)
    if existing_snapshots not in {0, EXPECTED_HISTORICAL_GRADE_ROWS}:
        raise RuntimeError(
            f"历史成绩策略快照残留异常 expected=0/{EXPECTED_HISTORICAL_GRADE_ROWS} actual={existing_snapshots}"
        )
    if existing_snapshots == 0:
        policy_json = policy_payload(policy)
        last_id = 0
        inserted = 0
        while True:
            grades = list(db.scalars(select(AcademicGrade).where(
                AcademicGrade.tenant_id == tenant_id,
                AcademicGrade.term == HISTORICAL_TERM_CODE,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
                AcademicGrade.id > last_id,
            ).order_by(AcademicGrade.id).limit(1500)).all())
            if not grades:
                break
            rows = []
            for grade in grades:
                identity = identity_snapshot(grade)
                if identity["identityType"] == "LEGACY_NAME_KEY":
                    raise RuntimeError(f"历史成绩仍缺稳定课程身份 grade={grade.id}")
                decision = {
                    "academicGradeId": str(grade.id),
                    "studentId": str(grade.acad_student_id or ""),
                    "score": grade.score,
                    "passStatus": grade.pass_status,
                    "recordStatus": grade.record_status,
                    "gradeSource": grade.source,
                    "examType": grade.exam_type,
                    "effectivePolicyCode": grade.effective_policy_code,
                    "effectivePolicyVersion": grade.effective_policy_version,
                    "attemptStrategy": grade.effective_attempt_strategy,
                    "passLineSnapshot": grade.pass_line_snapshot,
                    **identity,
                }
                payload_hash = _hash({"policy": policy_json, "decision": decision})
                rows.append({
                    "tenant_id": tenant_id,
                    "academic_grade_id": int(grade.id),
                    "event_key": f"PUBLISH:SANDBOX_ARCHIVE_BACKFILL:{int(grade.id)}",
                    "event_type": "PUBLISH",
                    "source_biz_type": "SANDBOX_ARCHIVE_BACKFILL",
                    "source_biz_id": int(grade.id),
                    "policy_code": POLICY_CODE,
                    "policy_version": POLICY_VERSION,
                    "policy_json": _canonical(policy_json),
                    "policy_hash": payload_hash,
                    "identity_type": identity["identityType"],
                    "identity_key": identity["identityKey"][:300],
                    "course_id": identity["courseId"],
                    "course_code": identity["courseCode"],
                    "course_version": identity["courseVersion"],
                    "attempt_no": identity["attemptNo"],
                    "grade_source": str(grade.source or "") or None,
                    "decision_json": _canonical(decision),
                })
            _bulk_insert(db, AaEffectiveGradePolicySnapshot, rows, chunk_size=1500)
            inserted += len(rows)
            last_id = int(grades[-1].id)
            db.commit()
        existing_snapshots = inserted
    return {
        "historicalGradeIdentities": updated,
        "historicalGradePolicySnapshots": existing_snapshots,
        "policyCode": POLICY_CODE,
        "policyVersion": POLICY_VERSION,
    }


def seed_school_academic_archive_prerequisites_20k(db, tenant_id: int) -> dict:
    term = _term(db, tenant_id)
    result = {
        "programBindings": _seed_program_bindings(db, tenant_id),
        "springRegistration": _seed_spring_registration(db, tenant_id, int(term.id)),
        "historicalSchedule": _normalize_historical_schedule(db, tenant_id, int(term.id)),
        "historicalGrades": _normalize_grade_identities(db, tenant_id, int(term.id)),
    }
    result["validation"] = validate_school_academic_archive_prerequisites_20k(db, tenant_id)
    return result


def validate_school_academic_archive_prerequisites_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaProgramBinding,
        AaRegistration,
        AaRegistrationBatch,
        AaScheduleBatch,
        AcademicGrade,
    )
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicySnapshot
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        grade_identity_key,
        policy_snapshot_debt,
    )

    term = _term(db, tenant_id)
    bindings = int(db.scalar(select(func.count()).select_from(AaProgramBinding).where(
        AaProgramBinding.tenant_id == tenant_id,
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    )) or 0)
    batch = db.scalars(select(AaRegistrationBatch).where(
        AaRegistrationBatch.tenant_id == tenant_id,
        AaRegistrationBatch.term_id == int(term.id),
        AaRegistrationBatch.batch_name == "2025-2026学年第二学期在校生学期注册",
        AaRegistrationBatch.is_deleted.is_(False),
    )).one_or_none()
    spring_regs = 0 if batch is None else int(db.scalar(select(func.count()).select_from(AaRegistration).where(
        AaRegistration.tenant_id == tenant_id,
        AaRegistration.batch_id == int(batch.id),
        AaRegistration.status == "REGISTERED",
        AaRegistration.is_deleted.is_(False),
    )) or 0)
    published_schedule = int(db.scalar(select(func.count()).select_from(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == tenant_id,
        AaScheduleBatch.term_id == int(term.id),
        AaScheduleBatch.status == "PUBLISHED",
        AaScheduleBatch.is_deleted.is_(False),
    )) or 0)
    grade_rows = int(db.scalar(select(func.count()).select_from(AcademicGrade).where(
        AcademicGrade.tenant_id == tenant_id,
        AcademicGrade.term == HISTORICAL_TERM_CODE,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )) or 0)
    snapshots = int(db.scalar(select(func.count()).select_from(AaEffectiveGradePolicySnapshot).where(
        AaEffectiveGradePolicySnapshot.tenant_id == tenant_id,
        AaEffectiveGradePolicySnapshot.source_biz_type == "SANDBOX_ARCHIVE_BACKFILL",
        AaEffectiveGradePolicySnapshot.is_deleted.is_(False),
    )) or 0)

    previous_tenant = get_tenant()
    try:
        set_tenant({"tenantId": str(tenant_id), "tenantCode": "sandbox-school"})
        debt = policy_snapshot_debt(db, term=HISTORICAL_TERM_CODE)
    finally:
        set_tenant(previous_tenant)

    report = {
        "programBindings": bindings,
        "springRegistrations": spring_regs,
        "publishedHistoricalSchedules": published_schedule,
        "historicalGrades": grade_rows,
        "historicalGradePolicySnapshots": snapshots,
        "gradePolicyDebt": debt,
    }
    expected = {
        "programBindings": EXPECTED_PROGRAM_BINDINGS,
        "springRegistrations": EXPECTED_SPRING_REGISTRATIONS,
        "publishedHistoricalSchedules": 1,
        "historicalGrades": EXPECTED_HISTORICAL_GRADE_ROWS,
        "historicalGradePolicySnapshots": EXPECTED_HISTORICAL_GRADE_ROWS,
    }
    mismatch = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if mismatch or not debt.get("ready"):
        raise RuntimeError(f"历史教务归档前置事实验收失败 mismatch={mismatch} gradeDebt={debt}")
    report["passed"] = True
    return report
