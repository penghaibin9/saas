"""归档终态证据不可变守卫。

毕业设计备案完成后，任务书、开题、中期、指导、成果、查重、评阅、答辩评分、
成绩、互查和成绩申诉都属于归档证据。任何 Service 即使遗漏状态判断，也不能再
通过 ORM flush 修改这些对象。后续若产品需要解档，必须建设显式解档审批流程，
而不是绕过本守卫。
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models import (
    GraduationArchiveRecord,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationGrade,
    GraduationGradeAppeal,
    GraduationGuidance,
    GraduationGuidancePlan,
    GraduationMidterm,
    GraduationPeerReview,
    GraduationPlagiarismCheck,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationStudentEval,
    GraduationTaskBook,
    GraduationTopicChangeRequest,
    GraduationTopicChoice,
)

_INSTALLED = False
_EVIDENCE_MODELS = (
    GraduationTaskBook,
    GraduationProposal,
    GraduationGuidance,
    GraduationGuidancePlan,
    GraduationMidterm,
    GraduationStudentEval,
    GraduationFinal,
    GraduationPlagiarismCheck,
    GraduationReview,
    GraduationDefenseScore,
    GraduationGrade,
    GraduationGradeAppeal,
    GraduationPeerReview,
    GraduationTopicChoice,
    GraduationTopicChangeRequest,
)


def _candidate_pairs(session: Session) -> dict[int, set[int]]:
    by_tenant: dict[int, set[int]] = defaultdict(set)
    for obj in tuple(session.new) + tuple(session.dirty) + tuple(session.deleted):
        if not isinstance(obj, _EVIDENCE_MODELS):
            continue
        tenant_id = getattr(obj, "tenant_id", None)
        student_id = getattr(obj, "gd_student_id", None)
        if tenant_id is None or student_id is None:
            continue
        by_tenant[int(tenant_id)].add(int(student_id))
    return by_tenant


def _before_flush(session: Session, _flush_context, _instances) -> None:
    pairs = _candidate_pairs(session)
    if not pairs:
        return
    with session.no_autoflush:
        for tenant_id, student_ids in pairs.items():
            archived_students = set(session.scalars(select(GraduationStudent.id).where(
                GraduationStudent.tenant_id == tenant_id,
                GraduationStudent.id.in_(student_ids),
                GraduationStudent.is_deleted.is_(False),
                GraduationStudent.stage == "ARCHIVED",
            )).all())
            filed_students = set(session.scalars(select(GraduationArchiveRecord.gd_student_id).where(
                GraduationArchiveRecord.tenant_id == tenant_id,
                GraduationArchiveRecord.gd_student_id.in_(student_ids),
                GraduationArchiveRecord.is_deleted.is_(False),
                GraduationArchiveRecord.status == "FILED",
            )).all())
            blocked = sorted(int(value) for value in (archived_students | filed_students))
            if blocked:
                raise AppException(
                    "DATA_CONFLICT",
                    "毕业设计材料已备案归档，不允许继续修改归档证据；如确需更正，请先建设并执行正式解档审批流程",
                )


def register_graduation_archive_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    event.listen(Session, "before_flush", _before_flush)
    _INSTALLED = True
