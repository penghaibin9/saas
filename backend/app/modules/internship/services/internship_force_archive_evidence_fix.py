"""包 8：强制归档依据只在稳定 archive.id 上绑定并冻结。

原始 fileId 在预备 flush 期间由事务暂存守卫持续隐藏，不写入正式归档记录，
也不参与任何通用文件监听器。归档主记录取得稳定 ID 后，本模块一次性消费暂存，
建立唯一权威 binding，再保存 file/version/hash/binding 不可变快照。
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

    raw = None
    if archive:
        # 延迟导入避免服务包安装阶段形成循环依赖。
        from app.modules.internship.services import (
            internship_archive_preflush_evidence_guard as preflush_guard,
        )

        raw = preflush_guard.pop_raw_evidence(db, archive)
        if raw is None:
            raw = archive.force_evidence_file_ids

    if archive and raw and not evidence_guard._is_snapshot_list(raw):
        raw_ids = list(raw)
        # 正式行在绑定完成前保持空值，禁止任何监听器看到未冻结的原始 fileId。
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
