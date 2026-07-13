"""13A-D 学生干部与组织（06 卡）：学生组织 + 任职；干部履历 union 组织任职 + 班级班干部。

班级班干部复用既有 AffairsClassCadre（t_affairs_class_cadre）。留痕 AffairsAuditTrail(biz_type=ORG)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

ORG_TYPES = ("STUDENT_UNION", "SOCIETY_FEDERATION", "SELF_GOV", "OTHER")
L_ORG_TYPE = {"STUDENT_UNION": "学生会", "SOCIETY_FEDERATION": "社团联合会",
              "SELF_GOV": "自律委员会", "OTHER": "其他组织"}
L_LEVEL = {"SCHOOL": "校级", "COLLEGE": "院级"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), u.get("userId")


def _uid_int(user):
    try:
        return int((user or {}).get("userId") or 0) or None
    except (TypeError, ValueError):
        return None


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, _ = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="ORG",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _load(db, org_id):
    from app.models import AffairsStudentOrg
    o = db.get(AffairsStudentOrg, int(org_id))
    if not o or o.is_deleted or o.tenant_id != _tid():
        raise not_found("学生组织不存在")
    return o


def _org_row(o) -> dict:
    return {"orgId": str(o.id), "orgName": o.org_name, "orgType": o.org_type,
            "orgTypeLabel": L_ORG_TYPE.get(o.org_type, o.org_type), "level": o.level,
            "levelLabel": L_LEVEL.get(o.level, o.level), "collegeId": str(o.college_id or ""),
            "advisorName": o.advisor_name or "", "status": o.status, "version": o.version}


def list_orgs(user, level=None, status=None, page=1, page_size=50):
    from app.models import AffairsStudentOrg
    with session() as db:
        conds = [AffairsStudentOrg.tenant_id == _tid(), AffairsStudentOrg.is_deleted.is_(False)]
        if level:
            conds.append(AffairsStudentOrg.level == level)
        if status:
            conds.append(AffairsStudentOrg.status == status)
        rows = db.scalars(select(AffairsStudentOrg).where(*conds).order_by(
            AffairsStudentOrg.id.desc())).all()
        out = [_org_row(o) for o in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def create_org(body, user) -> dict:
    from app.models import AffairsStudentOrg
    name = (getattr(body, "orgName", "") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "组织名称必填")
    otype = getattr(body, "orgType", "STUDENT_UNION") or "STUDENT_UNION"
    if otype not in ORG_TYPES:
        raise AppException("VALIDATION_ERROR", "组织类型非法")
    with session() as db:
        dup = db.scalars(select(AffairsStudentOrg).where(
            AffairsStudentOrg.tenant_id == _tid(), AffairsStudentOrg.org_name == name,
            AffairsStudentOrg.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "同名组织已存在")
        o = AffairsStudentOrg(tenant_id=_tid(), org_name=name, org_type=otype,
                              level=getattr(body, "level", "SCHOOL") or "SCHOOL",
                              college_id=getattr(body, "collegeId", None),
                              advisor_name=getattr(body, "advisorName", None),
                              status="ACTIVE", created_by=_uid_int(user))
        db.add(o); db.flush()
        _audit(db, o.id, "ORG_CREATE", name)
        db.commit(); db.refresh(o)
        return _org_row(o)


def _pos_row(p, s=None, org=None) -> dict:
    return {"positionId": str(p.id), "orgId": str(p.org_id),
            "orgName": org.org_name if org else "", "studentId": str(p.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "position": p.position, "termCode": p.term_code or "",
            "status": p.status, "appointedAt": _iso(p.appointed_at), "removedAt": _iso(p.removed_at)}


def list_positions(org_id, user):
    from app.models import AffairsOrgPosition, StudentProfile
    with session() as db:
        org = _load(db, org_id)
        rows = db.scalars(select(AffairsOrgPosition).where(
            AffairsOrgPosition.tenant_id == _tid(), AffairsOrgPosition.org_id == int(org_id),
            AffairsOrgPosition.status == "ACTIVE", AffairsOrgPosition.is_deleted.is_(False))
            .order_by(AffairsOrgPosition.id.desc())).all()
        return [_pos_row(p, db.get(StudentProfile, int(p.student_id)) if p.student_id else None, org)
                for p in rows]


def appoint(org_id, body, user) -> dict:
    from app.models import AffairsOrgPosition, StudentProfile
    sid = int(getattr(body, "studentId", 0) or 0)
    position = (getattr(body, "position", "") or "").strip()
    if not position:
        raise AppException("VALIDATION_ERROR", "职务必填")
    with session() as db:
        org = _load(db, org_id)
        if org.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "仅在运营组织可任命")
        s = db.get(StudentProfile, sid) if sid else None
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        dup = db.scalars(select(AffairsOrgPosition).where(
            AffairsOrgPosition.tenant_id == _tid(), AffairsOrgPosition.org_id == int(org_id),
            AffairsOrgPosition.student_id == sid, AffairsOrgPosition.position == position,
            AffairsOrgPosition.status == "ACTIVE", AffairsOrgPosition.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生已任此职务")
        p = AffairsOrgPosition(tenant_id=_tid(), org_id=int(org_id), student_id=sid, position=position,
                               term_code=getattr(body, "termCode", None), appointed_at=datetime.utcnow(),
                               status="ACTIVE", created_by=_uid_int(user))
        db.add(p); db.flush()
        _audit(db, org_id, "ORG_APPOINT", f"student={sid} {position}")
        db.commit(); db.refresh(p)
        return _pos_row(p, s, org)


def dismiss(position_id, user) -> dict:
    from app.models import AffairsOrgPosition
    with session() as db:
        p = db.get(AffairsOrgPosition, int(position_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("任职记录不存在")
        if p.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "该任职已卸任")
        p.status, p.removed_at, p.version = "REMOVED", datetime.utcnow(), p.version + 1
        _audit(db, p.org_id, "ORG_DISMISS", f"position={position_id}")
        db.commit()
        return {"positionId": str(position_id), "status": "REMOVED"}


def student_resume(student_id, user):
    """干部履历：union 组织任职（org_position）+ 班级班干部（class_cadre）。倒序。"""
    from app.models import (AffairsClassCadre, AffairsOrgPosition, AffairsStudentOrg,
                            SchoolClass)
    sid = int(student_id)
    with session() as db:
        out = []
        for p in db.scalars(select(AffairsOrgPosition).where(
                AffairsOrgPosition.tenant_id == _tid(), AffairsOrgPosition.student_id == sid,
                AffairsOrgPosition.is_deleted.is_(False))).all():
            org = db.get(AffairsStudentOrg, int(p.org_id))
            out.append({"source": "ORG", "scope": org.org_name if org else "组织",
                        "position": p.position, "termCode": p.term_code or "",
                        "status": p.status, "appointedAt": _iso(p.appointed_at),
                        "removedAt": _iso(p.removed_at)})
        for c in db.scalars(select(AffairsClassCadre).where(
                AffairsClassCadre.tenant_id == _tid(), AffairsClassCadre.student_id == sid,
                AffairsClassCadre.is_deleted.is_(False))).all():
            k = db.get(SchoolClass, int(c.class_id)) if getattr(c, "class_id", None) else None
            out.append({"source": "CLASS", "scope": (k.class_name if k else "班级"),
                        "position": c.position, "termCode": getattr(c, "term_code", "") or "",
                        "status": c.status, "appointedAt": _iso(getattr(c, "appointed_at", None)),
                        "removedAt": _iso(getattr(c, "removed_at", None))})
        out.sort(key=lambda x: x["appointedAt"] or "", reverse=True)
        return out
