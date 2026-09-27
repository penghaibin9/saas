"""包 7 事务修复：调分证据绑定必须先落库再冻结绑定快照。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models.file import FileBinding
from app.modules.internship.services import internship_score_fact_guard as base
from app.services.db_service import _tid

_INSTALLED = False
_legacy_bind = base._bind_adjustment_evidence
_legacy_verify = base._verify_evidence_snapshot


def _numeric(value) -> bool:
    return str(value or "").isdigit()


def _bind_adjustment_evidence(db, *, score, record, student, user, file_ids):
    rows = _legacy_bind(
        db,
        score=score,
        record=record,
        student=student,
        user=user,
        file_ids=file_ids,
    )
    # bind_file_to_business 与成绩命令共用当前 Session；先 flush，才能冻结真实 binding id/version。
    db.flush()
    for item in rows:
        if _numeric(item.get("bindingId")):
            continue
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == int(item["fileId"]),
            FileBinding.biz_type == "INTERNSHIP_SCORE_ADJUSTMENT",
            FileBinding.biz_id == str(score.id),
            FileBinding.relation_type == "MANUAL_SCORE_ADJUSTMENT",
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.id.desc()))
        if not binding:
            raise AppException(
                "DATA_CONFLICT",
                "人工调分依据文件未形成有效业务绑定，禁止保存成绩",
                details={"fileId": item.get("fileId"), "scoreId": str(score.id)},
            )
        item["bindingId"] = str(binding.id)
        item["bindingVersion"] = int(binding.version or 0)
        item["bindingStatus"] = binding.status
    return rows


def _verify_evidence_snapshot(db, score, evidence_rows):
    for item in evidence_rows:
        if not _numeric(item.get("bindingId")) or not _numeric(item.get("fileId")):
            raise AppException(
                "DATA_CONFLICT",
                "人工调分依据快照不完整，禁止发布成绩",
                details={"scoreId": str(score.id), "evidence": item},
            )
    return _legacy_verify(db, score, evidence_rows)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    base._bind_adjustment_evidence = _bind_adjustment_evidence
    base._verify_evidence_snapshot = _verify_evidence_snapshot
    _INSTALLED = True
