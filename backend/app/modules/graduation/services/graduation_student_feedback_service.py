"""W7.5 Student PC feedback timeline and resubmit projection.

`t_gd_review_feedback` remains the append-only feedback authority.  This module is read-only:
it scopes rows to the current student, resolves the exact reviewed FileVersion/FileObject, and
derives whether a rejected record has already been superseded by a real canonical resubmission.
No second submission state machine is introduced here.
"""
from __future__ import annotations

from sqlalchemy import select, text

from app.core.exceptions import not_found
from app.models import GraduationFinal, GraduationProposal
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services import graduation_review_feedback_service as feedback
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED


_STAGE_LABELS = {
    "PROPOSAL": "开题报告",
    "FINAL": "论文成果",
    "FORMAL": "正式评阅",
}
_RESULT_LABELS = {
    "APPROVED": "已通过",
    "REJECTED": "退回整改",
    "COMPLETED": "评阅完成",
}
_PREVIEWABLE_EXTS = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "docx"}


def _require_student(user: dict):
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise not_found("毕业设计评阅反馈不存在")


def _file_ready(file_object: FileObject | None) -> bool:
    if not file_object or file_object.is_deleted or not is_downloadable_status(file_object.status):
        return False
    return str(file_object.scan_status or SCAN_NOT_REQUIRED).upper() in READY_SCAN_STATES


def _reviewed_file(db, row: dict, student_id: int) -> dict | None:
    try:
        version_id = int(row.get("file_version_id"))
        material_id = int(row.get("material_id"))
    except (TypeError, ValueError):
        return None
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(), GraduationStudentMaterial.id == material_id,
        GraduationStudentMaterial.gd_student_id == int(student_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    )).first()
    if not material or material.asset_id is None:
        return None
    version = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.id == version_id,
        FileVersion.asset_id == int(material.asset_id), FileVersion.is_deleted.is_(False),
    )).first()
    if not version:
        return None
    file_object = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(version.file_object_id),
        FileObject.is_deleted.is_(False),
    )).first()
    if not file_object:
        return None
    ext = str(file_object.ext or "").lower().lstrip(".")
    source_sha = str(row.get("source_sha256") or "").lower()
    object_sha = str(file_object.sha256 or "").lower()
    evidence_locked = bool(source_sha and object_sha and source_sha == object_sha)
    scan_status = str(file_object.scan_status or SCAN_NOT_REQUIRED).upper()
    ready = bool(evidence_locked and _file_ready(file_object))
    allowed_actions = ["viewMetadata"]
    if ready and ext in _PREVIEWABLE_EXTS:
        allowed_actions.append("preview")
    if ready:
        allowed_actions.append("download")
    return {
        # Keep immutable version/hash evidence visible even when bytes are no longer safe to serve.
        # FileObject id is transport capability and is withheld unless both evidence and File Center
        # safety state are valid.
        "fileId": str(file_object.id) if ready else None,
        "fileVersionId": str(version.id),
        "versionNo": int(version.version_no or 0),
        "fileName": file_object.file_name,
        "mimeType": file_object.mime_type or "application/octet-stream",
        "size": int(file_object.size_bytes or 0),
        "ext": ext,
        "isCurrent": bool(version.is_current),
        "immutable": True,
        "evidenceLocked": evidence_locked,
        "sha256": row.get("source_sha256") or file_object.sha256,
        "scanStatus": scan_status,
        "readyForBusiness": ready,
        "allowedActions": allowed_actions,
        "statusText": f"评阅冻结版本 v{int(version.version_no or 0)}",
        "canPreview": bool("preview" in allowed_actions),
        "canDownload": bool("download" in allowed_actions),
    }


