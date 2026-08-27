"""Bind GD-018 FILE preview tokens to guidance/plagiarism source truth.

The V2 readiness bridge only needs source presence to decide whether structured
snapshots can be generated.  Final filing additionally signs the actual source rows
so a real guidance/plagiarism edit after preview makes the old token stale.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from sqlalchemy import select

from app.models import GraduationGuidance, GraduationPlagiarismCheck
from app.services.db_service import _iso, _tid


def _hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _locked(stmt, lock: bool):
    return stmt.with_for_update() if lock else stmt


def enrich_file_source_hash(db, snapshot: dict, *, lock: bool = False) -> dict:
    rows = snapshot.get("rows") or []
    student_ids = [int(row["studentId"]) for row in rows]
    if not student_ids:
        return snapshot

    guidance_by_student: dict[int, list[dict]] = defaultdict(list)
    guidance_stmt = select(GraduationGuidance).where(
        GraduationGuidance.tenant_id == _tid(),
        GraduationGuidance.gd_student_id.in_(student_ids),
        GraduationGuidance.void_reason.is_(None),
        GraduationGuidance.is_deleted.is_(False),
    ).order_by(GraduationGuidance.gd_student_id, GraduationGuidance.guidance_date, GraduationGuidance.id)
    for item in db.scalars(_locked(guidance_stmt, lock)).all():
        guidance_by_student[int(item.gd_student_id)].append({
            "id": str(item.id), "date": _iso(item.guidance_date), "method": item.method or "",
            "content": item.content or "", "issues": item.issues or "",
            "version": int(item.version or 0),
        })

    plagiarism_by_student: dict[int, dict] = {}
    plagiarism_stmt = select(GraduationPlagiarismCheck).where(
        GraduationPlagiarismCheck.tenant_id == _tid(),
        GraduationPlagiarismCheck.gd_student_id.in_(student_ids),
        GraduationPlagiarismCheck.status == "DONE",
        GraduationPlagiarismCheck.is_deleted.is_(False),
    ).order_by(GraduationPlagiarismCheck.gd_student_id, GraduationPlagiarismCheck.id)
    for item in db.scalars(_locked(plagiarism_stmt, lock)).all():
        plagiarism_by_student[int(item.gd_student_id)] = {
            "id": str(item.id), "status": item.status, "rate": item.rate,
            "threshold": item.threshold, "overThreshold": bool(item.over_threshold),
            "disputeStatus": item.dispute_status or "", "submitAt": _iso(item.submit_at),
            "version": int(item.version or 0),
        }

    for row in rows:
        sid = int(row["studentId"])
        row["v2SourceHash"] = _hash({
            "guidance": guidance_by_student.get(sid, []),
            "plagiarism": plagiarism_by_student.get(sid),
        })
    return snapshot


def install_archive_v2_source_guard() -> None:
    from app.modules.graduation.services import graduation_archive_batch_scale as scale

    current = scale.build_snapshot
    if getattr(current, "_gd_archive_v2_source_bound", False):
        return

    def wrapped(db, batch, mode: str, *, lock: bool = False):
        snapshot = current(db, batch, mode, lock=lock)
        if str(mode or "").upper() == "FILE":
            snapshot = enrich_file_source_hash(db, snapshot, lock=lock)
        return snapshot

    wrapped._gd_archive_v2_source_bound = True
    wrapped._gd_archive_v2_source_original = current
    scale.build_snapshot = wrapped


__all__ = ["enrich_file_source_hash", "install_archive_v2_source_guard"]
