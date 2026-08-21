"""W7.1 formal-review canonical FileVersion guard.

This module extends the existing GraduationReview authority instead of introducing a second
review/file state machine.  Assignment freezes the approved THESIS_FINAL material version and
submit re-checks the exact immutable FileObject SHA/security facts before mutating review state.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, String, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import GraduationFinal, GraduationReview, GraduationStudent
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.materials.rule_service import rule_item
from app.modules.graduation.policies import review_policy
from app.modules.graduation.services import graduation_review_service as svc
from app.modules.graduation.services.graduation_scope_service import has_full_scope
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED

_INSTALLED = False
_PREVIOUS_REVIEW_ROW = None


def _install_model_columns() -> None:
    """Attach W7.1 columns to the existing mapped authority until graduation.py is next compacted."""
    columns = {
        "material_id": Column(BigInteger, nullable=True),
        "file_version_id": Column(BigInteger, nullable=True),
        "source_sha256": Column(String(64), nullable=True),
        "started_at": Column(DateTime, nullable=True),
    }
    for name, column in columns.items():
        if not hasattr(GraduationReview, name):
            setattr(GraduationReview, name, column)


def _conflict(message: str, **details):
    raise AppException(
        "APPROVAL_VERSION_CONFLICT",
        message,
        http_status=409,
        details=details or None,
    )


def _assert_file_security(file_obj: FileObject) -> str:
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    if file_obj.is_deleted or not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
        raise AppException(
            "FILE_NOT_READY",
            "当前文件安全状态发生变化，暂不能提交评阅",
            http_status=409,
        )
    digest = str(file_obj.sha256 or "").strip()
    if len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
        raise AppException("FILE_HASH_MISSING", "文件缺少可信 SHA-256，禁止评阅", http_status=409)
    return digest.lower()


def _authoritative_snapshot(db, stu: GraduationStudent, final: GraduationFinal):
    if not stu.batch_id:
        _conflict("学生未绑定毕业设计批次，无法冻结正式评阅版本")
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(stu.batch_id),
        GraduationStudentMaterial.gd_student_id == int(stu.id),
        GraduationStudentMaterial.material_code == "THESIS_FINAL",
        GraduationStudentMaterial.source_record_type == "FINAL",
        GraduationStudentMaterial.source_record_id == int(final.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if not material or not material.asset_id or not material.current_version_id:
        _conflict("正式定稿缺少 canonical FileVersion，无法分配评阅任务", gdFinalId=str(final.id))

    version = db.scalars(select(FileVersion).where(
        FileVersion.id == int(material.current_version_id),
        FileVersion.tenant_id == _tid(),
        FileVersion.asset_id == int(material.asset_id),
        FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if not version:
        _conflict("正式定稿的 FileVersion 不存在")
    if not version.is_current or str(version.status or "").upper() != "APPROVED":
        _conflict(
            "正式评阅只能冻结当前已通过定稿版本",
            fileVersionId=str(version.id),
            fileVersionStatus=str(version.status or ""),
        )

    file_obj = db.scalars(select(FileObject).where(
        FileObject.id == int(version.file_object_id),
        FileObject.tenant_id == _tid(),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if not file_obj:
        _conflict("正式定稿的文件对象不存在")
    digest = _assert_file_security(file_obj)

    # Resolve the enabled rule as an additional authority check.  The material row remains the
    # business instance; no new ReviewFile table or file authority is introduced.
    rule_item(db, int(stu.batch_id), "THESIS_FINAL")
    return material, version, file_obj, digest


def _verify_frozen_snapshot(db, r: GraduationReview, stu: GraduationStudent):
    if not r.material_id or not r.file_version_id or not str(r.source_sha256 or "").strip():
        _conflict(
            "该历史评阅任务缺少版本快照，请重新分配后再评阅",
            reviewId=str(r.id),
        )
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.id == int(r.material_id),
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(stu.batch_id),
        GraduationStudentMaterial.gd_student_id == int(stu.id),
        GraduationStudentMaterial.material_code == "THESIS_FINAL",
        GraduationStudentMaterial.source_record_type == "FINAL",
        GraduationStudentMaterial.source_record_id == int(r.gd_final_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if not material or int(material.current_version_id or 0) != int(r.file_version_id):
        _conflict(
            "学生材料版本已变化，为避免批错版本，本次提交已停止。请重新载入最新材料后继续。",
            reviewId=str(r.id),
            frozenFileVersionId=str(r.file_version_id),
            currentFileVersionId=str(material.current_version_id) if material else None,
        )
    version = db.scalars(select(FileVersion).where(
        FileVersion.id == int(r.file_version_id),
        FileVersion.tenant_id == _tid(),
        FileVersion.asset_id == int(material.asset_id),
        FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if not version or not version.is_current or str(version.status or "").upper() != "APPROVED":
        _conflict("评阅目标 FileVersion 已变化，请重新载入")
    file_obj = db.scalars(select(FileObject).where(
        FileObject.id == int(version.file_object_id),
        FileObject.tenant_id == _tid(),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if not file_obj:
        _conflict("评阅目标文件对象不存在")
    digest = _assert_file_security(file_obj)
    if digest != str(r.source_sha256).strip().lower():
        _conflict(
            "评阅目标文件摘要已变化，请重新载入",
            frozenSha256=str(r.source_sha256),
            currentSha256=digest,
        )
    return material, version, file_obj


def _review_row(r: GraduationReview, stu=None) -> dict:
    row = _PREVIOUS_REVIEW_ROW(r, stu)
    row.update({
        "version": int(r.version or 0),
        "materialId": str(r.material_id) if r.material_id else None,
        "fileVersionId": str(r.file_version_id) if r.file_version_id else None,
        "sourceSha256": r.source_sha256 or None,
        "startedAt": svc._iso(r.started_at) if getattr(r, "started_at", None) else None,
    })
    return row


def assign_review(gd_student_id, reviewer_name: str | None = None, gd_final_id=None,
                  reviewer_mentor_id=None) -> dict:
    """Freeze the server-authoritative approved final; caller-supplied gd_final_id is never authority."""
    from app.modules.graduation.services import graduation_identity as gid

    with session() as db:
        stu = svc._stu(db, gd_student_id)
        review_policy.authorize(db, stu, "assign")
        reviewer = (reviewer_name or "").strip()
        mid = None
        if reviewer_mentor_id not in (None, ""):
            mentor = gid.require_mentor(db, reviewer_mentor_id)
            mid = int(mentor.id)
            reviewer = (mentor.teacher_name or "").strip()
        if not reviewer or not mid:
            raise AppException("VALIDATION_ERROR", "评阅任务必须选择已绑定导师台账的评阅人")
        if gid.sod_conflict_with_advisor(db, stu, reviewer_mentor_id=mid, reviewer_name=reviewer):
            raise AppException("VALIDATION_ERROR", "评阅人不得是该生指导教师（SoD 冲突）")

        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.gd_student_id == stu.id,
            GraduationFinal.final_type == "定稿",
            GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).with_for_update()).first()
        if not final:
            raise AppException("DATA_CONFLICT", "请先完成并通过正式定稿，再分配评阅任务")
        material, version, _, digest = _authoritative_snapshot(db, stu, final)
        final_id = int(final.id)

        existing = db.scalars(select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(),
            GraduationReview.gd_student_id == stu.id,
            GraduationReview.gd_final_id == final_id,
            GraduationReview.reviewer_mentor_id == mid,
            GraduationReview.status.in_(("ASSIGNED", "REVIEWING", "RETURNED")),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            if not existing.material_id or not existing.file_version_id or not existing.source_sha256:
                existing.material_id = int(material.id)
                existing.file_version_id = int(version.id)
                existing.source_sha256 = digest
                existing.version += 1
                svc._audit(db, "REVIEW", existing.id, "补齐正式评阅版本快照",
                           detail=f"fileVersionId={version.id}")
                db.commit()
            return _review_row(existing, stu)

        actor, _ = svc._op()
        r = GraduationReview(
            tenant_id=_tid(), gd_student_id=stu.id, gd_final_id=final_id,
            reviewer_name=reviewer, reviewer_mentor_id=mid, status="ASSIGNED",
            assigned_by=actor, assigned_at=datetime.now(timezone.utc),
            material_id=int(material.id), file_version_id=int(version.id), source_sha256=digest,
        )
        db.add(r)
        db.flush()
        svc._audit(
            db, "REVIEW", r.id, "分配评阅任务",
            detail=f"{stu.name}→{reviewer};fileVersionId={version.id};sha256={digest}",
        )
        db.commit()
        return _review_row(r, stu)


def submit_review(rid, score: int, opinion: str, expected_version=None, file_version_id=None) -> dict:
    """Submit only against the frozen business version + FileVersion + SHA snapshot."""
    from app.modules.graduation.services import graduation_identity as gid

    with session() as db:
        r = db.scalars(select(GraduationReview).where(
            GraduationReview.id == int(rid),
            GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("评阅任务不存在")
        stu = db.get(GraduationStudent, r.gd_student_id)
        review_policy.authorize(db, stu, "submit")
        if not has_full_scope():
            me = gid.current_user_mentor(db)
            if not r.reviewer_mentor_id or not me or int(me.id) != int(r.reviewer_mentor_id):
                raise no_permission("当前账号不是该评阅任务指定评阅人")

        if file_version_id not in (None, "") and int(file_version_id) != int(r.file_version_id or 0):
            _conflict(
                "提交的 FileVersion 与评阅任务冻结版本不一致",
                expectedFileVersionId=str(r.file_version_id) if r.file_version_id else None,
                receivedFileVersionId=str(file_version_id),
            )
        _verify_frozen_snapshot(db, r, stu)

        # Exact duplicate retry remains idempotent even if its optimistic version is now old.
        if r.status == "COMPLETED" and r.score == score and (r.opinion or "") == opinion:
            return _review_row(r, stu)
        if expected_version not in (None, "") and int(expected_version) != int(r.version or 0):
            _conflict(
                "评阅任务版本已变化，请重新载入",
                expectedVersion=int(expected_version),
                currentVersion=int(r.version or 0),
            )
        if r.status not in ("ASSIGNED", "REVIEWING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交评阅")

        r.score = score
        r.opinion = opinion
        r.status = "COMPLETED"
        if not r.started_at:
            r.started_at = datetime.now(timezone.utc)
        r.reviewed_at = datetime.now(timezone.utc)
        r.version += 1
        svc._audit(
            db, "REVIEW", r.id, "提交评阅",
            detail=f"score={score};fileVersionId={r.file_version_id};sha256={r.source_sha256}",
        )
        db.commit()
        return _review_row(r, stu)


def install() -> None:
    global _INSTALLED, _PREVIOUS_REVIEW_ROW
    if _INSTALLED:
        return
    _install_model_columns()
    _PREVIOUS_REVIEW_ROW = svc._review_row
    svc._review_row = _review_row
    svc.assign_review = assign_review
    svc.submit_review = submit_review
    _INSTALLED = True
