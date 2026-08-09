"""Stage C1 deterministic program-binding assessment for major transitions."""
from __future__ import annotations

import json
from datetime import datetime

from app.core.exceptions import AppException
from app.services.db_service import _tid

_PROGRAM_USABLE = {"PUBLISHED", "ENABLED", "FROZEN"}


def _candidate_bindings(db, *, major_id: int | None, grade: str | None, class_id: int | None) -> list[dict]:
    from app.models import AaProgram, AaProgramBinding

    if not major_id:
        return []
    rows = db.query(AaProgramBinding).filter(
        AaProgramBinding.tenant_id == _tid(),
        AaProgramBinding.major_id == int(major_id),
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    ).all()
    candidates: list[dict] = []
    for row in rows:
        if row.grade_year not in (None, "", grade):
            continue
        if row.class_id is not None and (class_id is None or int(row.class_id) != int(class_id)):
            continue
        program = db.query(AaProgram).filter(
            AaProgram.id == int(row.program_id),
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).first()
        if not program or str(program.status or "").upper() not in _PROGRAM_USABLE:
            continue
        score = 0
        if row.grade_year and grade and row.grade_year == grade:
            score += 2
        if row.class_id is not None and class_id is not None and int(row.class_id) == int(class_id):
            score += 4
        candidates.append({
            "bindingId": int(row.id),
            "programId": int(row.program_id),
            "score": score,
            "gradeYear": row.grade_year,
            "classId": int(row.class_id) if row.class_id is not None else None,
        })
    candidates.sort(key=lambda item: (-int(item["score"]), int(item["programId"]), int(item["bindingId"])))
    return candidates


def _resolve_program(candidates: list[dict]) -> tuple[int | None, str, list[int]]:
    if not candidates:
        return None, "NONE", []
    best_score = int(candidates[0]["score"])
    best_programs = sorted({int(item["programId"]) for item in candidates if int(item["score"]) == best_score})
    if len(best_programs) == 1:
        return best_programs[0], "UNIQUE", best_programs
    return None, "AMBIGUOUS", best_programs


def assess_program_transition_in_session(
    db,
    *,
    student,
    source_fact,
    to_major_id: int,
    target_class_id: int | None,
    source_type: str,
    source_ref_id: int | None,
):
    """Create one deterministic assessment before a canonical major transition.

    Missing/ambiguous target bindings are recorded as MANUAL_REVIEW rather than guessed.
    The academic identity transition may still proceed: this table is the explicit debt
    and evidence trail consumed by later program-binding remediation, not a hidden fallback.
    """
    from app.models.academic_affairs_program_transition import ProgramTransitionAssessment

    if int(source_fact.major_id or 0) == int(to_major_id or 0):
        return None

    existing_q = db.query(ProgramTransitionAssessment).filter(
        ProgramTransitionAssessment.tenant_id == _tid(),
        ProgramTransitionAssessment.student_id == int(student.id),
        ProgramTransitionAssessment.source_type == str(source_type or "").upper(),
        ProgramTransitionAssessment.source_fact_version == int(source_fact.version_no),
    )
    if source_ref_id is None:
        existing_q = existing_q.filter(ProgramTransitionAssessment.source_ref_id.is_(None))
    else:
        existing_q = existing_q.filter(ProgramTransitionAssessment.source_ref_id == int(source_ref_id))
    existing = existing_q.with_for_update().first()
    if existing:
        if int(existing.to_major_id) != int(to_major_id):
            raise AppException(
                "PROGRAM_TRANSITION_SOURCE_CONFLICT",
                "同一学籍事实来源已存在不同目标专业的培养方案迁移评估",
                http_status=409,
            )
        return existing

    source_candidates = _candidate_bindings(
        db,
        major_id=source_fact.major_id,
        grade=source_fact.grade,
        class_id=source_fact.class_id,
    )
    target_candidates = _candidate_bindings(
        db,
        major_id=int(to_major_id),
        grade=student.grade,
        class_id=target_class_id,
    )
    from_program_id, source_resolution, source_programs = _resolve_program(source_candidates)
    target_program_id, target_resolution, target_programs = _resolve_program(target_candidates)

    if target_resolution == "UNIQUE":
        decision = "SWITCH_TARGET"
        status = "READY"
    elif target_resolution == "AMBIGUOUS":
        decision = "MANUAL_REVIEW"
        status = "AMBIGUOUS_TARGET"
    else:
        decision = "MANUAL_REVIEW"
        status = "NO_TARGET_BINDING"

    evidence = {
        "source": {
            "resolution": source_resolution,
            "programIds": source_programs,
            "candidates": source_candidates,
        },
        "target": {
            "resolution": target_resolution,
            "programIds": target_programs,
            "candidates": target_candidates,
        },
        "rule": "class-specific > grade-specific > major-generic; same-score multi-program => manual review",
    }
    row = ProgramTransitionAssessment(
        tenant_id=_tid(),
        student_id=int(student.id),
        source_fact_id=int(source_fact.id),
        source_fact_version=int(source_fact.version_no),
        applied_fact_id=None,
        source_type=str(source_type or "").upper(),
        source_ref_id=int(source_ref_id) if source_ref_id is not None else None,
        from_major_id=int(source_fact.major_id) if source_fact.major_id is not None else None,
        to_major_id=int(to_major_id),
        target_class_id=int(target_class_id) if target_class_id is not None else None,
        grade=student.grade,
        from_program_id=from_program_id,
        target_program_id=target_program_id,
        decision=decision,
        assessment_status=status,
        evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        assessed_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def mark_program_transition_applied_in_session(db, assessment, applied_fact) -> None:
    if assessment is None:
        return
    assessment.applied_fact_id = int(applied_fact.id)
    assessment.assessment_status = (
        "APPLIED" if assessment.decision == "SWITCH_TARGET" else "APPLIED_REVIEW_REQUIRED"
    )
    db.flush()
