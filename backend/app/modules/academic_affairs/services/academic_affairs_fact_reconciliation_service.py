"""Stage C1 current StudentProfile ↔ StudentAcademicFact reconciliation."""
from __future__ import annotations

from collections import defaultdict

from app.services.db_service import _tid


def scan_current_projection(db, detail_limit: int = 100) -> dict:
    from app.models import StudentProfile
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    tid = _tid()
    profiles = db.query(
        StudentProfile.id, StudentProfile.student_status, StudentProfile.college_id,
        StudentProfile.major_id, StudentProfile.class_id, StudentProfile.grade,
    ).filter(StudentProfile.tenant_id == tid, StudentProfile.is_deleted.is_(False)).all()
    facts = db.query(
        StudentAcademicFact.student_id, StudentAcademicFact.version_no,
        StudentAcademicFact.student_status, StudentAcademicFact.college_id,
        StudentAcademicFact.major_id, StudentAcademicFact.class_id, StudentAcademicFact.grade,
    ).filter(
        StudentAcademicFact.tenant_id == tid,
        StudentAcademicFact.valid_to.is_(None),
    ).all()

    grouped = defaultdict(list)
    for fact in facts:
        grouped[int(fact.student_id)].append(fact)

    missing = []
    overlap = []
    drifts = []
    missing_count = overlap_count = drift_count = 0
    for profile in profiles:
        sid = int(profile.id)
        current = grouped.get(sid, [])
        if not current:
            missing_count += 1
            if len(missing) < detail_limit:
                missing.append(str(sid))
            continue
        if len(current) != 1:
            overlap_count += 1
            if len(overlap) < detail_limit:
                overlap.append(str(sid))
            continue
        fact = current[0]
        p = (profile.student_status or "NORMAL", profile.college_id, profile.major_id,
             profile.class_id, profile.grade)
        f = (fact.student_status or "NORMAL", fact.college_id, fact.major_id,
             fact.class_id, fact.grade)
        if p != f:
            drift_count += 1
            if len(drifts) < detail_limit:
                drifts.append({"studentId": str(sid), "factVersion": int(fact.version_no),
                               "profile": p, "fact": f})

    unresolved = missing_count + overlap_count + drift_count
    return {
        "tenantId": str(tid), "activeProfiles": len(profiles),
        "missingCurrentFact": missing_count,
        "overlappingCurrentFact": overlap_count,
        "projectionDrift": drift_count,
        "unresolved": unresolved,
        "details": {"missingStudentIds": missing, "overlapStudentIds": overlap, "drifts": drifts},
    }
