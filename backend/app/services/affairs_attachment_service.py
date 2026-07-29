"""13A 统一业务附件（违纪/送达/申诉/党团/减免贷款回执/家校 等材料）。

分工：file 字节走 file_service（真实上传 t_file_object，含租户校验/白名单/sha256）；
本服务只登记 (biz_type,biz_id,file_id) 回链 + 授权列表 + 授权下载。
安全口径：权限 + 具体业务对象 + 数据范围 + 租户必须同时满足。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
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
        raise AppException("VALIDATION_ERROR", f"未知附件业务类型：{biz_type}",
                           details={"allowed": sorted(_BIZ_VIEW)})
    return bt


def _row(a) -> dict:
    return {"attachmentId": str(a.id), "bizType": a.biz_type, "bizId": str(a.biz_id),
            "fileId": str(a.file_id), "fileName": a.file_name or "", "note": a.note or "",
            "uploadedAt": _iso(a.created_at)}


def _require_club_scope(db, biz_id, user) -> None:
    from app.core.affairs_security import build_affairs_context, no_data_scope
    from app.models import AffairsClub

    club = db.get(AffairsClub, int(biz_id))
    if not club or club.is_deleted or club.tenant_id != _tid():
        raise not_found("社团记录不存在")
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return
    # 校级社团没有学院归属，只有全校范围角色可处理；学院角色仅能处理本院挂靠社团。
    if ctx.scope_type == "COLLEGE" and club.college_id and int(club.college_id) in ctx.college_ids:
        return
    raise no_data_scope("该社团不在您的学院或学校数据范围内")


def _require_biz_scope(db, biz_type: str, biz_id, user) -> None:
    """解析具体业务对象并执行学生/学院范围；未知映射绝不默认放行。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import (
        AffairsLeagueDev, DisciplineAppeal, DisciplineCase, FamilyContactLog,
        FeeReduction, FundingApplication, StudentLoan,
    )
    if biz_type == "CLUB":
        _require_club_scope(db, biz_id, user)
        return
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
    build_affairs_context(user, db).require_student(db, student_id)


def link_attachment(biz_type, biz_id, file_id, note, user) -> dict:
    bt = _norm_biz(biz_type)
    enforce_permission(user, _BIZ_MANAGE[bt])
    meta = file_service.get_file_meta(str(file_id), user=user)
    if not meta:
        raise not_found("文件不存在或无权访问")
    from app.models import AffairsAttachment
    with session() as db:
        _require_biz_scope(db, bt, biz_id, user)
        a = AffairsAttachment(tenant_id=_tid(), biz_type=bt, biz_id=int(biz_id),
                              file_id=int(meta["fileId"]), file_name=meta.get("fileName"),
                              note=(note or "").strip() or None)
        db.add(a)
        db.flush()
        file_service.bind_file_biz(str(meta["fileId"]), bt, str(biz_id), user=user, db=db)
        db.commit()
        db.refresh(a)
        return _row(a)


def list_attachments(biz_type, biz_id, user) -> list[dict]:
    bt = _norm_biz(biz_type)
    enforce_permission(user, _BIZ_VIEW[bt])
    from app.models import AffairsAttachment
    with session() as db:
        _require_biz_scope(db, bt, biz_id, user)
        rows = db.scalars(select(AffairsAttachment).where(
            AffairsAttachment.tenant_id == _tid(), AffairsAttachment.biz_type == bt,
            AffairsAttachment.biz_id == int(biz_id),
            AffairsAttachment.is_deleted.is_(False)).order_by(AffairsAttachment.id.desc())).all()
        return [_row(a) for a in rows]


def _load(db, attachment_id):
    from app.models import AffairsAttachment
    a = db.get(AffairsAttachment, int(attachment_id))
    if not a or a.is_deleted or a.tenant_id != _tid():
        raise not_found("附件不存在")
    return a


def download_attachment(attachment_id, user):
    bt, fid, fname = "UNKNOWN", "", ""
    detail = {"attachmentId": str(attachment_id)}
    try:
        with session() as db:
            a = _load(db, attachment_id)
            _require_biz_scope(db, a.biz_type, a.biz_id, user)
            bt, fid, fname = a.biz_type, str(a.file_id), a.file_name
        detail.update({"fileId": fid, "bizType": bt, "fileName": fname})
        enforce_permission(user, _BIZ_VIEW.get(bt, "__UNKNOWN_ATTACHMENT_PERMISSION__"))
        resolved = file_service.resolve_download(fid, user=user)
        detail["hit"] = bool(resolved)
        audit_insert("SENSITIVE_EXPORT", f"affairs_attachment:{bt}", detail,
                     "SUCCESS" if resolved else "NOT_FOUND")
        return resolved
    except AppException as exc:
        detail["errorCode"] = exc.code
        audit_insert("SENSITIVE_EXPORT", f"affairs_attachment:{bt}", detail,
                     "DENIED" if exc.code in {"NO_PERMISSION", "NO_DATA_SCOPE"} else "NOT_FOUND")
        raise
    except Exception as exc:
        detail["errorType"] = type(exc).__name__
        audit_insert("SENSITIVE_EXPORT", f"affairs_attachment:{bt}", detail, "FAILED")
        raise
