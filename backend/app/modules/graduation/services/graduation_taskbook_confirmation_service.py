"""Evidence-backed student taskbook confirmation shared by portal and miniapp."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import db_enabled
from app.models import (
    GraduationAuditTrail,
    GraduationTaskBook,
    PortalSignRecord,
)
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.services.db_service import _iso, _tid
from app.services.mobile_student_service import _require_student, _session, resolve_student


def _snapshot(taskbook: GraduationTaskBook, student) -> dict:
    return {
        "gdStudentId": str(student.id),
        "studentNo": student.student_no or "",
        "studentName": student.name or "",
        "topicTitle": student.topic_title or "",
        "advisorName": student.advisor_name or "",
        "taskbookId": str(taskbook.id),
        "taskbookVersion": int(taskbook.taskbook_version or 1),
        "objective": taskbook.objective or "",
        "content": taskbook.content or "",
        "progressPlan": taskbook.progress_plan or "",
        "outcomeRequirement": taskbook.outcome_requirement or "",
        "issuedBy": taskbook.issued_by or "",
        "issuedAt": _iso(taskbook.issued_at),
    }


def _taskbook_payload(taskbook: GraduationTaskBook, student) -> dict:
    return {
        "id": str(taskbook.id),
        "gdStudentId": str(student.id),
        "studentName": student.name or "",
        "studentNo": student.student_no or "",
        "advisorName": student.advisor_name or "",
        "objective": taskbook.objective or "",
        "content": taskbook.content or "",
        "progressPlan": taskbook.progress_plan or "",
        "outcomeRequirement": taskbook.outcome_requirement or "",
        "taskbookVersion": int(taskbook.taskbook_version or 1),
        "status": taskbook.status,
        "statusLabel": "已确认" if taskbook.status == "CONFIRMED" else taskbook.status,
        "issuedBy": taskbook.issued_by or "",
        "issuedAt": _iso(taskbook.issued_at),
        "confirmedAt": _iso(taskbook.confirmed_at),
    }


def confirm_with_evidence(user: dict, *, expected_version=None, confirm: bool = True) -> dict:
    """Confirm current taskbook and evidence record in one MySQL transaction.

    Idempotency is version + canonical content hash, so a previous version's
    signature can never be reused for changed taskbook content.
    """
    u = _require_student(user)
    if not confirm:
        raise AppException("VALIDATION_ERROR", "请先勾选确认后再签署任务书")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实签署")

    with _session() as db:
        master = resolve_student(db, u)
        if not master:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案，无法签署")
        gd_student = resolve_current_gd_student(db, u)
        if not gd_student:
            raise AppException("DATA_NOT_FOUND", "未找到你的毕业设计档案，无法签署")

        taskbook = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(),
            GraduationTaskBook.gd_student_id == gd_student.id,
            GraduationTaskBook.is_deleted.is_(False),
        ).with_for_update()).first()
        if not taskbook:
            raise AppException("DATA_NOT_FOUND", "导师尚未下达任务书")

        version = int(taskbook.taskbook_version or 1)
        if expected_version not in (None, "") and int(expected_version) != version:
            raise AppException("DATA_CONFLICT", "任务书版本已变化，请刷新后重新确认")
        if taskbook.status not in ("PENDING_CONFIRM", "CHANGE_PENDING", "CONFIRMED"):
            raise AppException("DATA_CONFLICT", "当前任务书状态不允许确认")

        snapshot = _snapshot(taskbook, gd_student)
        canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        sign_biz_id = f"{gd_student.id}:v{version}"

        sign = db.scalars(select(PortalSignRecord).where(
            PortalSignRecord.tenant_id == _tid(),
            PortalSignRecord.student_id == master.id,
            PortalSignRecord.biz_type == "GRADUATION_TASKBOOK",
            PortalSignRecord.biz_id == sign_biz_id,
            PortalSignRecord.content_hash == content_hash,
        ).with_for_update()).first()
        now = datetime.now(timezone.utc)
        if not sign:
            sign = PortalSignRecord(
                tenant_id=_tid(), student_id=master.id,
                biz_type="GRADUATION_TASKBOOK", biz_id=sign_biz_id,
                content_hash=content_hash, provider="reliable_log",
                signer_name=master.real_name, signed_at=now,
            )
            db.add(sign)
            db.flush()

        if taskbook.status != "CONFIRMED":
            before = taskbook.status
            taskbook.status = "CONFIRMED"
            taskbook.confirmed_at = now
            if gd_student.stage == "TASKBOOK_CONFIRM":
                gd_student.stage = "GUIDING"
            db.add(GraduationAuditTrail(
                tenant_id=_tid(), biz_type="TASKBOOK", biz_id=str(taskbook.id),
                action="学生确认任务书",
                operator=u.get("realName") or master.real_name or "学生本人",
                role_name=u.get("currentRoleCode") or "STUDENT",
                detail=f"v{version}; evidence={content_hash}",
                before_val=before, after_val="CONFIRMED",
                before_json={"status": before, "version": version},
                after_json={"status": "CONFIRMED", "version": version, "contentHash": content_hash},
                batch_id=gd_student.batch_id, occurred_at=now,
            ))
            from app.modules.graduation.services.graduation_risk_service import notify_risk_rescan
            notify_risk_rescan(db, gd_student.id)

        db.commit()
        return {
            "signId": str(sign.id), "contentHash": content_hash,
            "provider": sign.provider, "signedAt": _iso(sign.signed_at),
            "legalEffect": False, "confirmationType": "EVIDENCE_LOG",
            "taskbookVersion": version,
            "taskbook": _taskbook_payload(taskbook, gd_student),
        }