def _proposal_context(db, student_id: int, source_id: int) -> dict:
    source = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.id == int(source_id),
        GraduationProposal.gd_student_id == int(student_id), GraduationProposal.is_deleted.is_(False),
    )).first()
    if not source:
        # Broken historical source linkage must not manufacture a new write affordance.
        return {"sourceExists": False, "resubmitTarget": None, "resubmission": None}
    nxt = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == int(student_id),
        GraduationProposal.id > int(source.id), GraduationProposal.is_deleted.is_(False),
    ).order_by(GraduationProposal.id.asc())).first()
    return {
        "sourceExists": True,
        "sourceVersion": source.version or "",
        "sourceStatus": source.status,
        "resubmitTarget": {"kind": "PROPOSAL"},
        "resubmission": None if not nxt else {
            "recordId": str(nxt.id), "version": nxt.version or "", "status": nxt.status,
        },
    }


def _final_context(db, student_id: int, source_id: int) -> dict:
    source = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.id == int(source_id),
        GraduationFinal.gd_student_id == int(student_id), GraduationFinal.is_deleted.is_(False),
    )).first()
    if not source:
        # In particular, never infer 初稿/定稿 from mutable current state when the reviewed
        # source record is missing. The feedback remains visible but remediation is fail-closed.
        return {"sourceExists": False, "resubmitTarget": None, "resubmission": None}
    nxt = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == int(student_id),
        GraduationFinal.final_type == source.final_type, GraduationFinal.id > int(source.id),
        GraduationFinal.is_deleted.is_(False),
    ).order_by(GraduationFinal.id.asc())).first()
    return {
        "sourceExists": True,
        "sourceVersion": source.version or "",
        "sourceStatus": source.status,
        "resubmitTarget": {"kind": "FINAL", "finalType": source.final_type},
        "resubmission": None if not nxt else {
            "recordId": str(nxt.id), "version": nxt.version or "", "status": nxt.status,
            "finalType": nxt.final_type,
        },
    }


def student_feedback_timeline(user: dict) -> dict:
    """Return only student-visible, append-only W7 feedback for the current graduation record."""
    _require_student(user)
    with session() as db:
        student = resolve_current_gd_student(db, user)
        if not student:
            return {"hasData": False, "items": [], "latestActionable": None}
        rows = db.execute(text(
            "SELECT * FROM t_gd_review_feedback "
            "WHERE tenant_id=:tenant_id AND gd_student_id=:student_id AND visible_to_student=1 "
            "ORDER BY created_at ASC,id ASC"
        ), {"tenant_id": int(_tid()), "student_id": int(student.id)}).mappings().all()
        items: list[dict] = []
        for raw in rows:
            row = dict(raw)
            public = feedback.public_feedback(row) or {}
            stage = str(public.get("stage") or "").upper()
            try:
                source_id = int(public.get("sourceRecordId") or 0)
            except (TypeError, ValueError):
                source_id = 0
            if stage == "PROPOSAL" and source_id:
                context = _proposal_context(db, int(student.id), source_id)
            elif stage == "FINAL" and source_id:
                context = _final_context(db, int(student.id), source_id)
            else:
                context = {"sourceExists": bool(source_id), "resubmitTarget": None, "resubmission": None}
            rejected = str(public.get("result") or "").upper() == "REJECTED"
            action_required = bool(rejected and context.get("resubmitTarget") and not context.get("resubmission"))
            items.append({
                **public,
                "stageLabel": _STAGE_LABELS.get(stage, stage or "评阅反馈"),
                "resultLabel": _RESULT_LABELS.get(str(public.get("result") or "").upper(), public.get("result") or ""),
                "reviewedFile": _reviewed_file(db, row, int(student.id)),
                "actionRequired": action_required,
                **context,
            })
        actionable = next((item for item in reversed(items) if item.get("actionRequired")), None)
        return {
            "hasData": bool(items),
            "gdStudentId": str(student.id),
            "items": items,
            "latestActionable": actionable,
            "appendOnly": True,
            "authority": "t_gd_review_feedback",
        }


__all__ = ["student_feedback_timeline"]
