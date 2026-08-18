"""Read-only DB preview bridge for ordinary Program workbook imports.

This local INT owner connects the six-sheet workbook adapter to the frozen Program
preflight pipeline without activating shared File Exchange dispatch.  It performs
only tenant-bounded SELECTs: no row locks, no flush/commit, no domain mutation and
no FileObject/ImportJob lifecycle work.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping

from sqlalchemy import and_, or_, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from .academic_affairs_school_setup_import_contract import PROGRAM_GROUP_BINDING
from .academic_affairs_school_setup_program_binding_policy import (
    PHASE_BINDING,
    PHASE_DEFINITION,
)
from .academic_affairs_school_setup_program_import_preflight import (
    program_import_source_preflight,
)
from .academic_affairs_school_setup_program_preflight_pipeline import (
    run_program_import_preflight,
)
from .academic_affairs_school_setup_program_preview_adapter import (
    program_preflight_to_file_exchange_preview,
)
from .academic_affairs_school_setup_program_snapshot_request_plan import (
    binding_scope_key,
)
from .academic_affairs_school_setup_program_workbook_adapter import (
    parse_and_normalize_program_workbook,
)

_COURSE_KEY_RE = re.compile(r"^(.+)@v([1-9][0-9]*)$", re.IGNORECASE)


def _phase(value: object) -> str:
    resolved = str(value or "").strip().upper()
    if resolved not in {PHASE_DEFINITION, PHASE_BINDING}:
        raise ValueError("phase must be DEFINITION or BINDING")
    return resolved


def _allowed_major_ids(db, security) -> set[int] | None:
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
                Major.college_id.in_(sorted(int(value) for value in security.college_ids)),
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
                SchoolClass.id.in_(sorted(int(value) for value in security.class_ids)),
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
        ).order_by(Major.id)
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
    from app.models import SchoolClass

    wanted = sorted({int(value) for value in ids})
    if not wanted:
        return []
    rows = db.scalars(
        select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(wanted),
            SchoolClass.is_deleted.is_(False),
        ).order_by(SchoolClass.id)
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
        ).order_by(AaCourse.course_code, AaCourse.version, AaCourse.id)
    ).all()
    result = []
    for row in rows:
        pair = (str(row.course_code or "").strip().upper(), int(row.version or 0))
        if pair not in wanted:
            continue
        result.append({
            "courseId": int(row.id),
            "courseCode": pair[0],
            "version": pair[1],
            "courseName": str(row.course_name or "").strip(),
            "credit": row.credit,
            "status": str(row.status or "").strip().upper(),
        })
    return result


def _program_snapshots(db, series_keys: Iterable[object]) -> list[dict]:
    from app.models import AaProgram

    wanted = sorted({
        str(value or "").strip().upper()
        for value in series_keys
        if str(value or "").strip()
    })
    if not wanted:
        return []
    rows = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == _tid(),
            AaProgram.series_key.in_(wanted),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.series_key, AaProgram.version, AaProgram.id)
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
            "既有培养方案学分结构数据损坏，拒绝预览复用",
            details={"programId": str(program.id)},
            http_status=409,
        ) from exc
    structure = parsed.get("creditStructure") if isinstance(parsed, dict) else None
    if not isinstance(structure, list):
        raise AppException(
            "DATA_CONFLICT",
            "既有培养方案学分结构数据损坏，拒绝预览复用",
            details={"programId": str(program.id)},
            http_status=409,
        )
    result = []
    for item in structure:
        if not isinstance(item, dict):
            raise AppException(
                "DATA_CONFLICT",
                "既有培养方案学分结构数据损坏，拒绝预览复用",
                details={"programId": str(program.id)},
                http_status=409,
            )
        result.append({
            "programId": str(program.id),
            "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {
                "module": str(item.get("module") or "").strip(),
                "creditTarget": item.get("creditTarget"),
            },
        })
    return result


def _definition_rows(db, program_ids: Iterable[object]) -> list[dict]:
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
    programs = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == _tid(),
            AaProgram.id.in_(wanted),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.id)
    ).all()
    found = {int(row.id) for row in programs}
    course_rows = db.execute(
        select(AaProgramCourse, AaCourse).join(
            AaCourse,
            (AaCourse.id == AaProgramCourse.course_id)
            & (AaCourse.tenant_id == AaProgramCourse.tenant_id)
            & (AaCourse.is_deleted.is_(False)),
        ).where(
            AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.program_id.in_(wanted),
            AaProgramCourse.is_deleted.is_(False),
        ).order_by(AaProgramCourse.program_id, AaProgramCourse.id)
    ).all()
    practices = db.scalars(
        select(AaProgramPracticeSegment).where(
            AaProgramPracticeSegment.tenant_id == _tid(),
            AaProgramPracticeSegment.program_id.in_(wanted),
            AaProgramPracticeSegment.is_deleted.is_(False),
            AaProgramPracticeSegment.status == "ACTIVE",
        ).order_by(
            AaProgramPracticeSegment.program_id,
            AaProgramPracticeSegment.sort_order,
            AaProgramPracticeSegment.id,
        )
    ).all()
    graduations = db.scalars(
        select(AaProgramGraduationRequirement).where(
            AaProgramGraduationRequirement.tenant_id == _tid(),
            AaProgramGraduationRequirement.program_id.in_(wanted),
            AaProgramGraduationRequirement.is_deleted.is_(False),
            AaProgramGraduationRequirement.status == "ACTIVE",
        ).order_by(
            AaProgramGraduationRequirement.program_id,
            AaProgramGraduationRequirement.sort_order,
            AaProgramGraduationRequirement.id,
        )
    ).all()

    result: list[dict] = []
    for program in programs:
        result.extend(_credit_requirement_rows(program))
    for relation, course in course_rows:
        if int(relation.program_id) not in found:
            continue
        result.append({
            "programId": str(relation.program_id),
            "logicalGroup": "COURSE",
            "payload": {
                "courseKey": f"{str(course.course_code or '').strip().upper()}@v{int(course.version or 0)}",
                "module": str(relation.module or "").strip(),
                "formationMode": str(relation.formation_mode or "").strip().upper(),
                "openTermNo": int(relation.open_term_no or 0),
                "creditSnapshot": relation.credit_snapshot,
            },
        })
    for row in practices:
        result.append({
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
        })
    for row in graduations:
        result.append({
            "programId": str(row.program_id),
            "logicalGroup": "GRADUATION",
            "payload": {
                "category": str(row.category or "").strip().upper(),
                "content": row.content,
                "sortOrder": int(row.sort_order or 0),
            },
        })
    return result


def _program_status_by_id(db, program_ids: Iterable[object]) -> dict[str, str]:
    from app.models import AaProgram

    wanted = sorted({int(value) for value in program_ids if str(value or "").strip()})
    if not wanted:
        return {}
    rows = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == _tid(),
            AaProgram.id.in_(wanted),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.id)
    ).all()
    return {str(row.id): str(row.status or "").strip().upper() for row in rows}


def _binding_scope_specs(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    specs: dict[str, dict] = {}
    for raw in rows:
        if str(raw.get("logicalGroup") or "").strip().upper() != PROGRAM_GROUP_BINDING:
            continue
        payload = dict(raw.get("payload") or {})
        scope_key = binding_scope_key(payload)
        specs.setdefault(scope_key, {
            "majorId": int(payload.get("majorId") or 0),
            "gradeYear": str(payload.get("gradeYear") or "").strip(),
            "classId": (
                int(payload.get("classId"))
                if payload.get("classId") not in (None, "", 0, "0")
                else None
            ),
        })
    return specs


def _active_binding_snapshots(
    db,
    *,
    specs: Mapping[str, Mapping[str, object]],
    requested_scope_keys: Iterable[object],
) -> list[dict]:
    from app.models import AaProgramBinding

    requested = tuple(sorted({
        str(value or "").strip()
        for value in requested_scope_keys
        if str(value or "").strip()
    }))
    if not requested:
        return []
    unknown = [scope for scope in requested if scope not in specs]
    if unknown:
        raise RuntimeError(f"PROGRAM_BINDING_SCOPE_SPEC_MISSING:{','.join(unknown)}")
    clauses = []
    for scope in requested:
        spec = specs[scope]
        class_id = spec.get("classId")
        class_clause = (
            AaProgramBinding.class_id.is_(None)
            if class_id is None
            else AaProgramBinding.class_id == int(class_id)
        )
        clauses.append(and_(
            AaProgramBinding.major_id == int(spec["majorId"]),
            AaProgramBinding.grade_year == str(spec["gradeYear"]),
            class_clause,
        ))
    rows = db.scalars(
        select(AaProgramBinding).where(
            AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.is_deleted.is_(False),
            AaProgramBinding.status == "ACTIVE",
            or_(*clauses),
        ).order_by(
            AaProgramBinding.major_id,
            AaProgramBinding.grade_year,
            AaProgramBinding.class_id,
            AaProgramBinding.id,
        )
    ).all()
    result = []
    for row in rows:
        scope_key = (
            f"MAJOR:{int(row.major_id)}:GRADE:{str(row.grade_year)}:MAJOR_GRADE"
            if row.class_id is None
            else f"MAJOR:{int(row.major_id)}:GRADE:{str(row.grade_year)}:CLASS:{int(row.class_id)}"
        )
        if scope_key not in requested:
            raise RuntimeError(
                f"PROGRAM_BINDING_SCOPE_OVERFETCH:{scope_key}:requested={list(requested)}"
            )
        result.append({
            "scopeKey": scope_key,
            "programId": str(row.program_id),
            "majorId": int(row.major_id) if row.major_id is not None else None,
            "gradeYear": str(row.grade_year or ""),
            "classId": int(row.class_id) if row.class_id is not None else None,
            "status": "ACTIVE",
        })
    return result


def _early_preview_if_no_db_needed(rows: list[dict], *, phase: str) -> dict | None:
    source = program_import_source_preflight(rows)
    binding_rows = [
        row for row in rows
        if str(row.get("logicalGroup") or "").strip().upper() == PROGRAM_GROUP_BINDING
    ]
    if bool(source.get("sourcePreflightSafe")) and not (
        phase == PHASE_BINDING and not binding_rows
    ):
        return None

    def no_db_loader(*_args, **_kwargs):
        raise RuntimeError("PROGRAM_PREVIEW_EARLY_GATE_OPENED_DB")

    preflight = run_program_import_preflight(
        rows,
        phase=phase,
        load_allowed_major_ids=no_db_loader,
        load_major_snapshots=no_db_loader,
        load_class_snapshots=no_db_loader,
        load_course_snapshots=no_db_loader,
        load_program_snapshots=no_db_loader,
        load_existing_definition_rows=no_db_loader,
        load_program_status_by_id=no_db_loader,
        load_active_binding_snapshots=no_db_loader,
    )
    return program_preflight_to_file_exchange_preview(rows, preflight)


def preview_program_normalized_rows(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    phase: object,
    user: dict,
) -> dict:
    """Run Program preview with zero mutations and no row locks."""
    resolved_phase = _phase(phase)
    rows = [dict(row) for row in normalized_rows]
    early = _early_preview_if_no_db_needed(rows, phase=resolved_phase)
    if early is not None:
        return early

    with session() as db:
        security = build_affairs_context(user, db)
        allowed_major_ids = _allowed_major_ids(db, security)
        scope_specs = _binding_scope_specs(rows)
        preflight = run_program_import_preflight(
            rows,
            phase=resolved_phase,
            load_allowed_major_ids=(
                lambda: None if allowed_major_ids is None else set(allowed_major_ids)
            ),
            load_major_snapshots=lambda keys: _major_snapshots(db, keys),
            load_class_snapshots=lambda keys: _class_snapshots(db, keys),
            load_course_snapshots=lambda keys: _course_snapshots(db, keys),
            load_program_snapshots=lambda keys: _program_snapshots(db, keys),
            load_existing_definition_rows=lambda keys: _definition_rows(db, keys),
            load_program_status_by_id=lambda keys: _program_status_by_id(db, keys),
            load_active_binding_snapshots=lambda keys: _active_binding_snapshots(
                db,
                specs=scope_specs,
                requested_scope_keys=keys,
            ),
        )
        return program_preflight_to_file_exchange_preview(rows, preflight)


def preview_program_workbook(
    file_bytes: bytes,
    *,
    phase: object,
    user: dict,
) -> dict:
    """Parse six-sheet XLSX bytes and return only the safe preview envelope."""
    grouped, normalized = parse_and_normalize_program_workbook(file_bytes)
    preview = preview_program_normalized_rows(normalized, phase=phase, user=user)
    return {
        **preview,
        "sheetRowCounts": {group: len(rows) for group, rows in grouped.items()},
        "normalizedRowCount": len(normalized),
    }
