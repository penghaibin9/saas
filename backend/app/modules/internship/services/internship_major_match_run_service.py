"""Bounded read/preparation path for the major auto-match command.

The canonical mutation semantics remain in internship_match_service._upsert_match. This adapter
bulk-loads students/majors once, indexes eligible positions per major, and caches the ranked
three-position recommendation per preference tuple. The explicit confirmation command remains the
only place that consumes position capacity.
"""
from __future__ import annotations

from sqlalchemy import or_, select

from app.core.exceptions import AppException
from app.models import InternshipIntention, InternshipPosition, InternshipRecord, Major, StudentProfile
from app.services.db_service import _tid, session


def run_major_match(batch_id=None, user=None) -> dict:
    from app.modules.internship.services import internship_match_service as legacy
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_service import assert_admin_tenant

    assert_admin_tenant(user, "专业自动匹配")
    created = 0
    with session() as db:
        batch = resolve_batch(db, batch_id)
        if batch.status != "RUNNING":
            raise AppException("DATA_CONFLICT", "仅进行中的实习批次可执行自动匹配")

        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.position_id.is_(None),
            InternshipRecord.status != "ARCHIVED",
        )).all()
        positions = db.scalars(select(InternshipPosition).where(
            InternshipPosition.tenant_id == _tid(),
            InternshipPosition.is_deleted.is_(False),
            InternshipPosition.status == "PUBLISHED",
            or_(InternshipPosition.batch_id == batch.id, InternshipPosition.batch_id.is_(None)),
        )).all()
        intents = db.scalars(select(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(),
            InternshipIntention.is_deleted.is_(False),
            InternshipIntention.batch_id == batch.id,
            InternshipIntention.status == "SUBMITTED",
        )).all()
        intent_map = {item.record_id: item for item in intents}

        student_ids = {int(record.student_id) for record in records if record.student_id}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id.in_(student_ids or [0]),
            StudentProfile.is_deleted.is_(False),
        )).all()
        student_map = {row.id: row for row in students}
        major_ids = {int(row.major_id) for row in students if row.major_id}
        majors = db.scalars(select(Major).where(
            Major.tenant_id == _tid(),
            Major.id.in_(major_ids or [0]),
            Major.is_deleted.is_(False),
        )).all()
        major_map = {row.id: (row.major_name or "") for row in majors}

        # Candidate eligibility depends only on the student's major and current published/capacity
        # snapshot. Score ordering additionally depends on city/company preference. Split those two
        # dimensions so hundreds/thousands of students do not rescan every position.
        eligible_by_major: dict[str, list[InternshipPosition]] = {}
        ranked_by_preference: dict[tuple[str, str, int | None], list[InternshipPosition]] = {}
        for record in records:
            student = student_map.get(record.student_id)
            major_name = major_map.get(getattr(student, "major_id", None), "")
            intent = intent_map.get(record.id)
            city = str(getattr(intent, "preferred_city", "") or "").strip()
            preferred_company_id = getattr(intent, "preferred_company_id", None)

            eligible = eligible_by_major.get(major_name)
            if eligible is None:
                eligible = [
                    position for position in positions
                    if legacy._major_hit(major_name, position.major_requirement or "")
                    and max(0, (position.headcount or 0) - (position.allocated_count or 0)) > 0
                ]
                eligible_by_major[major_name] = eligible

            key = (major_name, city, int(preferred_company_id) if preferred_company_id else None)
            ranked = ranked_by_preference.get(key)
            if ranked is None:
                scored = [(legacy._score(intent, major_name, position, None)[0], position)
                          for position in eligible]
                # Python's stable sort preserves the legacy equal-score position ordering exactly.
                scored.sort(key=lambda item: -item[0])
                ranked = [item[1] for item in scored[:3]]
                ranked_by_preference[key] = ranked

            for position in ranked:
                match = legacy._upsert_match(
                    db, record, position, "AUTO_MAJOR", intent, major_name, "RECOMMENDED")
                if match:
                    created += 1

        legacy._trail(db, 0, "RUN_MAJOR_MATCH", {
            "created": created,
            "records": len(records),
            "positions": len(positions),
            "majorGroups": len(eligible_by_major),
            "preferenceGroups": len(ranked_by_preference),
        })
        db.commit()
    return {"created": created}
