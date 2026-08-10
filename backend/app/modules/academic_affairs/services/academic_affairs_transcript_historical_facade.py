"""Stage C2 historical transcript identity facade.

``StudentProfile`` is current projection only.  A transcript row that says it belongs to
a historical term must never inherit today's college/major/class after a transfer.
This facade leaves the existing grade calculation, object-scope guard and API shape in
place, but adds a deterministic academic-identity snapshot for every term using
``StudentAcademicFact(as_of=AaTerm.start_date)``.

Cumulative transcript headers deliberately do *not* pick a current academic identity.
The caller receives an explicit policy marker and per-term identities instead.  Missing
term metadata or a missing fact is returned as UNKNOWN; there is no current-profile
fallback that could silently rewrite history.
"""
from __future__ import annotations

from app.services.db_service import _tid

from . import academic_affairs_grade_service as grade_service

# Import after object-scope guards have installed so the wrapped function preserves all
# existing permission/data-scope checks.
_original_transcript = grade_service.transcript


def _parse_term_code(term_code: str | None):
    text = str(term_code or "").strip()
    if not text or "-" not in text:
        return None
    year_code, term_no = text.rsplit("-", 1)
    try:
        parsed_no = int(term_no)
    except (TypeError, ValueError):
        return None
    if not year_code or parsed_no <= 0:
        return None
    return year_code, parsed_no


def resolve_term_academic_identity(db, student_id: int, term_code: str | None) -> dict:
    """Resolve a historical academic identity without ever falling back to current Profile."""
    from app.models import AaTerm
    from .academic_affairs_student_fact_service import resolve_student_academic_fact

    parsed = _parse_term_code(term_code)
    if not parsed:
        return {
            "status": "UNKNOWN",
            "reason": "TERM_CODE_INVALID",
            "termCode": str(term_code or ""),
            "asOf": None,
        }
    year_code, term_no = parsed
    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == _tid(),
        AaTerm.year_code == year_code,
        AaTerm.term_no == term_no,
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return {
            "status": "UNKNOWN",
            "reason": "TERM_NOT_FOUND",
            "termCode": str(term_code or ""),
            "asOf": None,
        }
    if not term.start_date:
        return {
            "status": "UNKNOWN",
            "reason": "TERM_START_DATE_MISSING",
            "termCode": str(term_code or ""),
            "termId": str(term.id),
            "asOf": None,
        }

    fact = resolve_student_academic_fact(
        db,
        int(student_id),
        as_of=term.start_date,
        required=False,
    )
    if fact is None:
        return {
            "status": "UNKNOWN",
            "reason": "ACADEMIC_FACT_MISSING",
            "termCode": str(term_code or ""),
            "termId": str(term.id),
            "asOf": term.start_date.isoformat(),
        }
    return {
        "status": "RESOLVED",
        "reason": None,
        "termCode": str(term_code or ""),
        "termId": str(term.id),
        "asOf": term.start_date.isoformat(),
        "academicFactId": str(fact.id),
        "academicFactVersion": int(fact.version_no),
        "studentStatus": fact.student_status,
        "collegeId": str(fact.college_id) if fact.college_id is not None else None,
        "majorId": str(fact.major_id) if fact.major_id is not None else None,
        "classId": str(fact.class_id) if fact.class_id is not None else None,
        "grade": fact.grade,
    }


def attach_historical_identities(db, student_id: int, payload: dict) -> dict:
    """Return a copy of transcript payload with per-term immutable identity provenance."""
    result = dict(payload or {})
    items = [dict(item) for item in (result.get("items") or [])]
    by_term: dict[str, dict] = {}
    for item in items:
        term_code = str(item.get("term") or "")
        if term_code not in by_term:
            by_term[term_code] = resolve_term_academic_identity(db, student_id, term_code)
        item["academicIdentity"] = by_term[term_code]
    result["items"] = items
    result["termIdentities"] = by_term
    result["historicalIdentityComplete"] = all(
        identity.get("status") == "RESOLVED" for identity in by_term.values()
    ) if by_term else True
    result["identityPolicy"] = "TERM_START_ACADEMIC_FACT_V1"
    result["cumulativeHeaderIdentity"] = None
    result["cumulativeHeaderIdentityPolicy"] = "NO_IMPLICIT_CURRENT_PROFILE"
    return result


def transcript(student_id, user) -> dict:
    payload = _original_transcript(student_id, user)
    with grade_service._core.session() as db:
        return attach_historical_identities(db, int(student_id), payload)


def install() -> None:
    grade_service.transcript = transcript
