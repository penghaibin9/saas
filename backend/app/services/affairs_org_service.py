"""13A-D 学生干部与组织（06 卡）：学生组织 + 任职；干部履历 union 组织任职 + 班级班干部。

班级班干部复用既有 AffairsClassCadre（t_affairs_class_cadre）。留痕 AffairsAuditTrail(biz_type=ORG)。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.services.db_service import _iso, _tid, session
from app.core import affairs_security
from app.services.affairs_organization_scope import organization_condition, require_organization, student_condition

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


def _load(db, org_id, user):
    from app.models import AffairsStudentOrg
    o = db.get(AffairsStudentOrg, int(org_id))
    if not o or o.is_deleted or o.tenant_id != _tid():
        raise not_found("学生组织不存在")
    require_organization(db, user, o.college_id, level=o.level)
    return o


def _org_row(o) -> dict:
    return {"orgId": str(o.id), "orgName": o.org_name, "orgType": o.org_type,
            "orgTypeLabel": L_ORG_TYPE.get(o.org_type, o.org_type), "level": o.level,
            "levelLabel": L_LEVEL.get(o.level, o.level), "collegeId": str(o.college_id or ""),
            "advisorName": o.advisor_name or "", "status": o.status, "version": o.version}


def list_orgs(user, level=None, status=None, page=1, page_size=50):
    from app.models import AffairsStudentOrg
    with session() as db:
        conds = [AffairsStudentOrg.tenant_id == _tid(), AffairsStudentOrg.is_deleted.is_(False),
                 organization_condition(db, user, AffairsStudentOrg)]
        if level:
            conds.append(AffairsStudentOrg.level == level)
        if status:
            conds.append(AffairsStudentOrg.status == status)
        page, page_size = max(1, int(page)), max(1, min(200, int(page_size)))
        total = int(db.scalar(select(func.count()).select_from(AffairsStudentOrg).where(*conds)) or 0)
        rows = db.scalars(select(AffairsStudentOrg).where(*conds).order_by(
            AffairsStudentOrg.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return [_org_row(o) for o in rows], total


def create_org(body, user) -> dict:
    from app.models import AffairsStudentOrg
    name = (getattr(body, "orgName", "") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "组织名称必填")
    otype = getattr(body, "orgType", "STUDENT_UNION") or "STUDENT_UNION"
    if otype not in ORG_TYPES:
        raise AppException("VALIDATION_ERROR", "组织类型非法")
    level = getattr(body, "level", "SCHOOL") or "SCHOOL"
    college_id = getattr(body, "collegeId", None)
    if level not in L_LEVEL or (level == "COLLEGE") != (college_id is not None):
        raise AppException("VALIDATION_ERROR", "院级组织须指定学院，校级组织不能指定学院")
    with session() as db:
        require_organization(db, user, college_id, level=level)
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
        org = _load(db, org_id, user)
        rows = db.scalars(select(AffairsOrgPosition).where(
            AffairsOrgPosition.tenant_id == _tid(), AffairsOrgPosition.org_id == int(org_id),
            AffairsOrgPosition.status == "ACTIVE", AffairsOrgPosition.is_deleted.is_(False),
            AffairsOrgPosition.student_id.in_(select(StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                student_condition(user, StudentProfile))))
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
        org = _load(db, org_id, user)
        if org.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "仅在运营组织可任命")
        s = db.get(StudentProfile, sid) if sid else None
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        affairs_security.build_affairs_context(user, db).require_student(db, sid)
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


def dismiss(position_id, user, *, expected_version=None) -> dict:
    from app.models import AffairsOrgPosition
    with session() as db:
        p = db.get(AffairsOrgPosition, int(position_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("任职记录不存在")
        _load(db, p.org_id, user)
        affairs_security.build_affairs_context(user, db).require_student(db, p.student_id)
        if p.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "该任职已卸任")
        atomic_claim_version(db, p, expected_version)
        p.status, p.removed_at, p.version = "REMOVED", datetime.utcnow(), p.version + 1
        _audit(db, p.org_id, "ORG_DISMISS", f"position={position_id}")
        db.commit()
        return {"positionId": str(position_id), "status": "REMOVED"}


def student_resume(student_id, user):
    """干部履历：组织和班级名称批量加载，避免逐任职查询。"""
    from app.models import AffairsClassCadre, AffairsOrgPosition, AffairsStudentOrg, SchoolClass

    sid = int(student_id)
    with session() as db:
        affairs_security.build_affairs_context(user, db).require_student(db, sid)
        positions = db.scalars(select(AffairsOrgPosition).where(
            AffairsOrgPosition.tenant_id == _tid(), AffairsOrgPosition.student_id == sid,
            AffairsOrgPosition.is_deleted.is_(False),
        )).all()
        cadres = db.scalars(select(AffairsClassCadre).where(
            AffairsClassCadre.tenant_id == _tid(), AffairsClassCadre.student_id == sid,
            AffairsClassCadre.is_deleted.is_(False),
        )).all()
        org_ids = {int(position.org_id) for position in positions if position.org_id}
        class_ids = {int(cadre.class_id) for cadre in cadres if getattr(cadre, "class_id", None)}
        orgs = {
            int(org.id): org
            for org in db.scalars(select(AffairsStudentOrg).where(
                AffairsStudentOrg.tenant_id == _tid(),
                AffairsStudentOrg.id.in_(org_ids) if org_ids else AffairsStudentOrg.id == -1,
                AffairsStudentOrg.is_deleted.is_(False),
            )).all()
        }
        classes = {
            int(row.id): row
            for row in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(class_ids) if class_ids else SchoolClass.id == -1,
            )).all()
        }
        out = []
        for position in positions:
            org = orgs.get(int(position.org_id)) if position.org_id else None
            out.append({
                "source": "ORG", "scope": org.org_name if org else "组织",
                "position": position.position, "termCode": position.term_code or "",
                "status": position.status, "appointedAt": _iso(position.appointed_at),
                "removedAt": _iso(position.removed_at),
            })
        for cadre in cadres:
            klass = classes.get(int(cadre.class_id)) if getattr(cadre, "class_id", None) else None
            out.append({
                "source": "CLASS", "scope": klass.class_name if klass else "班级",
                "position": cadre.position, "termCode": getattr(cadre, "term_code", "") or "",
                "status": cadre.status, "appointedAt": _iso(getattr(cadre, "appointed_at", None)),
                "removedAt": _iso(getattr(cadre, "removed_at", None)),
            })
        out.sort(key=lambda row: row["appointedAt"] or "", reverse=True)
        return out
