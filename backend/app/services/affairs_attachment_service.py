"""学工旧附件 API 的公共版本 adapter。

FileObject/FileAsset/FileVersion/FileBinding 是文件真相源；AffairsAttachment 仅保留旧接口
编号、展示名和业务回链。安全口径始终是权限 + 具体业务对象 + 数据范围 + 租户。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.models.file import FileObject
from app.services import file_service
from app.services.db_service import _iso, _tid, audit_insert, session

_BIZ_VIEW = {
    "DISCIPLINE": "studentAffairs.discipline.view",
    "DISCIPLINE_APPEAL": "studentAffairs.discipline.view",
    "LEAGUE": "studentAffairs.league.view",
    "CLUB": "studentAffairs.club.view",
    "FUNDING": "studentAffairs.funding.view",
    "REDUCTION": "studentAffairs.funding.view",
    "LOAN": "studentAffairs.funding.view",
    "HOME_SCHOOL": "studentAffairs.homeSchool.view",
}
_BIZ_MANAGE = {
    "DISCIPLINE": "studentAffairs.discipline.create",
    "DISCIPLINE_APPEAL": "studentAffairs.discipline.appeal.create",
    "LEAGUE": "studentAffairs.league.manage",
    "CLUB": "studentAffairs.club.manage",
    "FUNDING": "studentAffairs.funding.project.manage",
    "REDUCTION": "studentAffairs.funding.reduction.manage",
    "LOAN": "studentAffairs.funding.loan.manage",
    "HOME_SCHOOL": "studentAffairs.homeSchool.record.create",
}


def _norm_biz(biz_type: str) -> str:
    bt = (biz_type or "").strip().upper()
    if bt not in _BIZ_VIEW:
        raise AppException(
            "VALIDATION_ERROR", f"未知附件业务类型：{biz_type}",
            details={"allowed": sorted(_BIZ_VIEW)},
        )
    return bt


def _row(attachment) -> dict:
    return {
        "attachmentId": str(attachment.id),
        "bizType": attachment.biz_type,
        "bizId": str(attachment.biz_id),
        "fileId": str(attachment.file_id),
        "fileName": attachment.file_name or "",
        "note": attachment.note or "",
        "assetId": str(attachment.asset_id or ""),
        "fileVersionId": str(attachment.file_version_id or ""),
        "bindingId": str(attachment.binding_id or ""),
        "sensitivityLevel": attachment.sensitivity_level or "SENSITIVE",
        "uploadedAt": _iso(attachment.created_at),
    }


def _require_club_scope(db, biz_id, user) -> None:
    from app.core.affairs_security import build_affairs_context, no_data_scope
    from app.models import AffairsClub

    club = db.get(AffairsClub, int(biz_id))
    if not club or club.is_deleted or club.tenant_id != _tid():
        raise not_found("社团记录不存在")
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return
    if ctx.scope_type == "COLLEGE" and club.college_id and int(club.college_id) in ctx.college_ids:
        return
    raise no_data_scope("该社团不在您的学院或学校数据范围内")


def resolve_attachment_student(db, biz_type: str, biz_id) -> int:
    """解析附件的学生主体；旧 CLUB 附件优先回链社长/发起人。"""
    from app.models import (
        AffairsClub,
        AffairsLeagueDev,
        DisciplineAppeal,
        DisciplineCase,
        FamilyContactLog,
        FeeReduction,
        FundingApplication,
        StudentLoan,
    )

    if biz_type == "CLUB":
        club = db.get(AffairsClub, int(biz_id))
        if not club or club.is_deleted or club.tenant_id != _tid():
            raise not_found("社团记录不存在")
        student_id = club.president_student_id or club.founder_student_id
        if not student_id:
            raise not_found("社团记录未关联学生主体")
        return int(student_id)
    mappings = {
        "DISCIPLINE": (DisciplineCase, "student_id"),
        "DISCIPLINE_APPEAL": (DisciplineAppeal, "student_id"),
        "LEAGUE": (AffairsLeagueDev, "student_id"),
        "FUNDING": (FundingApplication, "student_id"),
        "REDUCTION": (FeeReduction, "student_id"),
        "LOAN": (StudentLoan, "student_id"),
        "HOME_SCHOOL": (FamilyContactLog, "student_id"),
    }
    mapping = mappings.get(biz_type)
    if mapping is None:
        raise AppException("VALIDATION_ERROR", "附件业务类型尚未配置对象范围校验")
    model, student_attr = mapping
    obj = db.get(model, int(biz_id))
    if not obj or getattr(obj, "is_deleted", False) or obj.tenant_id != _tid():
        raise not_found("业务记录不存在")
    student_id = getattr(obj, student_attr, None)
    if not student_id:
        raise not_found("业务记录未关联学生")
    return int(student_id)


def _require_biz_scope(db, biz_type: str, biz_id, user) -> None:
    from app.core.affairs_security import build_affairs_context

    if biz_type == "CLUB":
        _require_club_scope(db, biz_id, user)
        return
    student_id = resolve_attachment_student(db, biz_type, biz_id)
    build_affairs_context(user, db).require_student(db, student_id)


def link_attachment(biz_type, biz_id, file_id, note, user) -> dict:
    bt = _norm_biz(biz_type)
    enforce_permission(user, _BIZ_MANAGE[bt])
    meta = file_service.get_file_meta(str(file_id), user=user)
    if not meta:
        raise not_found("文件不存在或无权访问")
    from app.models import AffairsAttachment
    from app.modules.student_affairs.services import affairs_material_center_service as center

    with session() as db:
        _require_biz_scope(db, bt, biz_id, user)
        student_id = resolve_attachment_student(db, bt, biz_id)
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(meta["fileId"]),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise not_found("文件不存在或无权访问")
        sensitivity, material_scope = center.classify_sensitivity(bt, "", meta.get("fileName") or "")
        attachment = AffairsAttachment(
            tenant_id=_tid(), biz_type=bt, biz_id=int(biz_id),
            file_id=int(meta["fileId"]), file_name=meta.get("fileName"),
            note=(note or "").strip() or None,
            sensitivity_level=sensitivity, source_channel="LEGACY_ADAPTER",
        )
        db.add(attachment)
        db.flush()
        center.link_legacy_attachment(
            db, attachment, file_obj, student_id=student_id, user=user,
            sensitivity_level=sensitivity, material_scope=material_scope,
        )
        db.commit()
        db.refresh(attachment)
        return _row(attachment)


def list_attachments(biz_type, biz_id, user) -> list[dict]:
    bt = _norm_biz(biz_type)
    enforce_permission(user, _BIZ_VIEW[bt])
    from app.models import AffairsAttachment

    with session() as db:
        _require_biz_scope(db, bt, biz_id, user)
        rows = db.scalars(select(AffairsAttachment).where(
            AffairsAttachment.tenant_id == _tid(), AffairsAttachment.biz_type == bt,
            AffairsAttachment.biz_id == int(biz_id), AffairsAttachment.is_deleted.is_(False),
        ).order_by(AffairsAttachment.id.desc())).all()
        return [_row(attachment) for attachment in rows]


def _load(db, attachment_id):
    from app.models import AffairsAttachment

    attachment = db.get(AffairsAttachment, int(attachment_id))
    if not attachment or attachment.is_deleted or attachment.tenant_id != _tid():
        raise not_found("附件不存在")
    return attachment


def download_attachment(attachment_id, user):
    bt, file_id, file_name = "UNKNOWN", "", ""
    detail = {"attachmentId": str(attachment_id)}
    try:
        with session() as db:
            attachment = _load(db, attachment_id)
            _require_biz_scope(db, attachment.biz_type, attachment.biz_id, user)
            bt, file_id, file_name = attachment.biz_type, str(attachment.file_id), attachment.file_name
        detail.update({"fileId": file_id, "bizType": bt, "fileName": file_name})
        enforce_permission(user, _BIZ_VIEW.get(bt, "__UNKNOWN_ATTACHMENT_PERMISSION__"))
        resolved = file_service.resolve_download(file_id, user=user)
        detail["hit"] = bool(resolved)
        audit_insert(
            "SENSITIVE_EXPORT", f"affairs_attachment:{bt}", detail,
            "SUCCESS" if resolved else "NOT_FOUND",
        )
        return resolved
    except AppException as exc:
        detail["errorCode"] = exc.code
        audit_insert(
            "SENSITIVE_EXPORT", f"affairs_attachment:{bt}", detail,
            "DENIED" if exc.code in {"NO_PERMISSION", "NO_DATA_SCOPE"} else "NOT_FOUND",
        )
        raise
    except Exception as exc:
        detail["errorType"] = type(exc).__name__
        audit_insert("SENSITIVE_EXPORT", f"affairs_attachment:{bt}", detail, "FAILED")
        raise
