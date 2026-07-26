"""13A 统一业务附件（违纪/送达/申诉/党团/减免贷款回执/家校 等材料）。

分工：file 字节走 file_service（真实上传 t_file_object，含租户校验/白名单/sha256）；
本服务只登记 (biz_type,biz_id,file_id) 回链 + 授权列表 + 授权下载。
安全口径：
- link/上传关联 → 需该 biz 的**管理权限**（越权 403 NO_PERMISSION）；
- list/download → 需该 biz 的**查看权限**；列表只回展示名+id，不回路径/明文；
- 每次下载写 t_security_audit_log(SENSITIVE_EXPORT)（敏感材料下载留痕，绝不阻塞主流程）；
- 跨租户：file_service.get_file_meta / 本表查询均按当前租户收敛，跨租户不可达。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.services import file_service
from app.services.db_service import _iso, _tid, audit_insert, session

# biz_type → 查看权限（下载/列表门禁）
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
# biz_type → 管理权限（上传/关联门禁）
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


def _require_biz_scope(db, biz_type: str, biz_id, user) -> None:
    """Resolve the business owner and enforce the caller's student scope."""
    from app.core.affairs_security import build_affairs_context
    from app.models import (
        AffairsLeagueDev, DisciplineAppeal, DisciplineCase, FamilyContactLog,
        FeeReduction, FundingApplication, StudentLoan,
    )
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
        return
    model, student_attr = mapping
    obj = db.get(model, int(biz_id))
    if not obj or getattr(obj, "is_deleted", False) or obj.tenant_id != _tid():
        raise not_found("业务记录不存在")
    student_id = getattr(obj, student_attr, None)
    if not student_id:
        raise not_found("业务记录未关联学生")
    build_affairs_context(user, db).require_student(db, student_id)


def link_attachment(biz_type, biz_id, file_id, note, user) -> dict:
    """把已上传文件(file_id)关联到业务记录。需 biz 管理权限；file 必须属当前租户。"""
    bt = _norm_biz(biz_type)
    enforce_permission(user, _BIZ_MANAGE[bt])
    meta = file_service.get_file_meta(str(file_id), user=user)          # 租户+对象级授权
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
    """列业务记录附件（脱敏：只回展示名+id，不回路径）。需 biz 查看权限。"""
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
    """授权下载：校验 biz 查看权限 → 写 SENSITIVE_EXPORT 审计 → 返回 (磁盘路径, 文件名)。
    未授权在 enforce_permission 抛 403 前即拦截；文件丢失返回 None 由端点转 404。"""
    bt, fid, fname = "UNKNOWN", "", ""
    detail = {"attachmentId": str(attachment_id)}
    try:
        with session() as db:
            a = _load(db, attachment_id)
            _require_biz_scope(db, a.biz_type, a.biz_id, user)
            bt, fid, fname = a.biz_type, str(a.file_id), a.file_name
        detail.update({"fileId": fid, "bizType": bt, "fileName": fname})
        enforce_permission(user, _BIZ_VIEW.get(bt, "studentAffairs.dashboard.view"))
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
