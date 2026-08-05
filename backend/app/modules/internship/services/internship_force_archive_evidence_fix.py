"""包 8：强制归档依据文件先绑定、后生成不可变快照。

历史归档命令会先把原始 fileId 写入 InternshipArchive，再调用证据包快照。
证据权威守卫若在快照生成后才转换，重复采集链可能把同一文件当成另一个
正式对象再次绑定。这里把转换前移到不可变快照之前：原始 ID 只存在于当前
事务内，正式归档记录只保存 file/version/hash/binding 快照。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.models import InternshipArchive, StudentProfile
from app.modules.internship.services import internship_evidence_authority_guard as evidence_guard
from app.modules.internship.services import internship_evidence_package_service as package_service
from app.services.db_service import _tid

_INSTALLED = False
_PREVIOUS_CAPTURE = None


def _capture_archive_snapshot(db, record, evaluation, user):
    archive = db.scalar(select(InternshipArchive).where(
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.internship_id == record.id,
        InternshipArchive.is_deleted.is_(False),
    ).order_by(InternshipArchive.id.desc()).with_for_update())
    raw = archive.force_evidence_file_ids if archive else None
    if archive and raw and not evidence_guard._is_snapshot_list(raw):
        # 先移除事务内原始 ID，防止后续快照/监听器把它当成第二个正式关系。
        raw_ids = list(raw)
        archive.force_evidence_file_ids = None
        db.flush()

        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == record.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ))
        if not student:
            raise not_found("实习学生主档不存在")
        archive.force_evidence_file_ids = evidence_guard.bind_evidence(
            db,
            file_ids=raw_ids,
            biz_type="INTERNSHIP_FORCE_ARCHIVE",
            biz_id=archive.id,
            relation_type="FORCE_ARCHIVE_EVIDENCE",
            actor=user,
            record=record,
            student=student,
        )
        db.flush()

    return _PREVIOUS_CAPTURE(db, record, evaluation, user)


def install() -> None:
    global _INSTALLED, _PREVIOUS_CAPTURE
    if _INSTALLED:
        return
    # 在 evidence_guard.install() 之后调用，保留其失效复核与详情校验。
    _PREVIOUS_CAPTURE = package_service.capture_archive_snapshot
    package_service.capture_archive_snapshot = _capture_archive_snapshot
    _INSTALLED = True
