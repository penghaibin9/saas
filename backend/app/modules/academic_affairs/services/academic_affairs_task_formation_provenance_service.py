"""A-owned TeachingTask formation provenance consumer boundary.

Only a persisted ``source_program_course_id`` may establish ProgramCourse provenance.
Course/class labels, current Program activation, major/grade and task-majority heuristics
are deliberately excluded.  Legacy/incomplete rows remain UNKNOWN; contradictory direct
links are CONFLICT.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _tid, session

from .academic_affairs_task_formation_policy import normalize_formation_mode

STATUS_PROVEN = "PROVEN"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_CONFLICT = "CONFLICT"
_UNLOADED = object()


def _snapshot(task, *, status: str, source_id=None, formation_mode=None, blockers=()) -> dict:
    return {
        "status": status,
        "teachingTaskId": str(task.id),
        "sourceProgramCourseId": str(source_id or ""),
        "formationMode": str(formation_mode or ""),
        "blockers": list(blockers),
    }


def _normalized(value):
    try:
        return normalize_formation_mode(value), None
    except ValueError:
        return None, "FORMATION_MODE_INVALID"


def resolve_program_course_formation_snapshot(db, source, *, tenant_id: int, proof_bundle=_UNLOADED) -> dict:
    """Use the exact source or its immutable, authorized historical evidence only."""
    from app.models import AaProgram, AaProgramCourseFormationProof
    from app.models.file import FileObject
    from app.services.file_access_service import _scan_ready
    from .academic_affairs_program_formation_proof_service import _hash, source_fingerprint

    def result(status, mode=None, blocker=None, proof=None):
        value = {"status": status, "formationMode": mode or "", "blockers": [blocker] if blocker else []}
        if proof:
            value.update(proofId=str(proof.id), proofOrigin="HISTORICAL_CONFIRMATION")
        return value

    if int(source.tenant_id) != int(tenant_id) or source.is_deleted:
        return result(STATUS_CONFLICT, blocker="SOURCE_PROGRAM_COURSE_NOT_FOUND")
    source_mode, error = _normalized(source.formation_mode)
    if error:
        return result(STATUS_CONFLICT, blocker="SOURCE_PROGRAM_COURSE_FORMATION_INVALID")
    if proof_bundle is _UNLOADED:
        proof = db.scalar(select(AaProgramCourseFormationProof).where(
            AaProgramCourseFormationProof.tenant_id == int(tenant_id),
            AaProgramCourseFormationProof.program_course_id == source.id,
        ))
    else:
        proof = proof_bundle[0] if proof_bundle else None
    if not proof:
        return result(STATUS_PROVEN, source_mode) if source_mode else result(
            STATUS_UNKNOWN, blocker="FORMATION_MODE_UNRESOLVED")
    program = db.scalar(select(AaProgram).where(
        AaProgram.tenant_id == int(tenant_id), AaProgram.id == source.program_id,
        AaProgram.is_deleted.is_(False),
    )) if proof_bundle is _UNLOADED else proof_bundle[1]
    proof_mode, proof_error = _normalized(proof.formation_mode)
    if (not program or proof_error or not proof_mode or source.formation_mode is not None
        or proof.original_formation_mode is not None or proof.program_id != source.program_id
        or proof.course_id != source.course_id or proof.open_term_no != source.open_term_no
        or proof.credit_snapshot != source.credit_snapshot
        or proof.source_fingerprint != source_fingerprint(source, program)):
        return result(STATUS_CONFLICT, blocker="FORMATION_PROOF_SOURCE_CHANGED")
    if proof.payload_hash != _hash({"source": str(source.id), "mode": proof_mode,
        "file": str(proof.evidence_file_id), "locator": proof.evidence_locator,
        "reason": proof.reason, "fingerprint": proof.source_fingerprint}):
        return result(STATUS_CONFLICT, blocker="FORMATION_PROOF_PAYLOAD_CHANGED")
    file = db.scalar(select(FileObject).where(
        FileObject.tenant_id == int(tenant_id), FileObject.id == proof.evidence_file_id,
        FileObject.is_deleted.is_(False),
    )) if proof_bundle is _UNLOADED else proof_bundle[2]
    if (not file or not _scan_ready(file) or not file.sha256
        or file.sha256.lower() != proof.evidence_sha256.lower()):
        return result(STATUS_CONFLICT, blocker="FORMATION_PROOF_EVIDENCE_UNAVAILABLE")
    return result(STATUS_PROVEN, proof_mode, proof=proof)


def resolve_program_course_formation_snapshots(db, sources, *, tenant_id: int, lock=False) -> dict:
    """Batch evidence joins in bounded chunks, rather than one query per task/class."""
    from app.models import AaProgram, AaProgramCourseFormationProof as Proof
    from app.models.file import FileObject
    tid = int(tenant_id)
    source_ids = [source.id for source in sources if int(source.tenant_id) == tid]
    bundles = {}
    for offset in range(0, len(source_ids), 500):
        statement = select(Proof, AaProgram, FileObject).outerjoin(AaProgram,
            (AaProgram.id == Proof.program_id) & (AaProgram.tenant_id == tid) & AaProgram.is_deleted.is_(False)
        ).outerjoin(FileObject,
            (FileObject.id == Proof.evidence_file_id) & (FileObject.tenant_id == tid) & FileObject.is_deleted.is_(False)
        ).where(Proof.tenant_id == tid, Proof.program_course_id.in_(source_ids[offset:offset + 500]))
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        rows = db.execute(statement).all()
        bundles.update({row[0].program_course_id: row for row in rows})
    return {source.id: resolve_program_course_formation_snapshot(db, source,
        tenant_id=tid, proof_bundle=bundles.get(source.id)) for source in sources}


def resolve_task_formation_snapshot(db, task_id, *, tenant_id: int) -> dict:
    """Return B-consumable provenance from the persisted direct source link only."""
    try:
        tid = int(tenant_id)
        task_pk = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("positive tenant_id and task_id are required") from exc
    if tid <= 0 or task_pk <= 0:
        raise ValueError("positive tenant_id and task_id are required")

    from app.models import AaProgramCourse, AaTeachingTask

    task = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.id == task_pk,
        AaTeachingTask.tenant_id == tid,
        AaTeachingTask.is_deleted.is_(False),
    )).first()
    if not task:
        raise not_found("教学任务不存在")

    source_id = getattr(task, "source_program_course_id", None)
    task_mode, task_error = _normalized(getattr(task, "formation_mode", None))
    if task_error:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id,
            formation_mode=getattr(task, "formation_mode", None),
            blockers=("TASK_FORMATION_MODE_INVALID",),
        )
    if not source_id:
        return _snapshot(
            task, status=STATUS_UNKNOWN, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_ID_MISSING",),
        )

    source = db.scalars(select(AaProgramCourse).where(
        AaProgramCourse.id == int(source_id),
        AaProgramCourse.tenant_id == tid,
        AaProgramCourse.is_deleted.is_(False),
    )).first()
    if not source:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_NOT_FOUND",),
        )

    if int(getattr(source, "course_id", 0) or 0) != int(getattr(task, "course_id", 0) or 0):
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_COURSE_MISMATCH",),
        )
    source_snapshot = resolve_program_course_formation_snapshot(db, source, tenant_id=tid)
    source_mode = source_snapshot["formationMode"]
    if source_snapshot["status"] == STATUS_CONFLICT:
        return _snapshot(task, status=STATUS_CONFLICT, source_id=source_id,
            formation_mode=task_mode, blockers=source_snapshot["blockers"])
    if source_snapshot.get("proofId") and not task_mode:
        task_mode = source_mode
    if not task_mode or not source_mode:
        return _snapshot(
            task, status=STATUS_UNKNOWN, source_id=source_id, formation_mode=task_mode,
            blockers=("FORMATION_MODE_UNRESOLVED",),
        )
    if task_mode != source_mode:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("TASK_SOURCE_FORMATION_MISMATCH",),
        )

    result = _snapshot(
        task, status=STATUS_PROVEN, source_id=source_id, formation_mode=task_mode,
    )
    if source_snapshot.get("proofId"):
        result.update(proofId=source_snapshot["proofId"], proofOrigin=source_snapshot["proofOrigin"])
    return result


def get_task_formation_snapshot(task_id) -> dict:
    """Request-context convenience facade; internal callers may share their DB session above."""
    with session() as db:
        return resolve_task_formation_snapshot(db, task_id, tenant_id=_tid())
