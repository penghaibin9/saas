"""P2-01 / AA-004 formal major-split allocation serialization.

Dry-run remains the legacy read-only advisory path. Formal allocation keeps the
existing GPA/studentNo/preference/capacity algorithm verbatim, adding only the fixed
Batch -> Option(id ASC) -> Volunteer(id ASC) lock order and locked CLOSED recheck.
"""
from __future__ import annotations

import json

from . import academic_affairs_major_split_service as _legacy


def allocate(user, batch_id, dry_run=False) -> dict:
    if dry_run:
        return _legacy.allocate(user, batch_id, dry_run=True)

    from app.models import AaMajorSplitBatch, AaMajorSplitOption, AaMajorSplitVolunteer

    with _legacy.session() as db:
        _legacy._require_school(user, db)
        batch = db.query(AaMajorSplitBatch).filter(
            AaMajorSplitBatch.id == int(batch_id),
            AaMajorSplitBatch.tenant_id == _legacy._tid(),
            AaMajorSplitBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise _legacy.not_found("分流批次不存在")
        if batch.status != "CLOSED":
            raise _legacy._invalid("请先截止志愿再分配（已分配批次请用人工调剂）")

        options = db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _legacy._tid(),
            AaMajorSplitOption.batch_id == batch.id,
            AaMajorSplitOption.is_deleted.is_(False),
        ).order_by(AaMajorSplitOption.id).with_for_update().all()
        volunteers = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _legacy._tid(),
            AaMajorSplitVolunteer.batch_id == batch.id,
            AaMajorSplitVolunteer.is_deleted.is_(False),
        ).order_by(AaMajorSplitVolunteer.id).with_for_update().all()

        opts = {int(option.major_id): option for option in options}
        gpa = _legacy._gpa_of(db, [volunteer.student_id for volunteer in volunteers])
        remain = {
            major_id: max(0, option.capacity - option.allocated_count)
            for major_id, option in opts.items()
        }
        ordered = sorted(
            volunteers,
            key=lambda volunteer: (
                -(gpa.get(int(volunteer.student_id), 0)),
                volunteer.student_no or "",
                volunteer.id,
            ),
        )
        allocated = 0
        unallocated = 0
        for volunteer in ordered:
            choices = [
                int(value)
                for value in (json.loads(volunteer.choices_json) if volunteer.choices_json else [])
            ]
            got = None
            for rank, major_id in enumerate(choices, start=1):
                if remain.get(major_id, 0) > 0:
                    got = (major_id, rank)
                    remain[major_id] -= 1
                    break
            volunteer.gpa_snapshot = gpa.get(int(volunteer.student_id), 0)
            if got:
                volunteer.result_major_id = got[0]
                volunteer.result_choice_rank = got[1]
                volunteer.status = "ALLOCATED"
                allocated += 1
            else:
                volunteer.result_major_id = None
                volunteer.result_choice_rank = None
                volunteer.status = "UNALLOCATED"
                unallocated += 1

        for major_id, option in opts.items():
            option.allocated_count = (
                option.capacity - remain.get(major_id, 0)
                if major_id in remain else option.allocated_count
            )
        batch.status = "ALLOCATED"
        _legacy._audit(db, batch.id, "SPLIT_ALLOCATE", f"分配{allocated}/待调剂{unallocated}")
        db.commit()
        return {
            "batchId": str(batch.id),
            "dryRun": False,
            "allocated": allocated,
            "unallocated": unallocated,
            "options": _legacy._summary(volunteers, opts, remain),
        }
