"""13A-D 社团管理（05 卡）：建社→审批→成员/任职→年审→注销。

数据留痕走 AffairsAuditTrail(biz_type=CLUB)；社团为组织级台账（非学生 PII 敏感域），
按租户可见，团委/学工处管理，college_id 供院级筛选。成员唯一活跃约束防重复入社。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.services.db_service import _iso, _tid, session

CLUB_TYPES = ("INTEREST", "ACADEMIC", "SPORTS", "ARTS", "VOLUNTEER", "PRACTICE")
MEMBER_ROLES = ("MEMBER", "DEPT_HEAD", "VICE_PRESIDENT", "PRESIDENT")
L_STATUS = {"PENDING": "待审批", "ACTIVE": "运营中", "SUSPENDED": "暂停", "DISBANDED": "已注销"}
L_TYPE = {"INTEREST": "兴趣", "ACADEMIC": "学术", "SPORTS": "体育", "ARTS": "文艺",
          "VOLUNTEER": "公益", "PRACTICE": "实践"}
L_ROLE = {"MEMBER": "成员", "DEPT_HEAD": "部长", "VICE_PRESIDENT": "副社长", "PRESIDENT": "社长"}


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
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="CLUB",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _load(db, club_id):
    from app.models import AffairsClub
    c = db.scalars(select(AffairsClub).where(
        AffairsClub.id == int(club_id), AffairsClub.tenant_id == _tid(),
        AffairsClub.is_deleted.is_(False))).first()
    if not c:
        raise not_found("社团不存在")
    return c


def _row(c) -> dict:
    return {"clubId": str(c.id), "clubName": c.club_name, "clubType": c.club_type,
            "clubTypeLabel": L_TYPE.get(c.club_type, c.club_type), "collegeId": str(c.college_id or ""),
            "advisorName": c.advisor_name or "", "presidentStudentId": str(c.president_student_id or ""),
            "memberCount": c.member_count or 0, "establishedAt": _iso(c.established_at),
            "status": c.status, "statusLabel": L_STATUS.get(c.status, c.status),
            "rejectReason": c.reject_reason or "", "version": c.version}


def list_clubs(user, status=None, club_type=None, page=1, page_size=50):
    from app.models import AffairsClub
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        base_conds = [AffairsClub.tenant_id == _tid(), AffairsClub.is_deleted.is_(False)]
        if club_type:
            base_conds.append(AffairsClub.club_type == club_type)
        conds = list(base_conds)
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            conds.append(AffairsClub.status.in_(statuses))
        status_counts = status_counts_by_column(
            db, AffairsClub, AffairsClub.status, base_conds,
        )
        page = max(1, int(page or 1))
        page_size = max(1, min(200, int(page_size or 50)))
        total = int(db.scalar(select(func.count()).select_from(AffairsClub).where(*conds)) or 0)
        rows = db.scalars(select(AffairsClub).where(*conds)
                          .order_by(AffairsClub.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        out = [_row(c) for c in rows]
        return out, total, status_counts


def create_club(body, user) -> dict:
    from app.models import AffairsClub
    name = (getattr(body, "clubName", "") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "社团名称必填")
    ctype = getattr(body, "clubType", "INTEREST") or "INTEREST"
    if ctype not in CLUB_TYPES:
        raise AppException("VALIDATION_ERROR", "社团类型非法")
    with session() as db:
        dup = db.scalars(select(AffairsClub).where(
            AffairsClub.tenant_id == _tid(), AffairsClub.club_name == name,
            AffairsClub.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "同名社团已存在")
        c = AffairsClub(tenant_id=_tid(), club_name=name, club_type=ctype,
                        college_id=getattr(body, "collegeId", None),
                        advisor_name=getattr(body, "advisorName", None),
                        president_student_id=getattr(body, "presidentStudentId", None),
                        founder_student_id=getattr(body, "founderStudentId", None),
                        member_count=0, status="PENDING", created_by=_uid_int(user))
        db.add(c); db.flush()
        _audit(db, c.id, "CLUB_CREATE", name)
        db.commit(); db.refresh(c)
        return _row(c)


def review_club(club_id, user, action="APPROVE", reason="", expected_version=None) -> dict:
    """PENDING→ACTIVE(通过)/REJECTED-态(此处并入 DISBANDED? 用 reject 保留 PENDING→驳回置 SUSPENDED)。"""
    with session() as db:
        c = _load(db, club_id)
        if c.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审批社团可审批")
        atomic_claim_version(db, c, expected_version)
        if action == "APPROVE":
            c.status, c.established_at = "ACTIVE", datetime.utcnow()
            _audit(db, c.id, "CLUB_APPROVE", "")
        else:
            if len((reason or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因至少 5 字")
            c.status, c.reject_reason = "SUSPENDED", reason.strip()
            _audit(db, c.id, "CLUB_REJECT", reason.strip())
        c.version += 1
        db.commit(); db.refresh(c)
        return _row(c)


def disband_club(club_id, user, reason="", expected_version=None) -> dict:
    with session() as db:
        c = _load(db, club_id)
        if c.status == "DISBANDED":
            raise AppException("DATA_CONFLICT", "社团已注销")
        if len((reason or "").strip()) < 5:
            raise AppException("VALIDATION_ERROR", "注销原因至少 5 字")
        atomic_claim_version(db, c, expected_version)
        c.status, c.reject_reason, c.version = "DISBANDED", reason.strip(), c.version + 1
        _audit(db, c.id, "CLUB_DISBAND", reason.strip())
        db.commit(); db.refresh(c)
        return _row(c)


def _member_row(m, s=None) -> dict:
    return {"memberId": str(m.id), "clubId": str(m.club_id), "studentId": str(m.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "role": m.role, "roleLabel": L_ROLE.get(m.role, m.role),
            "status": m.status, "joinedAt": _iso(m.joined_at)}


def list_members(club_id, user):
    from app.models import AffairsClubMember, StudentProfile
    with session() as db:
        _load(db, club_id)
        rows = db.scalars(select(AffairsClubMember).where(
            AffairsClubMember.tenant_id == _tid(), AffairsClubMember.club_id == int(club_id),
            AffairsClubMember.status == "ACTIVE", AffairsClubMember.is_deleted.is_(False))
            .order_by(AffairsClubMember.id.desc())).all()
        student_ids = {int(m.student_id) for m in rows if m.student_id}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(student_ids),
            StudentProfile.is_deleted.is_(False))).all() if student_ids else []
        student_by_id = {int(s.id): s for s in students}
        return [_member_row(m, student_by_id.get(int(m.student_id))) for m in rows]


def _sync_count(db, club_id):
    from app.models import AffairsClub, AffairsClubMember
    n = db.scalar(select(func.count()).select_from(AffairsClubMember).where(
        AffairsClubMember.tenant_id == _tid(), AffairsClubMember.club_id == int(club_id),
        AffairsClubMember.status == "ACTIVE", AffairsClubMember.is_deleted.is_(False))) or 0
    c = db.scalars(select(AffairsClub).where(
        AffairsClub.id == int(club_id), AffairsClub.tenant_id == _tid(),
        AffairsClub.is_deleted.is_(False))).first()
    if c:
        c.member_count = int(n)


def _member_scope_or_403(db, student_id, user):
    """加人写范围：非全域角色只能给本数据范围内学生办入社。"""
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该学生不在您的数据范围内")


def add_member(club_id, body, user) -> dict:
    from app.models import AffairsClubMember, StudentProfile
    sid = int(getattr(body, "studentId", 0) or 0)
    role = getattr(body, "role", "MEMBER") or "MEMBER"
    if role not in MEMBER_ROLES:
        raise AppException("VALIDATION_ERROR", "任职角色非法")
    with session() as db:
        c = _load(db, club_id)
        if c.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "仅运营中社团可增补成员")
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == sid, StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False))).first() if sid else None
        if not s:
            raise not_found("学生不存在")
        _member_scope_or_403(db, sid, user)
        dup = db.scalars(select(AffairsClubMember).where(
            AffairsClubMember.tenant_id == _tid(), AffairsClubMember.club_id == int(club_id),
            AffairsClubMember.student_id == sid, AffairsClubMember.status == "ACTIVE",
            AffairsClubMember.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生已是社团成员")
        m = AffairsClubMember(tenant_id=_tid(), club_id=int(club_id), student_id=sid, role=role,
                              joined_at=datetime.utcnow(), status="ACTIVE", created_by=_uid_int(user))
        db.add(m); db.flush()
        _sync_count(db, club_id)
        _audit(db, club_id, "CLUB_MEMBER_ADD", f"student={sid} role={role}")
        db.commit(); db.refresh(m)
        return _member_row(m, s)


def remove_member(member_id, user) -> dict:
    from app.models import AffairsClubMember
    with session() as db:
        m = db.scalars(select(AffairsClubMember).where(
            AffairsClubMember.id == int(member_id), AffairsClubMember.tenant_id == _tid(),
            AffairsClubMember.is_deleted.is_(False))).first()
        if not m:
            raise not_found("成员记录不存在")
        if m.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "该成员已退社")
        # 与加人对称：非全域只能退本数据范围内学生
        _member_scope_or_403(db, m.student_id, user)
        m.status, m.quit_at, m.version = "QUIT", datetime.utcnow(), m.version + 1
        db.flush()  # 确保 QUIT 落定后再统计（本会话 autoflush 关闭）
        _sync_count(db, m.club_id)
        _audit(db, m.club_id, "CLUB_MEMBER_REMOVE", f"member={member_id}")
        db.commit()
        return {"memberId": str(member_id), "status": "QUIT"}


def annual_review(club_id, body, user) -> dict:
    from app.models import AffairsClubAnnualReview
    year = (getattr(body, "reviewYear", "") or "").strip()
    result = getattr(body, "result", "PASS") or "PASS"
    if not year:
        raise AppException("VALIDATION_ERROR", "年审学年必填")
    if result not in ("PASS", "CONDITIONAL", "FAIL"):
        raise AppException("VALIDATION_ERROR", "年审结果非法")
    with session() as db:
        _load(db, club_id)
        dup = db.scalars(select(AffairsClubAnnualReview).where(
            AffairsClubAnnualReview.tenant_id == _tid(),
            AffairsClubAnnualReview.club_id == int(club_id),
            AffairsClubAnnualReview.review_year == year,
            AffairsClubAnnualReview.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学年已年审")
        n, _r, _u = _op()
        rv = AffairsClubAnnualReview(tenant_id=_tid(), club_id=int(club_id), review_year=year,
                                     result=result, activity_count=getattr(body, "activityCount", None),
                                     comment=getattr(body, "comment", None), reviewer_name=n,
                                     reviewed_at=datetime.utcnow(), created_by=_uid_int(user))
        db.add(rv); db.flush()
        _audit(db, club_id, "CLUB_ANNUAL_REVIEW", f"{year}:{result}")
        db.commit()
        return {"reviewId": str(rv.id), "clubId": str(club_id), "reviewYear": year, "result": result}


def list_annual_reviews(club_id, user):
    from app.models import AffairsClubAnnualReview
    with session() as db:
        _load(db, club_id)
        rows = db.scalars(select(AffairsClubAnnualReview).where(
            AffairsClubAnnualReview.tenant_id == _tid(),
            AffairsClubAnnualReview.club_id == int(club_id),
            AffairsClubAnnualReview.is_deleted.is_(False))
            .order_by(AffairsClubAnnualReview.review_year.desc())).all()
        return [{"reviewId": str(r.id), "reviewYear": r.review_year, "result": r.result,
                 "activityCount": r.activity_count, "comment": r.comment or "",
                 "reviewerName": r.reviewer_name or "", "reviewedAt": _iso(r.reviewed_at)} for r in rows]
