"""教师工作量申报服务（对标正方 教师端1.18教学工作量申报/1.19考试工作量申报）。

教师申报需增记的课时工作量(教学/监考/阅卷/出卷/其他) → 教务审核(通过/驳回) → 通过后计入
教务侧工作量统计的「申报工时」。仅供教务参考；绑定职称/薪酬系数的正式核算属人事系统，不在此实现。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_CATEGORIES = ("TEACHING", "INVIGILATE", "MARKING", "PAPER", "OTHER")
_CATEGORY_LABEL = {"TEACHING": "教学", "INVIGILATE": "监考", "MARKING": "阅卷",
                   "PAPER": "出卷", "OTHER": "其他"}


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("realName") or ctx.get("loginName") or ctx.get("userId") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _tkey():
    ctx = get_current_user_ctx() or {}
    uid = str(ctx.get("userId") or "")
    return ctx.get("loginName") or (uid[2:] if uid.startswith("u_") else uid) or uid


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_WORKLOAD_DECL", biz_id=biz_id,
                             action=action, operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可审核工作量申报")
    return ctx


def _field(body, key, default=None):
    if isinstance(body, dict):
        return body.get(key, default)
    return getattr(body, key, default)


def _dto(r):
    return {"declarationId": str(r.id), "teacherKey": r.teacher_key, "teacherName": r.teacher_name,
            "termCode": r.term_code, "category": r.category,
            "categoryLabel": _CATEGORY_LABEL.get(r.category, r.category),
            "hours": float(r.hours) if r.hours is not None else 0.0, "description": r.description,
            "status": r.status, "reviewNote": r.review_note, "reviewedBy": r.reviewed_by,
            "reviewedAt": _iso(r.reviewed_at), "createdAt": _iso(r.created_at)}


def submit(user, body) -> dict:
    """教师本人申报工作量。"""
    from app.models import AaWorkloadDeclaration
    tk = _tkey()
    if not tk:
        raise _bad("无法识别申报教师身份")
    category = (_field(body, "category") or "").upper()
    if category not in _CATEGORIES:
        raise _bad("工作量类别非法（教学/监考/阅卷/出卷/其他）")
    try:
        hours = float(_field(body, "hours") or 0)
    except (TypeError, ValueError):
        raise _bad("申报课时必须为数字")
    if hours <= 0 or hours > 9999:
        raise _bad("申报课时须大于 0")
    with session() as db:
        r = AaWorkloadDeclaration(tenant_id=_tid(), teacher_key=tk,
                                  teacher_name=(get_current_user_ctx() or {}).get("realName"),
                                  term_code=(_field(body, "termCode") or None), category=category,
                                  hours=hours, description=(_field(body, "description") or None),
                                  status="SUBMITTED")
        db.add(r)
        db.flush()
        _audit(db, r.id, "WORKLOAD_SUBMIT", f"{_CATEGORY_LABEL.get(category)} {hours}课时")
        db.commit()
        return _dto(r)


def my(user):
    """教师本人工作量申报记录。"""
    from app.models import AaWorkloadDeclaration
    with session() as db:
        rows = db.query(AaWorkloadDeclaration).filter(
            AaWorkloadDeclaration.tenant_id == _tid(), AaWorkloadDeclaration.teacher_key == _tkey(),
            AaWorkloadDeclaration.is_deleted.is_(False)).order_by(AaWorkloadDeclaration.id.desc()).all()
        return [_dto(r) for r in rows]


def list_all(user, status=None, term_code=None, page=1, page_size=50):
    """工作量申报台账（教务处口径，收敛 TENANT_ALL）。"""
    from app.models import AaWorkloadDeclaration
    with session() as db:
        _require_school(user, db)
        q = db.query(AaWorkloadDeclaration).filter(AaWorkloadDeclaration.tenant_id == _tid(),
                                                   AaWorkloadDeclaration.is_deleted.is_(False))
        if status:
            q = q.filter(AaWorkloadDeclaration.status == status)
        if term_code:
            q = q.filter(AaWorkloadDeclaration.term_code == term_code)
        rows = q.order_by(AaWorkloadDeclaration.id.desc()).all()
        return [_dto(r) for r in rows[(page - 1) * page_size: page * page_size]], len(rows)


def review(user, decl_id, action, note="") -> dict:
    """教务审核：APPROVE 通过（计入统计）/ REJECT 驳回（原因≥5字）。"""
    from app.models import AaWorkloadDeclaration
    with session() as db:
        _require_school(user, db)
        r = db.get(AaWorkloadDeclaration, int(decl_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("工作量申报不存在")
        if r.status != "SUBMITTED":
            raise _invalid("仅待审核记录可审核")
        act = (action or "").upper()
        if act == "REJECT":
            if not note or len(note.strip()) < 5:
                raise _bad("驳回原因必填且不少于 5 字")
            r.status, r.review_note = "REJECTED", note.strip()
        elif act == "APPROVE":
            r.status, r.review_note = "APPROVED", (note or "").strip() or None
        else:
            raise _bad("无效操作（APPROVE/REJECT）")
        r.reviewed_by, r.reviewed_at = _op(), datetime.utcnow()
        _audit(db, r.id, f"WORKLOAD_{act}", (note or "")[:100])
        db.commit()
        return _dto(r)


def approved_hours_by_teacher(db, term_code=None) -> dict:
    """已审核通过的申报工时按教师归集（供工作量统计并入）。返回 {teacher_key: 总课时}。"""
    from app.models import AaWorkloadDeclaration
    q = db.query(AaWorkloadDeclaration).filter(
        AaWorkloadDeclaration.tenant_id == _tid(), AaWorkloadDeclaration.status == "APPROVED",
        AaWorkloadDeclaration.is_deleted.is_(False))
    if term_code:
        q = q.filter(AaWorkloadDeclaration.term_code == term_code)
    out: dict = {}
    for r in q.all():
        out[r.teacher_key] = out.get(r.teacher_key, 0.0) + float(r.hours or 0)
    return out
