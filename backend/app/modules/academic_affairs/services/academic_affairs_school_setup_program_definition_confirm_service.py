"""INT transactional DEFINITION writer for school-setup Program imports.

This module owns only the Program domain transaction. Shared FileObject/ImportJob
lease state and public dispatch remain disabled until INT wires them separately.

Confirmation always re-runs the frozen Program preflight inside the caller-owned
transaction with deterministic locks, applies the pure write plan, re-reads the
authoritative Program/definition rows, and delegates semantic verification to the
frozen post-confirm pipeline before commit.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_program_core_service as _program_core
from .academic_affairs_school_setup_program_definition_execution_gate import (
    assert_program_definition_execution_ready,
)
from .academic_affairs_school_setup_program_definition_write_plan import (
    build_program_definition_write_plan,
)
from .academic_affairs_school_setup_program_post_confirm_pipeline import (
    reconcile_program_confirm_reread,
)
from .academic_affairs_school_setup_program_preflight_pipeline import (
    run_program_import_preflight,
)

_COURSE_KEY_RE = re.compile(r"^(.+)@v([1-9][0-9]*)$", re.IGNORECASE)


def _db_error_code(exc: Exception) -> int | None:
    args = getattr(getattr(exc, "orig", None), "args", ()) or ()
    if not args:
        return None
    try:
        return int(args[0])
    except (TypeError, ValueError):
        return None


def _is_mysql_lock_conflict(exc: OperationalError) -> bool:
    return _db_error_code(exc) in {1205, 1213}


def _decimal_json(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _source_series_keys(rows: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    keys = set()
    for raw in rows:
        if str(raw.get("logicalGroup") or "").strip().upper() != "MAIN":
            continue
        payload = raw.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue
        key = str(payload.get("programSeriesKey") or "").strip().upper()
        if key:
            keys.add(key)
    return tuple(sorted(keys))


def _prelock_existing_program_series(db, rows: Iterable[Mapping[str, object]]) -> list[dict]:
    """Take Program-series locks before Major/Course locks for deadlock-safe vN confirm.

    Interactive binding and the frozen BINDING mutation plan both lock Program
    before Major/Class.  DEFINITION confirmation must share that prefix.  v1 has
    no existing Program row, so the activation authority's Tenant lock remains
    its absent-series anchor; v2+ locks the proven series rows here and later
    pipeline Program reads are same-transaction re-entrant locks.
    """
    keys = _source_series_keys(rows)
    if not keys:
        return []
    return _program_snapshots(db, keys)


def _allowed_major_ids(db, security) -> set[int] | None:
    """Return None for tenant-all, exact major ids for bounded scopes, empty on unsupported scopes."""
    from app.models import Major, SchoolClass

    scope = str(security.scope_type or "").strip().upper()
    if scope == "TENANT_ALL":
        return None
    if scope == "COLLEGE":
        if not security.college_ids:
            return set()
        rows = db.scalars(
            select(Major.id).where(
                Major.tenant_id == _tid(),
                Major.college_id.in_(sorted(int(v) for v in security.college_ids)),
                Major.is_deleted.is_(False),
            ).order_by(Major.id)
        ).all()
        return {int(value) for value in rows}
    if scope == "CLASS":
        if not security.class_ids:
            return set()
        rows = db.scalars(
            select(SchoolClass.major_id).where(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(sorted(int(v) for v in security.class_ids)),
                SchoolClass.is_deleted.is_(False),
            ).order_by(SchoolClass.id)
        ).all()
        return {int(value) for value in rows if value is not None}
    return set()


def _major_snapshots(db, ids: Iterable[object]) -> list[dict]:
    from app.models import Major

    wanted = sorted({int(value) for value in ids})
    if not wanted:
        return []
    rows = db.scalars(
        select(Major).where(
            Major.tenant_id == _tid(),
            Major.id.in_(wanted),
            Major.is_deleted.is_(False),
        ).order_by(Major.id).with_for_update()
    ).all()
    return [
        {
            "majorId": int(row.id),
            "educationYears": int(row.education_years),
            "status": str(row.status or "").strip().upper(),
        }
        for row in rows
    ]


def _class_snapshots(db, ids: Iterable[object]) -> list[dict]:
    """Generic bounded loader retained for pipeline contract; DEFINITION normally requests none."""
    from app.models import SchoolClass

    wanted = sorted({int(value) for value in ids})
    if not wanted:
        return []
    rows = db.scalars(
        select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(wanted),
            SchoolClass.is_deleted.is_(False),
        ).order_by(SchoolClass.id).with_for_update()
    ).all()
    return [
        {
            "classId": int(row.id),
            "majorId": int(row.major_id),
            "gradeYear": str(row.grade or ""),
            "classStatus": str(row.class_status or "").strip().upper(),
        }
        for row in rows
    ]


def _parse_course_keys(keys: Iterable[object]) -> set[tuple[str, int]]:
    result: set[tuple[str, int]] = set()
    for raw in keys:
        text = str(raw or "").strip()
        match = _COURSE_KEY_RE.fullmatch(text)
        if not match:
            raise ValueError(f"invalid Course stable key: {text}")
        result.add((match.group(1).strip().upper(), int(match.group(2))))
    return result


def _course_snapshots(db, keys: Iterable[object]) -> list[dict]:
    from app.models import AaCourse

    wanted = _parse_course_keys(keys)
    if not wanted:
        return []
    codes = sorted({code for code, _version in wanted})
    versions = sorted({version for _code, version in wanted})
    rows = db.scalars(
        select(AaCourse).where(
            AaCourse.tenant_id == _tid(),
            AaCourse.course_code.in_(codes),
            AaCourse.version.in_(versions),
            AaCourse.is_deleted.is_(False),
        ).order_by(AaCourse.course_code, AaCourse.version, AaCourse.id).with_for_update()
    ).all()
    result = []
    for row in rows:
        pair = (str(row.course_code or "").strip().upper(), int(row.version or 0))
        if pair not in wanted:
            continue
        result.append(
            {
                "courseId": int(row.id),
                "courseCode": pair[0],
                "version": pair[1],
                "courseName": str(row.course_name or "").strip(),
                "credit": row.credit,
                "status": str(row.status or "").strip().upper(),
            }
        )
    return result


def _program_snapshots(db, series_keys: Iterable[object]) -> list[dict]:
    from app.models import AaProgram

    wanted = sorted({str(value or "").strip().upper() for value in series_keys if str(value or "").strip()})
    if not wanted:
        return []
    rows = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == _tid(),
            AaProgram.series_key.in_(wanted),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.series_key, AaProgram.version, AaProgram.id).with_for_update()
    ).all()
    return [
        {
            "seriesKey": str(row.series_key or "").strip().upper(),
            "version": int(row.version or 0),
            "programId": str(row.id),
            "programName": str(row.program_name or "").strip(),
            "majorId": int(row.major_id) if row.major_id is not None else None,
            "gradeYear": str(row.grade_year or ""),
            "totalCredits": row.total_credits,
            "prevVersionId": str(row.prev_version_id) if row.prev_version_id else "",
            "status": str(row.status or "").strip().upper(),
        }
        for row in rows
    ]


def _credit_requirement_rows(program) -> list[dict]:
    raw = program.requirement_json
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppException(
            "DATA_CONFLICT",
            "既有培养方案学分结构数据损坏，拒绝复用",
            details={"programId": str(program.id)},
            http_status=409,
        ) from exc
    structure = parsed.get("creditStructure") if isinstance(parsed, dict) else None
    if not isinstance(structure, list):
        raise AppException(
            "DATA_CONFLICT",
            "既有培养方案学分结构数据损坏，拒绝复用",
            details={"programId": str(program.id)},
            http_status=409,
        )
    result = []
    for item in structure:
        if not isinstance(item, dict):
            raise AppException(
                "DATA_CONFLICT",
                "既有培养方案学分结构数据损坏，拒绝复用",
                details={"programId": str(program.id)},
                http_status=409,
            )
        result.append(
            {
                "programId": str(program.id),
                "logicalGroup": "CREDIT_REQUIREMENT",
                "payload": {
                    "module": str(item.get("module") or "").strip(),
                    "creditTarget": item.get("creditTarget"),
                },
            }
        )
    return result


def _definition_rows(db, program_ids: Iterable[object], *, lock_rows: bool) -> list[dict]:
    from app.models import (
        AaCourse,
        AaProgram,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
    )

    wanted = sorted({int(value) for value in program_ids})
    if not wanted:
        return []

    program_stmt = select(AaProgram).where(
        AaProgram.tenant_id == _tid(),
        AaProgram.id.in_(wanted),
        AaProgram.is_deleted.is_(False),
    ).order_by(AaProgram.id)
    if lock_rows:
        program_stmt = program_stmt.with_for_update()
    programs = db.scalars(program_stmt).all()
    found = {int(row.id) for row in programs}

    course_stmt = select(AaProgramCourse, AaCourse).join(
        AaCourse,
        (AaCourse.id == AaProgramCourse.course_id)
        & (AaCourse.tenant_id == AaProgramCourse.tenant_id)
        & (AaCourse.is_deleted.is_(False)),
    ).where(
        AaProgramCourse.tenant_id == _tid(),
        AaProgramCourse.program_id.in_(wanted),
        AaProgramCourse.is_deleted.is_(False),
    ).order_by(AaProgramCourse.program_id, AaProgramCourse.id)
    if lock_rows:
        course_stmt = course_stmt.with_for_update()
    course_rows = db.execute(course_stmt).all()

    practice_stmt = select(AaProgramPracticeSegment).where(
        AaProgramPracticeSegment.tenant_id == _tid(),
        AaProgramPracticeSegment.program_id.in_(wanted),
        AaProgramPracticeSegment.is_deleted.is_(False),
        AaProgramPracticeSegment.status == "ACTIVE",
    ).order_by(AaProgramPracticeSegment.program_id, AaProgramPracticeSegment.sort_order, AaProgramPracticeSegment.id)
    if lock_rows:
        practice_stmt = practice_stmt.with_for_update()
    practices = db.scalars(practice_stmt).all()

    graduation_stmt = select(AaProgramGraduationRequirement).where(
        AaProgramGraduationRequirement.tenant_id == _tid(),
        AaProgramGraduationRequirement.program_id.in_(wanted),
        AaProgramGraduationRequirement.is_deleted.is_(False),
        AaProgramGraduationRequirement.status == "ACTIVE",
    ).order_by(AaProgramGraduationRequirement.program_id, AaProgramGraduationRequirement.sort_order, AaProgramGraduationRequirement.id)
    if lock_rows:
        graduation_stmt = graduation_stmt.with_for_update()
    graduations = db.scalars(graduation_stmt).all()

    result: list[dict] = []
    for program in programs:
        result.extend(_credit_requirement_rows(program))
    for relation, course in course_rows:
        if int(relation.program_id) not in found:
            continue
        result.append(
            {
                "programId": str(relation.program_id),
                "logicalGroup": "COURSE",
                "payload": {
                    "courseKey": f"{str(course.course_code or '').strip().upper()}@v{int(course.version or 0)}",
                    "module": str(relation.module or "").strip(),
                    "formationMode": str(relation.formation_mode or "").strip().upper(),
                    "openTermNo": int(relation.open_term_no or 0),
                    "creditSnapshot": relation.credit_snapshot,
                },
            }
        )
    for row in practices:
        result.append(
            {
                "programId": str(row.program_id),
                "logicalGroup": "PRACTICE",
                "payload": {
                    "segmentName": row.segment_name,
                    "segmentType": str(row.segment_type or "").strip().upper(),
                    "openTermNo": int(row.open_term_no or 0),
                    "weeks": row.weeks,
                    "credit": row.credit,
                    "orgMode": str(row.org_mode or "").strip().upper(),
                    "location": row.location,
                    "assessmentMode": str(row.assessment_mode or "").strip().upper(),
                    "sortOrder": int(row.sort_order or 0),
                },
            }
        )
    for row in graduations:
        result.append(
            {
                "programId": str(row.program_id),
                "logicalGroup": "GRADUATION",
                "payload": {
                    "category": str(row.category or "").strip().upper(),
                    "content": row.content,
                    "sortOrder": int(row.sort_order or 0),
                },
            }
        )
    return result


def _exact_program_reread(db, preflight_result: Mapping[str, object]) -> list[dict]:
    from app.models import AaProgram

    wanted: set[tuple[str, int]] = set()
    for action in preflight_result.get("actions") or ():
        key = str(action.get("programKey") or "").strip()
        match = re.fullmatch(r"SERIES:(.+):v([1-9][0-9]*)", key, flags=re.IGNORECASE)
        if not match:
            raise RuntimeError(f"invalid Program action stable key: {key}")
        wanted.add((match.group(1).strip().upper(), int(match.group(2))))
    if not wanted:
        raise RuntimeError("Program confirm produced no target stable keys")

    series_keys = sorted({series for series, _version in wanted})
    versions = sorted({version for _series, version in wanted})
    rows = db.scalars(
        select(AaProgram).execution_options(populate_existing=True).where(
            AaProgram.tenant_id == _tid(),
            AaProgram.series_key.in_(series_keys),
            AaProgram.version.in_(versions),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.series_key, AaProgram.version, AaProgram.id).with_for_update()
    ).all()
    result = []
    for row in rows:
        pair = (str(row.series_key or "").strip().upper(), int(row.version or 0))
        if pair not in wanted:
            continue
        result.append(
            {
                "seriesKey": pair[0],
                "version": pair[1],
                "programId": str(row.id),
                "programName": str(row.program_name or "").strip(),
                "majorId": int(row.major_id) if row.major_id is not None else None,
                "gradeYear": str(row.grade_year or ""),
                "totalCredits": row.total_credits,
                "prevVersionId": str(row.prev_version_id) if row.prev_version_id else "",
                "status": str(row.status or "").strip().upper(),
            }
        )
    return result


def _apply_create_plan(db, plan: Mapping[str, object]) -> tuple[object, int]:
    from app.models import (
        AaProgram,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
    )

    writes = dict(plan.get("writes") or {})
    program_write = dict(writes.get("program") or {})
    predecessor = str(program_write.get("prevProgramId") or "").strip()
    program = AaProgram(
        tenant_id=_tid(),
        series_key=str(program_write.get("seriesKey") or "").strip().upper(),
        program_name=str(program_write.get("programName") or "").strip(),
        major_id=int(program_write["majorId"]),
        grade_year=str(program_write.get("gradeYear") or "").strip(),
        total_credits=program_write.get("totalCredits") or 0,
        requirement_json=json.dumps(
            program_write.get("requirementJson") or {},
            ensure_ascii=False,
            sort_keys=True,
            default=_decimal_json,
        ),
        version=int(program_write.get("version") or 0),
        prev_version_id=int(predecessor) if predecessor else None,
        status="DRAFT",
    )
    db.add(program)
    db.flush()

    write_count = 1
    for payload in writes.get("courses") or ():
        row = dict(payload)
        db.add(
            AaProgramCourse(
                tenant_id=_tid(),
                program_id=program.id,
                course_id=int(row["courseId"]),
                course_name=str(row.get("courseName") or "").strip(),
                open_term_no=int(row.get("openTermNo") or 0),
                module=str(row.get("module") or "").strip(),
                credit_snapshot=row.get("creditSnapshot") or 0,
                formation_mode=str(row.get("formationMode") or "").strip().upper(),
            )
        )
        write_count += 1
    for payload in writes.get("practices") or ():
        row = dict(payload)
        db.add(
            AaProgramPracticeSegment(
                tenant_id=_tid(),
                program_id=program.id,
                segment_name=str(row.get("segmentName") or "").strip(),
                segment_type=str(row.get("segmentType") or "").strip().upper(),
                open_term_no=int(row.get("openTermNo") or 0),
                weeks=row.get("weeks") or 0,
                credit=row.get("credit") or 0,
                org_mode=str(row.get("orgMode") or "").strip().upper(),
                location=str(row.get("location") or "").strip() or None,
                assessment_mode=str(row.get("assessmentMode") or "").strip().upper(),
                sort_order=int(row.get("sortOrder") or 0),
                status="ACTIVE",
            )
        )
        write_count += 1
    for payload in writes.get("graduationRequirements") or ():
        row = dict(payload)
        db.add(
            AaProgramGraduationRequirement(
                tenant_id=_tid(),
                program_id=program.id,
                category=str(row.get("category") or "").strip().upper(),
                content=str(row.get("content") or "").strip(),
                sort_order=int(row.get("sortOrder") or 0),
                status="ACTIVE",
            )
        )
        write_count += 1

    expected = int(plan.get("writeCount") or 0)
    if write_count != expected:
        raise RuntimeError(
            f"Program write-plan count mismatch: expected={expected}, actual={write_count}"
        )
    return program, write_count


def confirm_program_definition_import(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    user: dict,
) -> dict:
    """Atomically confirm one normalized ordinary Program DEFINITION import."""
    rows = [dict(row) for row in normalized_rows]
    if not rows:
        raise AppException("VALIDATION_ERROR", "培养方案导入不能为空")
    assert_program_definition_execution_ready()

    try:
        with session() as db:
            # Global Program mutation order starts with existing Program rows. This
            # matches interactive bind_grade/BINDING and removes the vN
            # Program<->Major lock inversion without changing the frozen pure
            # preflight loader contract.
            _prelock_existing_program_series(db, rows)
            security = build_affairs_context(user, db)
            allowed_major_ids = _allowed_major_ids(db, security)
            course_cache: dict[str, dict] = {}

            def load_allowed_major_ids():
                return None if allowed_major_ids is None else set(allowed_major_ids)

            def load_major_snapshots(keys):
                return _major_snapshots(db, keys)

            def load_class_snapshots(keys):
                return _class_snapshots(db, keys)

            def load_course_snapshots(keys):
                snapshots = _course_snapshots(db, keys)
                for item in snapshots:
                    key = f"{str(item['courseCode']).strip().upper()}@v{int(item['version'])}"
                    course_cache[key] = dict(item)
                return snapshots

            def load_program_snapshots(keys):
                return _program_snapshots(db, keys)

            def load_existing_definition_rows(keys):
                return _definition_rows(db, keys, lock_rows=True)

            def forbidden_binding_loader(_keys):
                raise RuntimeError("DEFINITION confirm must not query BINDING-only snapshots")

            preflight = run_program_import_preflight(
                rows,
                phase="DEFINITION",
                load_allowed_major_ids=load_allowed_major_ids,
                load_major_snapshots=load_major_snapshots,
                load_class_snapshots=load_class_snapshots,
                load_course_snapshots=load_course_snapshots,
                load_program_snapshots=load_program_snapshots,
                load_existing_definition_rows=load_existing_definition_rows,
                load_program_status_by_id=forbidden_binding_loader,
                load_active_binding_snapshots=forbidden_binding_loader,
            )
            if not bool(preflight.get("programPreflightSafe")) or str(preflight.get("stage") or "").upper() != "READY":
                raise AppException(
                    "DATA_CONFLICT",
                    "培养方案确认前的锁内预检未通过",
                    details={
                        "stage": str(preflight.get("stage") or ""),
                        "errors": list(preflight.get("errors") or ()),
                    },
                    http_status=409,
                )

            course_snapshots = [course_cache[key] for key in sorted(course_cache)]
            write_plan = build_program_definition_write_plan(
                rows,
                preflight,
                course_snapshots=course_snapshots,
            )

            created_ids: list[str] = []
            domain_write_count = 0
            for plan in write_plan.get("programPlans") or ():
                action = str(plan.get("action") or "").strip().upper()
                if action == "REUSE":
                    if int(plan.get("writeCount") or 0) != 0 or plan.get("writes"):
                        raise RuntimeError("Program REUSE plan must remain zero-write")
                    continue
                if action != "CREATE":
                    raise RuntimeError(f"unsupported Program write action: {action}")
                program, count = _apply_create_plan(db, plan)
                domain_write_count += count
                created_ids.append(str(program.id))
                _program_core._audit(
                    db,
                    program.id,
                    "IMPORT_CREATE",
                    f"seriesKey={program.series_key};version={program.version};status=DRAFT",
                )

            db.flush()
            authoritative_programs = _exact_program_reread(db, preflight)
            target_program_ids = [str(row["programId"]) for row in authoritative_programs]
            authoritative_definitions = _definition_rows(
                db,
                target_program_ids,
                lock_rows=True,
            )
            reconciliation = reconcile_program_confirm_reread(
                preflight,
                normalized_rows=rows,
                authoritative_program_snapshots=authoritative_programs,
                authoritative_definition_rows=authoritative_definitions,
                course_snapshots=course_snapshots,
            )
            if not bool(reconciliation.get("reconciliationSafe")):
                raise AppException(
                    "DATA_CONFLICT",
                    "培养方案确认后的权威回读对账失败，事务已回滚",
                    details={
                        "errors": list(reconciliation.get("errors") or ()),
                    },
                    http_status=409,
                )

            expected_write_count = sum(
                int(item.get("writeCount") or 0)
                for item in write_plan.get("programPlans") or ()
            )
            if domain_write_count != expected_write_count:
                raise RuntimeError(
                    f"Program domain write count mismatch: expected={expected_write_count}, actual={domain_write_count}"
                )
            db.commit()
            return {
                "phase": "DEFINITION",
                "createdProgramIds": created_ids,
                "domainMutationWriteCount": domain_write_count,
                "preflight": preflight,
                "reconciliation": reconciliation,
            }
    except OperationalError as exc:
        if _is_mysql_lock_conflict(exc):
            raise AppException(
                "DATA_CONFLICT",
                "培养方案确认期间发生并发锁冲突，请重新预检后重试",
                details={"dbErrorCode": _db_error_code(exc)},
                http_status=409,
            ) from exc
        raise
