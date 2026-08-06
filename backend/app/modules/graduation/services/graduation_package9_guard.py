"""包 9：毕设导师、答辩、checklist 与不可变归档统一生产守卫。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint, event, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.models import (
    GraduationArchiveRecord,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationGrade,
    GraduationMidterm,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTaskBook,
)
from app.models.base import Base, CommonMixin, PKMixin, TenantMixin
from app.modules.graduation.services import graduation_archive_consistency as archive_consistency
from app.modules.graduation.services import graduation_archive_service as archive_service
from app.modules.graduation.services import graduation_defense_score_service as defense_score_service
from app.modules.graduation.services import graduation_mentor_service as mentor_service
from app.modules.graduation.services.graduation_archive_terminal_guard import register_graduation_archive_guard
from app.services.db_service import _tid


class GraduationArchiveVersion(PKMixin, TenantMixin, CommonMixin, Base):
    """每次 FILED 生成一条追加式归档版本；历史版本永不覆盖。"""

    __tablename__ = "t_gd_archive_version"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "archive_record_id", "archive_version",
            name="uk_gd_archive_version_no",
        ),
        Index("ix_gd_archive_current", "tenant_id", "archive_record_id", "current_flag"),
        Index("ix_gd_archive_student_version", "tenant_id", "gd_student_id", "archive_version"),
    )

    archive_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    archive_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    previous_archive_id: Mapped[int | None] = mapped_column(BigInteger)
    invalidated_reason: Mapped[str | None] = mapped_column(String(500))
    source_manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    filed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    filed_by: Mapped[str] = mapped_column(String(100), nullable=False)


_INSTALLED = False
_PREVIOUS_BATCH_ASSIGN = None
_PREVIOUS_ENTER_SCORE = None
_PENDING_ARCHIVE_VERSION_KEY = "graduation_package9_pending_archive_versions"
_PROCESSING_ARCHIVE_VERSION_KEY = "graduation_package9_processing_archive_versions"


def _latest(db, model, student_id, *criteria):
    return db.scalars(select(model).where(
        model.tenant_id == _tid(),
        model.gd_student_id == int(student_id),
        model.is_deleted.is_(False),
        *criteria,
    ).order_by(model.id.desc()).limit(1)).first()


def _strict_check_completeness(db, student: GraduationStudent) -> tuple[list[dict], list[str]]:
    """只允许当前租户、未删除、最新且有效的事实满足归档清单。"""
    taskbook = _latest(db, GraduationTaskBook, student.id)
    proposal = _latest(db, GraduationProposal, student.id)
    midterm = _latest(db, GraduationMidterm, student.id)
    final = _latest(db, GraduationFinal, student.id, GraduationFinal.final_type == "定稿")
    review = (
        _latest(db, GraduationReview, student.id, GraduationReview.gd_final_id == int(final.id))
        if final else None
    )
    defense = _latest(db, GraduationDefenseScore, student.id)
    grade = _latest(db, GraduationGrade, student.id)

    present = {
        "taskbook": bool(taskbook and taskbook.status == "CONFIRMED"),
        "proposal": bool(proposal and proposal.status == "APPROVED"),
        "midterm": bool(midterm and midterm.status in {"CHECKED_PASS", "RECTIFIED_PASS"}),
        "final": bool(final and final.status == "APPROVED"),
        "review": bool(review and review.status == "COMPLETED"),
        "defenseScore": bool(defense and defense.status == "CONFIRMED"),
        "grade": bool(grade and grade.status == "PUBLISHED"),
    }
    checklist = [
        {"item": key, "label": label, "present": present[key]}
        for key, label in archive_service.CHECKLIST_ITEMS
    ]
    missing = [
        label for key, label in archive_service.CHECKLIST_ITEMS if not present[key]
    ]
    return checklist, missing


def _strict_manifest_payload(db, student: GraduationStudent, archive_batch_no: str) -> dict:
    """归档 manifest 与 checklist 使用同一条最新有效成绩事实。"""
    payload = archive_consistency.manifest_payload(db, student, archive_batch_no)
    grade = _latest(db, GraduationGrade, student.id, GraduationGrade.status == "PUBLISHED")
    if not grade:
        raise AppException("DATA_CONFLICT", "归档缺少当前有效的已发布成绩")
    payload["grade"] = {
        "id": str(grade.id),
        "status": grade.status,
        "score": grade.total_score,
        "sourceHash": grade.source_snapshot_hash,
        "version": grade.version,
    }
    payload["manifestHash"] = archive_consistency._json_hash(payload)
    return payload


def _normalize_assignment_item(item: dict) -> dict:
    if not isinstance(item, dict):
        raise AppException("VALIDATION_ERROR", "导师分配项必须是对象")
    allowed = {"gdStudentId", "mentorId", "externalAdvisorId", "reason"}
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise AppException(
            "VALIDATION_ERROR",
            "导师分配只接受稳定主体 ID",
            details={"unknownFields": unknown},
        )
    student_id = str(item.get("gdStudentId") or "").strip()
    mentor_id = str(item.get("mentorId") or "").strip()
    external_id = str(item.get("externalAdvisorId") or "").strip()
    if not student_id:
        raise AppException("VALIDATION_ERROR", "gdStudentId 必填")
    if bool(mentor_id) == bool(external_id):
        raise AppException(
            "VALIDATION_ERROR",
            "mentorId 与 externalAdvisorId 必须且只能提供一个",
        )
    return {
        "gdStudentId": student_id,
        "mentorId": mentor_id or external_id,
        "reason": item.get("reason"),
    }


def _batch_assign(assignments: list[dict]) -> dict:
    normalized = [_normalize_assignment_item(item) for item in (assignments or [])]
    return _PREVIOUS_BATCH_ASSIGN(normalized)


def _enter_score(*args, **kwargs):
    """groupId 永远从 GraduationStudent.defense_group_id 解析，请求值一律拒绝。"""
    positional_group_id = args[6] if len(args) > 6 else None
    requested_group_id = kwargs.get("defense_group_id")
    if positional_group_id not in (None, "") or requested_group_id not in (None, ""):
        raise AppException("VALIDATION_ERROR", "defenseGroupId 由服务端权威解析，禁止请求指定")
    if len(args) > 6:
        mutable = list(args)
        mutable[6] = None
        args = tuple(mutable)
    kwargs["defense_group_id"] = None
    return _PREVIOUS_ENTER_SCORE(*args, **kwargs)


def _filed_transition(archive: GraduationArchiveRecord) -> bool:
    if str(archive.status or "").upper() != "FILED":
        return False
    state = inspect(archive)
    is_new = state.session is not None and archive in state.session.new
    return bool(is_new or state.attrs.status.history.has_changes())


def _actor_name(archive: GraduationArchiveRecord) -> str:
    user = get_current_user_ctx() or {}
    return str(
        archive.verified_by
        or user.get("realName")
        or user.get("loginName")
        or user.get("userId")
        or "系统"
    )


def _queue_archive_versions(session: Session, flush_context, instances) -> None:
    """在 flush 前只记录 FILED 转换；主记录 ID 由本轮 flush 生成。"""
    if session.info.get(_PROCESSING_ARCHIVE_VERSION_KEY):
        return
    pending = session.info.setdefault(_PENDING_ARCHIVE_VERSION_KEY, [])
    known = {id(row) for row in pending}
    for archive in list(session.new) + list(session.dirty):
        if not isinstance(archive, GraduationArchiveRecord) or not _filed_transition(archive):
            continue
        if id(archive) not in known:
            pending.append(archive)
            known.add(id(archive))


def _append_archive_version(session: Session, archive: GraduationArchiveRecord) -> None:
    if archive.id is None:
        raise AppException("DATA_CONFLICT", "归档主记录尚未取得稳定 ID")

    student = session.scalars(select(GraduationStudent).where(
        GraduationStudent.id == int(archive.gd_student_id),
        GraduationStudent.tenant_id == int(archive.tenant_id),
        GraduationStudent.is_deleted.is_(False),
    ).with_for_update()).first()
    if not student:
        raise AppException("DATA_CONFLICT", "归档学生不存在或已失效")
    _checklist, missing = _strict_check_completeness(session, student)
    if missing:
        raise AppException(
            "DATA_CONFLICT",
            "归档来源事实不完整，禁止形成 FILED 版本",
            details={"missingItems": missing},
        )

    manifest = _strict_manifest_payload(
        session,
        student,
        str(archive.archive_batch_no or ""),
    )
    if manifest.get("fileErrors"):
        raise AppException(
            "DATA_CONFLICT",
            "归档文件证据不完整",
            details={"fileErrors": list(manifest.get("fileErrors") or [])[:10]},
        )
    manifest_hash = str(manifest.get("manifestHash") or "")
    if len(manifest_hash) != 64:
        raise AppException("DATA_CONFLICT", "归档来源清单 hash 生成失败")
    archive.manifest_hash = manifest_hash

    current_rows = list(session.scalars(select(GraduationArchiveVersion).where(
        GraduationArchiveVersion.tenant_id == int(archive.tenant_id),
        GraduationArchiveVersion.archive_record_id == int(archive.id),
        GraduationArchiveVersion.current_flag.is_(True),
        GraduationArchiveVersion.is_deleted.is_(False),
    ).order_by(GraduationArchiveVersion.archive_version.desc()).with_for_update()).all())
    if len(current_rows) > 1:
        raise AppException("DATA_CONFLICT", "同一毕设归档存在多个当前版本")
    previous = current_rows[0] if current_rows else None
    if previous:
        previous.current_flag = False
        if not previous.invalidated_reason:
            previous.invalidated_reason = "SUPERSEDED_BY_REFILING"

    next_version = int(previous.archive_version if previous else 0) + 1
    filed_at = archive.filed_at or datetime.now(timezone.utc)
    session.add(GraduationArchiveVersion(
        tenant_id=int(archive.tenant_id),
        archive_record_id=int(archive.id),
        gd_student_id=int(archive.gd_student_id),
        archive_version=next_version,
        current_flag=True,
        previous_archive_id=int(previous.id) if previous else None,
        invalidated_reason=None,
        source_manifest_json=manifest,
        source_manifest_hash=manifest_hash,
        archive_batch_no=str(archive.archive_batch_no or ""),
        filed_at=filed_at,
        filed_by=_actor_name(archive),
    ))


def _append_archive_versions(session: Session, flush_context) -> None:
    """flush 后主记录已取得稳定 ID，再追加不可变版本。"""
    pending = session.info.pop(_PENDING_ARCHIVE_VERSION_KEY, [])
    if not pending:
        return
    session.info[_PROCESSING_ARCHIVE_VERSION_KEY] = True
    try:
        for archive in pending:
            _append_archive_version(session, archive)
    finally:
        session.info.pop(_PROCESSING_ARCHIVE_VERSION_KEY, None)


def install() -> None:
    global _INSTALLED, _PREVIOUS_BATCH_ASSIGN, _PREVIOUS_ENTER_SCORE
    if _INSTALLED:
        return
    register_graduation_archive_guard()
    archive_service._base_check_completeness = _strict_check_completeness
    _PREVIOUS_BATCH_ASSIGN = mentor_service.batch_assign
    mentor_service.batch_assign = _batch_assign
    _PREVIOUS_ENTER_SCORE = defense_score_service.enter_score
    defense_score_service.enter_score = _enter_score
    event.listen(Session, "before_flush", _queue_archive_versions, insert=True)
    event.listen(Session, "after_flush_postexec", _append_archive_versions, insert=True)
    _INSTALLED = True
