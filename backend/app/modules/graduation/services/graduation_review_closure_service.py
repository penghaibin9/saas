"""W7.1/W7.2 formal graduation review closure.

GraduationReview remains the status authority. This service adds an exact FileVersion
snapshot and append-only feedback evidence without introducing a second review task.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.exceptions import AppException, no_permission, not_found
from app.models import GraduationFinal, GraduationReview, GraduationStudent
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.policies import review_policy
from app.modules.graduation.services import graduation_review_feedback_service as feedback
from app.modules.graduation.services import graduation_review_service as legacy
from app.modules.graduation.services.graduation_scope_service import has_full_scope
from app.services.db_service import _tid, session
from app.services.file_scan_constants import READY_SCAN_STATES


def _snapshot(db, review_id: int) -> dict:
    row = db.execute(text(
        "SELECT material_id,file_version_id,source_sha256,started_at FROM t_gd_review "
        "WHERE tenant_id=:tenant_id AND id=:review_id AND is_deleted=0"
    ), {"tenant_id": int(_tid()), "review_id": int(review_id)}).mappings().first()
    return dict(row) if row else {}


def _write_snapshot(db, review_id: int, *, material_id: int, file_version_id: int, source_sha256: str) -> None:
    db.execute(text(
        "UPDATE t_gd_review SET material_id=:material_id,file_version_id=:file_version_id,source_sha256=:source_sha256 "
        "WHERE tenant_id=:tenant_id AND id=:review_id AND is_deleted=0"
    ), {
        "material_id": int(material_id), "file_version_id": int(file_version_id),
        "source_sha256": str(source_sha256), "tenant_id": int(_tid()), "review_id": int(review_id),
    })


def _row(db, review: GraduationReview, student: GraduationStudent | None = None) -> dict:
    result = legacy._review_row(review, student)  # existing public contract
    snap = _snapshot(db, int(review.id))
    result.update({
        "version": int(review.version or 0),
        "materialId": str(snap.get("material_id")) if snap.get("material_id") is not None else None,
        "fileVersionId": str(snap.get("file_version_id")) if snap.get("file_version_id") is not None else None,
        "sourceSha256": snap.get("source_sha256"),
        "startedAt": snap.get("started_at").isoformat() if hasattr(snap.get("started_at"), "isoformat") else snap.get("started_at"),
    })
    return result


def _student(db, gd_student_id: int) -> GraduationStudent:
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.id == int(gd_student_id),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.is_deleted.is_(False),
    )).first()
    if not student:
        raise not_found("毕设学生不存在或不在当前租户")
    return student


def _canonical_evidence(db, student: GraduationStudent) -> tuple[GraduationFinal, GraduationStudentMaterial, FileVersion, FileObject]:
    final = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == int(student.id),
        GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
        GraduationFinal.is_deleted.is_(False),
    ).order_by(GraduationFinal.id.desc()).with_for_update()).first()
    if not final:
        raise AppException("DATA_CONFLICT", "请先完成并通过正式定稿，再分配评阅任务")
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.material_code == "THESIS_FINAL",
        GraduationStudentMaterial.source_record_type == "FINAL",
        GraduationStudentMaterial.source_record_id == str(final.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if not material or material.current_version_id is None or material.asset_id is None:
        raise AppException("REVIEW_TARGET_VERSION_MISSING", "正式评阅定稿尚未绑定权威 FileVersion")
    version = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id),
        FileVersion.asset_id == int(material.asset_id), FileVersion.is_current.is_(True),
        FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if not version or str(version.status or "").upper() != "APPROVED":
        raise AppException("REVIEW_TARGET_VERSION_MISSING", "正式评阅只能冻结已审核通过的定稿 FileVersion")
    file_object = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(version.file_object_id),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if (
        not file_object
        or str(file_object.status or "").upper() != "AVAILABLE"
        or str(file_object.scan_status or "").upper() not in READY_SCAN_STATES
    ):
        raise AppException("FILE_NOT_READY", "正式评阅文件未通过公共文件中心安全门禁")
    if not str(file_object.sha256 or "").strip():
        raise AppException("FILE_HASH_MISSING", "正式评阅文件缺少 SHA-256 证据")
    return final, material, version, file_object


def _assert_reviewer_and_sod(db, review: GraduationReview, student: GraduationStudent) -> None:
    from app.modules.graduation.services import graduation_identity as gid

    if gid.sod_conflict_with_advisor(
        db,
        student,
        reviewer_mentor_id=review.reviewer_mentor_id,
        reviewer_name=review.reviewer_name,
    ):
        raise AppException("VALIDATION_ERROR", "评阅人与当前指导教师发生 SoD 冲突，禁止提交")
    if has_full_scope():
        return
    me = gid.current_user_mentor(db)
    if not review.reviewer_mentor_id or not me or int(me.id) != int(review.reviewer_mentor_id):
        raise no_permission("仅稳定ID匹配的被指派评阅人可提交本任务")


def _prior_matches_request(prior: dict, review: GraduationReview, *, file_version_id: int,
                           opinion: str, categories=None, issues=None) -> bool:
    public = feedback.public_feedback(prior) or {}
    return (
        public.get("stage") == "FORMAL"
        and public.get("sourceRecordId") == str(review.id)
        and public.get("reviewId") == str(review.id)
        and public.get("fileVersionId") == str(file_version_id)
        and public.get("result") == "COMPLETED"
        and public.get("summary") == str(opinion)
        and public.get("categories") == list(categories or [])
        and public.get("issues") == list(issues or [])
    )


def assign_review(gd_student_id, reviewer_name: str | None = None, gd_final_id=None,
                  reviewer_mentor_id=None) -> dict:
    with session() as db:
        from app.modules.graduation.services import graduation_identity as gid

        student = legacy._stu(db, gd_student_id)
        review_policy.authorize(db, student, "assign")
        reviewer = str(reviewer_name or "").strip()
        mentor_id = None
        if reviewer_mentor_id not in (None, ""):
            mentor = gid.require_mentor(db, reviewer_mentor_id)
            mentor_id = int(mentor.id)
            reviewer = str(mentor.teacher_name or "").strip()
        if not reviewer or not mentor_id:
            raise AppException("VALIDATION_ERROR", "评阅任务必须选择已绑定导师台账的评阅人")
        if gid.sod_conflict_with_advisor(db, student, reviewer_mentor_id=mentor_id, reviewer_name=reviewer):
            raise AppException("VALIDATION_ERROR", "评阅人不得是该生指导教师（SoD 冲突）")

        final, material, version, file_object = _canonical_evidence(db, student)
        existing = db.scalars(select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(), GraduationReview.gd_student_id == int(student.id),
            GraduationReview.gd_final_id == int(final.id), GraduationReview.reviewer_mentor_id == mentor_id,
            GraduationReview.status.in_(("ASSIGNED", "REVIEWING", "RETURNED")),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            snap = _snapshot(db, int(existing.id))
            if not snap.get("file_version_id"):
                _write_snapshot(
                    db,
                    int(existing.id),
                    material_id=int(material.id),
                    file_version_id=int(version.id),
                    source_sha256=str(file_object.sha256),
                )
                legacy._audit(
                    db,
                    "REVIEW",
                    existing.id,
                    "补齐评阅冻结证据",
                    detail=f"fileVersionId={version.id};sha256={file_object.sha256}",
                )
                db.commit()
            return _row(db, existing, student)

        operator, _ = legacy._op()
        review = GraduationReview(
            tenant_id=_tid(), gd_student_id=int(student.id), gd_final_id=int(final.id),
            reviewer_name=reviewer, reviewer_mentor_id=mentor_id, status="ASSIGNED",
            assigned_by=operator, assigned_at=datetime.now(timezone.utc),
        )
        db.add(review)
        db.flush()
        _write_snapshot(
            db,
            int(review.id),
            material_id=int(material.id),
            file_version_id=int(version.id),
            source_sha256=str(file_object.sha256),
        )
        legacy._audit(
            db,
            "REVIEW",
            review.id,
            "分配评阅任务",
            detail=f"{student.name}→{reviewer};fileVersionId={version.id};sha256={file_object.sha256}",
        )
        db.commit()
        return _row(db, review, student)


def submit_review(rid, score: int, opinion: str, *, expected_version: int | None,
                  file_version_id: int | None, categories=None, issues=None,
                  idempotency_key: str | None = None) -> dict:
    if expected_version is None or file_version_id is None:
        raise AppException("VALIDATION_ERROR", "expectedVersion 和 fileVersionId 不能为空")
    with session() as db:
        review = db.scalars(select(GraduationReview).where(
            GraduationReview.id == int(rid), GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not review:
            raise not_found("评阅任务不存在")
        student = _student(db, int(review.gd_student_id))
        review_policy.authorize(db, student, "submit")
        _assert_reviewer_and_sod(db, review, student)

        snap = _snapshot(db, int(review.id))
        if not snap.get("material_id") or not snap.get("file_version_id") or not snap.get("source_sha256"):
            raise AppException("REVIEW_TARGET_VERSION_MISSING", "评阅任务缺少冻结版本证据，请重新分配或治理历史任务")
        if int(file_version_id) != int(snap["file_version_id"]):
            raise AppException("REVIEW_TARGET_VERSION_CHANGED", "提交的 FileVersion 与评阅任务冻结版本不一致")

        supplied_key = str(idempotency_key or "").strip() or feedback.make_idempotency_key(
            stage="FORMAL", source_record_id=int(review.id), file_version_id=int(file_version_id),
            result="COMPLETED", summary=opinion, categories=categories, issues=issues,
        )
        prior = feedback.find_by_idempotency(db, supplied_key)
        if prior:
            if review.status == "COMPLETED" and _prior_matches_request(
                prior,
                review,
                file_version_id=int(file_version_id),
                opinion=opinion,
                categories=categories,
                issues=issues,
            ):
                return _row(db, review, student)
            raise AppException("DATA_CONFLICT", "idempotencyKey 已被其他评阅证据占用，请重新载入任务")

        if int(review.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "评阅任务版本已变化，请重新载入后继续")
        if review.status not in ("ASSIGNED", "REVIEWING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交评阅")

        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.id == int(review.gd_final_id or 0),
            GraduationFinal.gd_student_id == int(student.id),
            GraduationFinal.final_type == "定稿",
            GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not final:
            raise AppException("REVIEW_TARGET_VERSION_CHANGED", "评阅绑定定稿已不再是当前可评阅的已通过定稿")

        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.id == int(snap["material_id"]),
            GraduationStudentMaterial.batch_id == int(student.batch_id),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.material_code == "THESIS_FINAL",
            GraduationStudentMaterial.source_record_type == "FINAL",
            GraduationStudentMaterial.source_record_id == str(final.id),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if (
            not material
            or material.asset_id is None
            or int(material.current_version_id or 0) != int(snap["file_version_id"])
        ):
            raise AppException("REVIEW_TARGET_VERSION_CHANGED", "学生材料 canonical FileVersion 已变化，请重新载入任务")
        version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(),
            FileVersion.id == int(snap["file_version_id"]),
            FileVersion.asset_id == int(material.asset_id),
            FileVersion.is_current.is_(True),
            FileVersion.is_deleted.is_(False),
        ).with_for_update()).first()
        file_object = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id == (int(version.file_object_id) if version else -1),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not version or str(version.status or "").upper() != "APPROVED" or not file_object:
            raise AppException("FILE_NOT_READY", "冻结 FileVersion 当前不可评阅")
        if (
            str(file_object.status or "").upper() != "AVAILABLE"
            or str(file_object.scan_status or "").upper() not in READY_SCAN_STATES
        ):
            raise AppException("FILE_NOT_READY", "冻结文件安全状态发生变化，暂不能提交评阅")
        if str(file_object.sha256 or "").lower() != str(snap["source_sha256"]).lower():
            raise AppException("REVIEW_TARGET_VERSION_CHANGED", "冻结文件 SHA-256 证据发生变化")

        now = datetime.now(timezone.utc)
        if not snap.get("started_at"):
            db.execute(text(
                "UPDATE t_gd_review SET started_at=:started_at WHERE tenant_id=:tenant_id AND id=:review_id"
            ), {"started_at": now.replace(tzinfo=None), "tenant_id": int(_tid()), "review_id": int(review.id)})
        review.score = int(score)
        review.opinion = str(opinion)
        review.status = "COMPLETED"
        review.reviewed_at = now
        review.version = int(review.version or 0) + 1
        feedback.append_feedback_in_session(
            db,
            batch_id=student.batch_id,
            gd_student_id=int(student.id),
            stage="FORMAL",
            source_record_id=int(review.id),
            review_id=int(review.id),
            material_id=int(material.id),
            file_version_id=int(version.id),
            source_sha256=str(snap["source_sha256"]),
            result="COMPLETED",
            summary=str(opinion),
            categories=categories,
            issues=issues,
            reviewer_mentor_id=int(review.reviewer_mentor_id) if review.reviewer_mentor_id else None,
            idempotency_key=supplied_key,
        )
        legacy._audit(
            db,
            "REVIEW",
            review.id,
            "提交评阅",
            detail=f"score={score};fileVersionId={version.id};sha256={snap['source_sha256']}",
        )
        db.commit()
        return _row(db, review, student)


def return_review(rid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        review = db.scalars(select(GraduationReview).where(
            GraduationReview.id == int(rid), GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not review:
            raise not_found("评阅任务不存在")
        student = _student(db, int(review.gd_student_id))
        review_policy.authorize(db, student, "return")
        if review.status == "RETURNED":
            return _row(db, review, student)
        if review.status != "COMPLETED":
            raise AppException("DATA_CONFLICT", "仅「已完成」评阅可退回重评")
        review.status = "RETURNED"
        review.version = int(review.version or 0) + 1
        legacy._audit(db, "REVIEW", review.id, "退回重评", detail=reason.strip())
        db.commit()
        return _row(db, review, student)


def list_reviews(*args, **kwargs):
    return legacy.list_reviews(*args, **kwargs)


def review_stats(*args, **kwargs):
    return legacy.review_stats(*args, **kwargs)
