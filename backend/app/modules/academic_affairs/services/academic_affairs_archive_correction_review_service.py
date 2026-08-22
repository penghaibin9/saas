"""W1 post-archive correction review completion.

The immutable Stage C3 approval path remains the canonical owner for APPROVE. This
module fills the missing formal REJECT decision and enriches correction detail with
persisted review evidence plus server-authoritative original/proposed/resulting fact
snapshots. ARCHIVED is never reopened and REJECT never creates an official fact or
ArchiveManifest revision.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_archive_manifest_service as immutable_service
from . import academic_affairs_archive_service as archive_service

_PENDING = "PENDING_SECOND_APPROVAL"


def _review_reason(value: str) -> str:
    reason = str(value or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因至少 5 字")
    if len(reason) > 500:
        raise AppException("VALIDATION_ERROR", "驳回原因最多 500 字")
    return reason


def _target_id(value) -> int | None:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _fact_snapshot(db, business_type: str, fact_id) -> dict | None:
    """Read one immutable/current formal fact under the active tenant scope."""
    target_id = _target_id(fact_id)
    if target_id is None:
        return None

    if business_type == "GRADE":
        from app.models import AcademicGrade

        row = db.query(AcademicGrade).filter(
            AcademicGrade.id == target_id,
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.is_deleted.is_(False),
        ).first()
        if not row:
            return None
        return {
            "factType": "ACADEMIC_GRADE",
            "factId": str(row.id),
            "acadStudentId": str(row.acad_student_id),
            "courseId": str(row.course_id) if getattr(row, "course_id", None) is not None else None,
            "courseCode": getattr(row, "course_code", None),
            "courseName": getattr(row, "course_name", None),
            "term": row.term,
            "score": row.score,
            "passStatus": row.pass_status,
            "recordStatus": row.record_status,
            "attemptNo": getattr(row, "attempt_no", None),
            "passLine": getattr(row, "pass_line_snapshot", None),
            "sourceBizType": getattr(row, "source_biz_type", None),
            "sourceBizId": str(row.source_biz_id) if getattr(row, "source_biz_id", None) is not None else None,
        }

    if business_type == "GRADUATION":
        from app.models import GraduationDecisionFact

        row = db.query(GraduationDecisionFact).filter(
            GraduationDecisionFact.id == target_id,
            GraduationDecisionFact.tenant_id == _tid(),
        ).first()
        if not row:
            return None
        return {
            "factType": "GRADUATION_DECISION",
            "factId": str(row.id),
            "resultId": str(row.result_id),
            "studentId": str(row.student_id),
            "decisionNo": int(row.decision_no),
            "evaluationRunId": str(row.evaluation_run_id),
            "conclusion": row.conclusion,
            "supersedesId": str(row.supersedes_id) if row.supersedes_id else None,
            "correctionCaseId": str(row.correction_case_id) if row.correction_case_id else None,
            "decisionAt": row.decision_at.isoformat() if row.decision_at else None,
        }
    return None


def _proposed_fact_snapshot(original: dict | None, correction: dict | None) -> dict | None:
    """Display-only proposal before approval; never treated as an official fact."""
    if not isinstance(correction, dict):
        return original
    if original is None:
        return dict(correction)
    proposed = dict(original)
    proposed.update(correction)
    proposed["factId"] = None
    proposed["recordStatus"] = "PROPOSED"
    return proposed


def get_correction_case(user, case_id) -> dict:
    """Return review detail with exact original and resulting official facts."""
    base = archive_service.get_correction_case(user, case_id)
    from app.models import PostArchiveCorrectionCase

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        case = db.query(PostArchiveCorrectionCase).filter(
            PostArchiveCorrectionCase.id == int(case_id),
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.is_deleted.is_(False),
        ).first()
        if not case:
            raise not_found("归档后纠错单不存在")

        original = _fact_snapshot(db, case.business_type, case.target_ref)
        correction = base.get("correction") if isinstance(base, dict) else None
        resulting = None
        if case.status == "APPLIED" and case.official_fact_id is not None:
            resulting = _fact_snapshot(db, case.business_type, case.official_fact_id)
            if resulting is None:
                raise AppException(
                    "DATA_CONFLICT",
                    "已应用纠错单引用的正式事实不存在或不在当前租户，证据链不完整",
                    http_status=409,
                )

        base.update({
            "rejectedBy": str(case.rejected_by) if case.rejected_by is not None else None,
            "rejectedAt": case.rejected_at.isoformat() if case.rejected_at else None,
            "rejectReason": case.reject_reason,
            "originalOfficialFact": original,
            "proposedOfficialFact": _proposed_fact_snapshot(original, correction) if case.status == _PENDING else None,
            "resultingOfficialFact": resulting,
        })
        return base


def reject_correction_case(user, case_id, *, reason: str) -> dict:
    """Reject a pending correction under the same two-person/tenant/lock discipline.

    This transition intentionally has no call to the official-fact command and no
    ArchiveManifest INSERT. A repeated reject/approve-after-reject therefore fails on
    the locked current status instead of replaying side effects.
    """
    from app.models import AaArchiveBatch, PostArchiveCorrectionCase

    core = archive_service._core
    reason = _review_reason(reason)
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        actor = immutable_service._actor_id(db)
        if actor is None:
            raise AppException(
                "NO_PERMISSION",
                "当前操作人无法解析到租户内稳定账号，禁止执行高风险归档纠错复核",
                http_status=403,
            )
        case = db.query(PostArchiveCorrectionCase).filter(
            PostArchiveCorrectionCase.id == int(case_id),
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.is_deleted.is_(False),
        ).with_for_update().first()
        if not case:
            raise not_found("归档后纠错单不存在")
        if case.status != _PENDING:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "该纠错单当前状态不可二次复核",
                details={"status": case.status},
                http_status=409,
            )
        if case.created_by is None:
            raise AppException(
                "DATA_CONFLICT",
                "该高风险纠错单缺少发起人审计身份，无法证明双人复核，禁止驳回",
                http_status=409,
            )
        if int(case.created_by) == int(actor):
            raise AppException("NO_PERMISSION", "归档后纠错必须由不同操作人二次复核", http_status=403)

        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == case.archive_batch_id,
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch or batch.status != "ARCHIVED":
            raise AppException(
                "DATA_CONFLICT",
                "纠错复核时归档批次不再处于 ARCHIVED，已拒绝执行",
                http_status=409,
            )
        if any((
            case.second_approved_by is not None,
            case.applied_at is not None,
            case.official_fact_id is not None,
            case.resulting_manifest_id is not None,
        )):
            raise AppException(
                "DATA_CONFLICT",
                "待驳回纠错单已出现正式应用痕迹，禁止覆盖历史事实",
                http_status=409,
            )

        now = datetime.utcnow()
        case.rejected_by = actor
        case.rejected_at = now
        case.reject_reason = reason
        case.status = "REJECTED"
        case.updated_by = actor
        audit_reason = " ".join(reason.split())[:200]
        core._audit(
            db,
            batch.id,
            "POST_ARCHIVE_CORRECTION_REJECT",
            (
                f"caseId={case.id};type={case.business_type};requester={case.created_by};"
                f"reviewer={actor};reason={audit_reason}"
            ),
            before_val=immutable_service._json({
                "caseId": str(case.id),
                "status": _PENDING,
                "requestedBy": int(case.created_by),
                "officialFactId": None,
                "resultingManifestId": None,
            }),
            after_val=immutable_service._json({
                "caseId": str(case.id),
                "status": "REJECTED",
                "rejectedBy": int(actor),
                "rejectReason": reason,
                "officialFactId": None,
                "resultingManifestId": None,
            }),
        )
        db.commit()
        return {
            "caseId": str(case.id),
            "status": case.status,
            "rejectedBy": str(case.rejected_by),
            "rejectedAt": case.rejected_at.isoformat(),
            "rejectReason": case.reject_reason,
            "officialFactType": None,
            "officialFactId": None,
            "resultingManifestId": None,
        }
