"""13A-D 学生活动与第二课堂 · 波次1 活动底座 service（活动闭环 + 报名签到 + 二课学分）。

状态机（施工包 §7.1）：DRAFT→PUBLISHED→ENROLL_CLOSED→ONGOING→FINISHED→CONFIRMED→ARCHIVED；CANCELLED 旁路。
CONFIRMED 唯一出口生成 t_affairs_activity_credit（(student,activity,type) 唯一防重复）+ 进360。
数据范围复用 _allowed_class_ids；业务留痕复用 AffairsAuditTrail；进360 复用 StudentStageEvent。
依据中青联发〔2018〕5号《第二课堂成绩单》记录评价/价值应用体系（已核验原文）。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.services.db_service import _iso, _tid, session

ACTIVITY_STATUS = ("DRAFT", "PUBLISHED", "ENROLL_CLOSED", "ONGOING",
                   "FINISHED", "CONFIRMED", "CANCELLED", "ARCHIVED")
ACTIVITY_TYPES = ("ACTIVITY", "VOLUNTEER", "LECTURE", "COMPETITION", "PRACTICE")
CREDIT_TYPES = ("SECOND_CLASS", "MORAL", "VOLUNTEER_HOUR")
# 手动/到时流转
_MANUAL = {"ENROLL_CLOSE": ("PUBLISHED", "ENROLL_CLOSED"),
           "START": ("ENROLL_CLOSED", "ONGOING"),
           "FINISH": ("ONGOING", "FINISHED")}
L_STATUS = {"DRAFT": "草稿", "PUBLISHED": "报名中", "ENROLL_CLOSED": "报名截止",
            "ONGOING": "进行中", "FINISHED": "已结束", "CONFIRMED": "已确认",
            "CANCELLED": "已取消", "ARCHIVED": "已归档"}
L_TYPE = {"ACTIVITY": "活动", "VOLUNTEER": "志愿服务", "LECTURE": "讲座报告",
          "COMPETITION": "竞赛", "PRACTICE": "社会实践"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), u.get("userId")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="ACTIVITY",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _row(a, signup_count=None, checkin_count=None) -> dict:
    return {"activityId": str(a.id), "activityName": a.activity_name, "activityType": a.activity_type,
            "activityTypeLabel": L_TYPE.get(a.activity_type, a.activity_type),
            "scopeType": a.scope_type, "scopeRef": a.scope_ref, "orgId": str(a.org_id or ""),
            "location": a.location or "", "description": a.description or "",
            "startAt": _iso(a.start_at), "endAt": _iso(a.end_at), "enrollDeadline": _iso(a.enroll_deadline),
            "quota": a.quota, "creditType": a.credit_type, "categoryCode": a.category_code,
            "creditValue": float(a.credit_value) if a.credit_value is not None else None,
            "status": a.status, "statusLabel": L_STATUS.get(a.status, a.status),
            "publisherName": a.publisher_name or "", "confirmAt": _iso(a.confirm_at),
            "version": a.version, "signupCount": signup_count, "checkinCount": checkin_count}


def _load(db, activity_id):
    from app.models import AffairsActivity
    a = db.get(AffairsActivity, int(activity_id))
    if not a or a.is_deleted or a.tenant_id != _tid():
        raise not_found("活动不存在")
    return a


def _uid_int(user):
    try:
        return int((user or {}).get("userId"))
    except (TypeError, ValueError):
        return None


# ═══════════ 活动 CRUD / 流转 ═══════════

def list_activities(user, activity_type=None, status=None, page=1, page_size=20):
    from app.models import AffairsActivity, AffairsActivitySignup
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        base_conds = [AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False)]
        if activity_type:
            base_conds.append(AffairsActivity.activity_type == activity_type)
        conds = list(base_conds)
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            conds.append(AffairsActivity.status.in_(statuses))
        status_counts = status_counts_by_column(
            db, AffairsActivity, AffairsActivity.status, base_conds,
        )
        rows = db.scalars(select(AffairsActivity).where(*conds).order_by(AffairsActivity.id.desc())).all()
        out = []
        for a in rows:
            sc = db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
                AffairsActivitySignup.signup_status != "CANCELLED",
                AffairsActivitySignup.is_deleted.is_(False))) or 0
            out.append(_row(a, signup_count=sc))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total, status_counts


def create_activity(body, user) -> dict:
    from app.models import AffairsActivity
    name = (getattr(body, "activityName", "") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "活动名称必填")
    atype = getattr(body, "activityType", "ACTIVITY") or "ACTIVITY"
    if atype not in ACTIVITY_TYPES:
        raise AppException("VALIDATION_ERROR", "活动类型非法")
    with session() as db:
        n, _r, uid = _op()
        a = AffairsActivity(
            tenant_id=_tid(), activity_name=name, activity_type=atype,
            scope_type=getattr(body, "scopeType", None), scope_ref=getattr(body, "scopeRef", None),
            location=getattr(body, "location", None), description=getattr(body, "description", None),
            start_at=_parse(getattr(body, "startAt", None)), end_at=_parse(getattr(body, "endAt", None)),
            enroll_deadline=_parse(getattr(body, "enrollDeadline", None)),
            quota=getattr(body, "quota", None), credit_type=getattr(body, "creditType", None),
            credit_value=getattr(body, "creditValue", None), category_code=getattr(body, "categoryCode", None),
            status="DRAFT", publisher_id=_uid_int(user), publisher_name=n)
        db.add(a); db.flush()
        _audit(db, a.id, "ACTIVITY_CREATE", name)
        db.commit(); db.refresh(a)
        return _row(a)


def update_activity(activity_id, body, user) -> dict:
    with session() as db:
        a = _load(db, activity_id)
        if a.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿可编辑")
        for attr, key in [("activity_name", "activityName"), ("location", "location"),
                          ("description", "description"), ("scope_type", "scopeType"),
                          ("scope_ref", "scopeRef"), ("credit_type", "creditType"),
                          ("category_code", "categoryCode")]:
            v = getattr(body, key, None)
            if v is not None:
                setattr(a, attr, v)
        for attr, key in [("start_at", "startAt"), ("end_at", "endAt"), ("enroll_deadline", "enrollDeadline")]:
            v = getattr(body, key, None)
            if v is not None:
                setattr(a, attr, _parse(v))
        if getattr(body, "quota", None) is not None:
            a.quota = body.quota
        if getattr(body, "creditValue", None) is not None:
            a.credit_value = body.creditValue
        a.version += 1
        _audit(db, a.id, "ACTIVITY_UPDATE")
        db.commit(); db.refresh(a)
        return _row(a)


def publish_activity(activity_id, user, action="PUBLISH", reason="", expected_version=None) -> dict:
    with session() as db:
        a = _load(db, activity_id)
        atomic_claim_version(db, a, expected_version)
        if action == "PUBLISH":
            if a.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "仅草稿可发布")
            if a.quota is not None and a.quota < 1:
                raise AppException("VALIDATION_ERROR", "名额至少为 1")
            if a.start_at and a.end_at and a.end_at <= a.start_at:
                raise AppException("VALIDATION_ERROR", "结束时间须晚于开始时间")
            a.status = "PUBLISHED"
            _audit(db, a.id, "ACTIVITY_PUBLISH")
        elif action == "CANCEL":
            if a.status not in ("PUBLISHED", "ENROLL_CLOSED", "DRAFT"):
                raise AppException("DATA_CONFLICT", "当前状态不可取消")
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "取消原因不少于 5 字")
            a.status = "CANCELLED"
            _audit(db, a.id, "ACTIVITY_CANCEL", reason)
        else:
            raise AppException("VALIDATION_ERROR", "非法动作")
        a.version += 1
        db.commit(); db.refresh(a)
        return _row(a)


def transition_activity(activity_id, user, action, expected_version=None) -> dict:
    """手动/到时流转 ENROLL_CLOSE/START/FINISH。"""
    if action not in _MANUAL:
        raise AppException("VALIDATION_ERROR", "非法流转")
    need, nxt = _MANUAL[action]
    with session() as db:
        a = _load(db, activity_id)
        if a.status != need:
            raise AppException("DATA_CONFLICT", f"当前状态不可{action}")
        atomic_claim_version(db, a, expected_version)
        a.status = nxt; a.version += 1
        _audit(db, a.id, f"ACTIVITY_{action}")
        db.commit(); db.refresh(a)
        return _row(a)


def confirm_activity(activity_id, user, expected_version=None) -> dict:
    """FINISHED→CONFIRMED：为已签到学生生成学时/积分/时长（唯一约束幂等）+ 进360。"""
    from app.models import (AffairsActivityCredit, AffairsActivitySignup, StudentStageEvent)
    with session() as db:
        a = _load(db, activity_id)
        if a.status != "FINISHED":
            raise AppException("DATA_CONFLICT", "仅已结束活动可确认")
        atomic_claim_version(db, a, expected_version)
        signups = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
            AffairsActivitySignup.signup_status == "CHECKED_IN",
            AffairsActivitySignup.is_deleted.is_(False))).all()
        ctype = a.credit_type or "SECOND_CLASS"
        cval = a.credit_value if a.credit_value is not None else 0
        made = 0
        n, _r, uid = _op()
        for su in signups:
            dup = db.scalars(select(AffairsActivityCredit).where(
                AffairsActivityCredit.tenant_id == _tid(),
                AffairsActivityCredit.student_id == su.student_id,
                AffairsActivityCredit.activity_id == a.id,
                AffairsActivityCredit.credit_type == ctype)).first()
            if dup:
                continue
            db.add(AffairsActivityCredit(tenant_id=_tid(), student_id=su.student_id, activity_id=a.id,
                                         credit_type=ctype, credit_value=cval, category_code=a.category_code,
                                         source="ACTIVITY", remark=a.activity_name, created_by=_uid_int(user)))
            su.signup_status = "CONFIRMED"; su.version += 1
            db.add(StudentStageEvent(tenant_id=_tid(), student_id=su.student_id, from_stage=None,
                                     to_stage="ACTIVITY_CONFIRMED",
                                     reason=f"参加《{a.activity_name}》获{L_TYPE.get(a.activity_type,'')} {cval}",
                                     source_module="student-affairs"))
            made += 1
        a.status = "CONFIRMED"; a.confirm_at = datetime.utcnow(); a.version += 1
        _audit(db, a.id, "ACTIVITY_CONFIRM", f"{made}人入账")
        db.commit(); db.refresh(a)
        d = _row(a); d["creditsGranted"] = made
        return d


def unconfirm_activity(activity_id, user, reason="", expected_version=None) -> dict:
    """撤销确认：删除本活动 credit + 回退 signup + 活动回 FINISHED。"""
    from app.models import AffairsActivityCredit, AffairsActivitySignup
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "撤销原因不少于 5 字")
    with session() as db:
        a = _load(db, activity_id)
        if a.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", "仅已确认活动可撤销")
        atomic_claim_version(db, a, expected_version)
        for c in db.scalars(select(AffairsActivityCredit).where(
                AffairsActivityCredit.tenant_id == _tid(), AffairsActivityCredit.activity_id == a.id)).all():
            db.delete(c)
        for su in db.scalars(select(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
                AffairsActivitySignup.signup_status == "CONFIRMED")).all():
            su.signup_status = "CHECKED_IN"; su.version += 1
        a.status = "FINISHED"; a.confirm_at = None; a.version += 1
        _audit(db, a.id, "ACTIVITY_UNCONFIRM", reason)
        db.commit(); db.refresh(a)
        return _row(a)


def archive_activity(activity_id, user, expected_version=None) -> dict:
    with session() as db:
        a = _load(db, activity_id)
        if a.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", "仅已确认活动可归档")
        atomic_claim_version(db, a, expected_version)
        a.status = "ARCHIVED"; a.version += 1
        _audit(db, a.id, "ACTIVITY_ARCHIVE")
        db.commit(); db.refresh(a)
        return _row(a)


def list_participants(activity_id, user):
    from app.models import AffairsActivitySignup, StudentProfile
    with session() as db:
        a = _load(db, activity_id)
        rows = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
            AffairsActivitySignup.is_deleted.is_(False)).order_by(AffairsActivitySignup.id)).all()
        out = []
        for su in rows:
            s = db.get(StudentProfile, int(su.student_id))
            out.append({"signupId": str(su.id), "studentId": str(su.student_id),
                        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
                        "signupStatus": su.signup_status, "enrolledAt": _iso(su.enrolled_at),
                        "checkinAt": _iso(su.checkin_at)})
        return out


# ═══════════ 报名 / 签到（学生本人，移动端）═══════════

def _resolve_student_id(db, user):
    """解析登录学生的 StudentProfile.id（与 mobile_affairs_service._me 同源）。"""
    from app.services.mobile_student_service import _require_student, resolve_student
    stu = resolve_student(db, _require_student(user))
    if not stu:
        raise AppException("PERMISSION_DENIED", "尚未建立你的学生档案")
    return stu.id


def enroll(activity_id, user, action="ENROLL") -> dict:
    from app.models import AffairsActivitySignup
    with session() as db:
        sid = _resolve_student_id(db, user)
        a = _load(db, activity_id)
        if a.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "活动未在报名中")
        if a.enroll_deadline and a.enroll_deadline < datetime.utcnow():
            raise AppException("DATA_CONFLICT", "报名已截止")
        su = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
            AffairsActivitySignup.student_id == sid, AffairsActivitySignup.is_deleted.is_(False))).first()
        if action == "CANCEL":
            if su and su.signup_status in ("ENROLLED", "WAITLIST"):
                su.signup_status = "CANCELLED"; su.version += 1
                _audit(db, a.id, "ACTIVITY_ENROLL_CANCEL", f"student={sid}")
            db.commit()
            return {"activityId": str(a.id), "signupStatus": "CANCELLED"}
        # ENROLL
        if su and su.signup_status in ("ENROLLED", "WAITLIST", "CHECKED_IN", "CONFIRMED"):
            raise AppException("DATA_CONFLICT", "已报名，请勿重复")
        if a.quota is not None:
            cnt = db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
                AffairsActivitySignup.signup_status.in_(("ENROLLED", "CHECKED_IN", "CONFIRMED")),
                AffairsActivitySignup.is_deleted.is_(False))) or 0
            if cnt >= a.quota:
                raise AppException("DATA_CONFLICT", "活动名额已满")
        if su:  # 复用被取消的行
            su.signup_status = "ENROLLED"; su.enrolled_at = datetime.utcnow(); su.version += 1
        else:
            db.add(AffairsActivitySignup(tenant_id=_tid(), activity_id=a.id, student_id=sid,
                                         signup_status="ENROLLED", enrolled_at=datetime.utcnow()))
        _audit(db, a.id, "ACTIVITY_ENROLL", f"student={sid}")
        db.commit()
        return {"activityId": str(a.id), "signupStatus": "ENROLLED"}


def checkin(activity_id, user, method="MANUAL") -> dict:
    from app.models import AffairsActivitySignup
    with session() as db:
        sid = _resolve_student_id(db, user)
        a = _load(db, activity_id)
        if a.status != "ONGOING":
            raise AppException("DATA_CONFLICT", "活动未在进行中，不能签到")
        su = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == a.id,
            AffairsActivitySignup.student_id == sid, AffairsActivitySignup.is_deleted.is_(False))).first()
        if not su or su.signup_status not in ("ENROLLED", "CHECKED_IN"):
            raise AppException("DATA_CONFLICT", "未报名或状态异常，不能签到")
        if su.signup_status == "CHECKED_IN":
            raise AppException("DATA_CONFLICT", "已签到，请勿重复")
        su.signup_status = "CHECKED_IN"; su.checkin_at = datetime.utcnow()
        su.checkin_method = method; su.version += 1
        _audit(db, a.id, "ACTIVITY_CHECKIN", f"student={sid}")
        db.commit()
        return {"activityId": str(a.id), "signupStatus": "CHECKED_IN"}


def my_activities(user):
    """学生端：可报名(PUBLISHED) + 我已报名。"""
    from app.models import AffairsActivity, AffairsActivitySignup
    with session() as db:
        try:
            sid = _resolve_student_id(db, user)
        except AppException:
            sid = None
        pub = db.scalars(select(AffairsActivity).where(
            AffairsActivity.tenant_id == _tid(), AffairsActivity.status == "PUBLISHED",
            AffairsActivity.is_deleted.is_(False)).order_by(AffairsActivity.id.desc())).all()
        mine_rows = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.student_id == sid,
            AffairsActivitySignup.is_deleted.is_(False))).all() if sid else []
        mine_map = {su.activity_id: su for su in mine_rows}
        available = [{**_row(a), "mySignupStatus": (mine_map[a.id].signup_status if a.id in mine_map else None)}
                     for a in pub]
        mine = []
        for su in mine_rows:
            a = db.get(AffairsActivity, int(su.activity_id))
            if a and not a.is_deleted:
                mine.append({**_row(a), "mySignupStatus": su.signup_status})
        return {"available": available, "mine": mine}


# ═══════════ 二课积分台账 / 类目 ═══════════

def credit_ledger(user, credit_type=None, page=1, page_size=50):
    from app.models import AffairsActivityCredit, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [AffairsActivityCredit.tenant_id == _tid()]
        if credit_type:
            conds.append(AffairsActivityCredit.credit_type == credit_type)
        rows = db.scalars(select(AffairsActivityCredit).where(*conds).order_by(
            AffairsActivityCredit.id.desc())).all()
        out = []
        for c in rows:
            s = db.get(StudentProfile, int(c.student_id)) if c.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append({"creditId": str(c.id), "studentId": str(c.student_id),
                        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
                        "creditType": c.credit_type, "creditValue": float(c.credit_value or 0),
                        "categoryCode": c.category_code or "", "source": c.source,
                        "remark": c.remark or "", "grantedAt": _iso(c.granted_at)})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def student_report(student_id, user):
    """个人第二课堂成绩单：按类型/类目汇总 + 明细。

    加权（本轮增强 a）：按类目系数 t_affairs_credit_category.weight 对类目原始合计加权，
    加权只在展示/汇总层（byCategoryWeighted + weightedTotal），**不改原始明细与 byCategory 原始合计**，
    不回改任何历史已入账 credit 行。类目无权重配置默认系数 1（加权=原始）。"""
    from app.models import AffairsActivityCredit, AffairsCreditCategory, StudentProfile
    with session() as db:
        s = db.get(StudentProfile, int(student_id))
        rows = db.scalars(select(AffairsActivityCredit).where(
            AffairsActivityCredit.tenant_id == _tid(),
            AffairsActivityCredit.student_id == int(student_id)).order_by(
            AffairsActivityCredit.id.desc())).all()
        # 类目系数映射（启用类目；缺省 1）
        cats = db.scalars(select(AffairsCreditCategory).where(
            AffairsCreditCategory.tenant_id == _tid(),
            AffairsCreditCategory.is_deleted.is_(False))).all()
        wmap = {c.category_code: (float(c.weight) if c.weight is not None else 1.0) for c in cats}
        by_type, by_cat = {}, {}
        for c in rows:
            v = float(c.credit_value or 0)
            by_type[c.credit_type] = round(by_type.get(c.credit_type, 0) + v, 2)
            if c.category_code:
                by_cat[c.category_code] = round(by_cat.get(c.category_code, 0) + v, 2)
        raw_total = round(sum(by_cat.values()), 2)
        by_cat_weighted = {k: round(v * wmap.get(k, 1.0), 2) for k, v in by_cat.items()}
        weighted_total = round(sum(by_cat_weighted.values()), 2)
        return {"studentId": str(student_id), "realName": s.real_name if s else "",
                "studentNo": s.student_no if s else "",
                "byType": [{"key": k, "value": v} for k, v in by_type.items()],
                "byCategory": [{"key": k, "value": v} for k, v in by_cat.items()],
                "byCategoryWeighted": [{"key": k, "value": v, "weight": wmap.get(k, 1.0),
                                        "rawValue": by_cat[k]} for k, v in by_cat_weighted.items()],
                "rawTotal": raw_total, "weightedTotal": weighted_total,
                "items": [{"activityId": str(c.activity_id or ""), "creditType": c.credit_type,
                           "creditValue": float(c.credit_value or 0), "categoryCode": c.category_code or "",
                           "remark": c.remark or "", "grantedAt": _iso(c.granted_at)} for c in rows]}


def list_categories(user):
    from app.models import AffairsCreditCategory
    with session() as db:
        rows = db.scalars(select(AffairsCreditCategory).where(
            AffairsCreditCategory.tenant_id == _tid(), AffairsCreditCategory.is_deleted.is_(False)).order_by(
            AffairsCreditCategory.sort_order, AffairsCreditCategory.id)).all()
        return [{"categoryCode": c.category_code, "categoryName": c.category_name,
                 "creditType": c.credit_type or "", "description": c.description or "",
                 "weight": float(c.weight) if c.weight is not None else 1.0,
                 "sortOrder": c.sort_order or 0, "status": c.status} for c in rows]


def create_category(body, user) -> dict:
    from app.models import AffairsCreditCategory
    code = (getattr(body, "categoryCode", "") or "").strip()
    name = (getattr(body, "categoryName", "") or "").strip()
    if not code or not name:
        raise AppException("VALIDATION_ERROR", "类目编码与名称必填")
    with session() as db:
        dup = db.scalars(select(AffairsCreditCategory).where(
            AffairsCreditCategory.tenant_id == _tid(),
            AffairsCreditCategory.category_code == code)).first()
        if dup:
            raise AppException("DATA_CONFLICT", "类目编码已存在")
        w = getattr(body, "weight", None)
        c = AffairsCreditCategory(tenant_id=_tid(), category_code=code, category_name=name,
                                  credit_type=getattr(body, "creditType", None),
                                  weight=w if (w is not None and float(w) > 0) else 1,
                                  description=getattr(body, "description", None),
                                  sort_order=getattr(body, "sortOrder", 0) or 0, status="ENABLED")
        db.add(c); db.flush()
        _audit(db, None, "CREDIT_CATEGORY_CREATE", code)
        db.commit()
        return {"categoryCode": code, "categoryName": name, "weight": float(c.weight) if c.weight is not None else 1.0}


def activity_stats(user):
    """活动统计（08 卡）：活动按类型/状态计数 + 二课学分按类型/类目汇总 + 报名签到概览。仅聚合。"""
    from app.models import AffairsActivity, AffairsActivityCredit, AffairsActivitySignup
    with session() as db:
        acts = db.scalars(select(AffairsActivity).where(
            AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False))).all()
        by_type, by_status = {}, {}
        for a in acts:
            by_type[a.activity_type] = by_type.get(a.activity_type, 0) + 1
            by_status[a.status] = by_status.get(a.status, 0) + 1
        creds = db.scalars(select(AffairsActivityCredit).where(
            AffairsActivityCredit.tenant_id == _tid())).all()
        credit_by_type, credit_by_cat = {}, {}
        for c in creds:
            v = float(c.credit_value or 0)
            credit_by_type[c.credit_type] = round(credit_by_type.get(c.credit_type, 0) + v, 2)
            if c.category_code:
                credit_by_cat[c.category_code] = round(credit_by_cat.get(c.category_code, 0) + v, 2)
        signups = db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(),
            AffairsActivitySignup.signup_status != "CANCELLED",
            AffairsActivitySignup.is_deleted.is_(False))) or 0
        checkins = db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(),
            AffairsActivitySignup.signup_status.in_(("CHECKED_IN", "CONFIRMED")),
            AffairsActivitySignup.is_deleted.is_(False))) or 0
        return {"totalActivities": len(acts), "totalSignups": int(signups), "totalCheckins": int(checkins),
                "creditStudents": len({c.student_id for c in creds}),
                "byType": [{"key": k, "count": v} for k, v in by_type.items()],
                "byStatus": [{"key": k, "count": v} for k, v in by_status.items()],
                "creditByType": [{"key": k, "value": v} for k, v in credit_by_type.items()],
                "creditByCategory": [{"key": k, "value": v} for k, v in credit_by_cat.items()]}


def _parse(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("/", "-"))
    except ValueError:
        try:
            return datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(str(v)[:10], "%Y-%m-%d")
            except ValueError:
                return None


# ═══════════ 志愿服务时长补录（04 卡；确认→VOLUNTEER_HOUR 学分入波次1 学分账）═══════════

_VOL_LABEL = {"PENDING": "待认定", "CONFIRMED": "已认定", "REJECTED": "已驳回"}
VOL_CATEGORY = "ZHIYUAN"  # 志愿公益类目（与二课默认五类对齐）


def _vol_row(r, s=None) -> dict:
    return {"recordId": str(r.id), "studentId": str(r.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "serviceName": r.service_name, "orgName": r.org_name or "",
            "hours": float(r.hours or 0), "serviceDate": _iso(r.service_date),
            "status": r.status, "statusLabel": _VOL_LABEL.get(r.status, r.status),
            "rejectReason": r.reject_reason or ""}


def list_volunteer(user, status=None, page=1, page_size=50):
    """志愿时长补录列表（数据范围过滤）。"""
    from app.models import AffairsVolunteerRecord, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [AffairsVolunteerRecord.tenant_id == _tid(), AffairsVolunteerRecord.is_deleted.is_(False)]
        status_counts = status_counts_by_column(
            db, AffairsVolunteerRecord, AffairsVolunteerRecord.status, base_conds,
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        conds = list(base_conds)
        if status:
            statuses = [s.strip() for s in str(status).split(",") if s.strip()]
            if len(statuses) == 1:
                conds.append(AffairsVolunteerRecord.status == statuses[0])
            elif statuses:
                conds.append(AffairsVolunteerRecord.status.in_(statuses))
        stmt = select(AffairsVolunteerRecord).join(
            StudentProfile, StudentProfile.id == AffairsVolunteerRecord.student_id
        ).where(*conds, StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))
        if allowed is not None:
            stmt = stmt.where(StudentProfile.class_id.in_(allowed or {-1}))
        rows = db.scalars(stmt.order_by(AffairsVolunteerRecord.id.desc())).all()
        sids = {int(r.student_id) for r in rows if r.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        out = [_vol_row(r, students.get(int(r.student_id)) if r.student_id else None) for r in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total, status_counts


def _vol_scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该学生不在您的数据范围内")


def create_volunteer(body, user) -> dict:
    """补录一条志愿时长（PENDING）。"""
    from app.models import AffairsVolunteerRecord, StudentProfile
    sid = int(getattr(body, "studentId", 0) or 0)
    hours = float(getattr(body, "hours", 0) or 0)
    name = (getattr(body, "serviceName", "") or "").strip()
    if hours <= 0:
        raise AppException("VALIDATION_ERROR", "志愿时长需大于 0")
    if not name:
        raise AppException("VALIDATION_ERROR", "服务名称必填")
    with session() as db:
        s = db.get(StudentProfile, sid) if sid else None
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        _vol_scope_or_403(db, sid, user)
        r = AffairsVolunteerRecord(tenant_id=_tid(), student_id=sid, service_name=name,
                                   org_name=getattr(body, "orgName", None), hours=hours,
                                   service_date=_parse(getattr(body, "serviceDate", None)),
                                   status="PENDING", created_by=_uid_int(user))
        db.add(r); db.flush()
        _audit(db, r.id, "VOLUNTEER_CREATE", f"{name} {hours}h")
        db.commit(); db.refresh(r)
        return _vol_row(r, s)


def confirm_volunteer(record_id, user, expected_version=None) -> dict:
    """认定：PENDING→CONFIRMED，生成 VOLUNTEER_HOUR 学分（复用波次1 学分账）+ 进360。"""
    from app.models import (AffairsActivityCredit, AffairsVolunteerRecord, StudentProfile,
                            StudentStageEvent)
    with session() as db:
        r = db.get(AffairsVolunteerRecord, int(record_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("志愿记录不存在")
        _vol_scope_or_403(db, r.student_id, user)
        if r.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待认定记录可认定")
        atomic_claim_version(db, r, expected_version)
        credit = AffairsActivityCredit(tenant_id=_tid(), student_id=r.student_id, activity_id=r.activity_id,
                                       credit_type="VOLUNTEER_HOUR", credit_value=r.hours,
                                       category_code=VOL_CATEGORY, source="VOLUNTEER_RECORD",
                                       remark=r.service_name, created_by=_uid_int(user))
        db.add(credit); db.flush()
        r.credit_id, r.status, r.version = credit.id, "CONFIRMED", r.version + 1
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=r.student_id, from_stage=None,
                                 to_stage="VOLUNTEER_CONFIRMED",
                                 reason=f"志愿服务《{r.service_name}》认定 {float(r.hours)} 小时",
                                 source_module="student-affairs"))
        _audit(db, r.id, "VOLUNTEER_CONFIRM", f"{float(r.hours)}h")
        db.commit(); db.refresh(r)
        s = db.get(StudentProfile, int(r.student_id))
        return _vol_row(r, s)


def reject_volunteer(record_id, user, reason="", expected_version=None) -> dict:
    """驳回：PENDING→REJECTED（原因≥5字，不生成学分）。"""
    from app.models import AffairsVolunteerRecord, StudentProfile
    if len((reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因至少 5 字")
    with session() as db:
        r = db.get(AffairsVolunteerRecord, int(record_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("志愿记录不存在")
        _vol_scope_or_403(db, r.student_id, user)
        if r.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待认定记录可驳回")
        atomic_claim_version(db, r, expected_version)
        r.status, r.reject_reason, r.version = "REJECTED", reason.strip(), r.version + 1
        _audit(db, r.id, "VOLUNTEER_REJECT", reason.strip())
        db.commit(); db.refresh(r)
        s = db.get(StudentProfile, int(r.student_id))
        return _vol_row(r, s)


# ═══════════ 第二课堂积分申诉（D 包·缺记/记错→审核补记/驳回）═══════════

_L_CAPPEAL = {"SUBMITTED": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回"}


def _cappeal_row(a, s=None) -> dict:
    return {"appealId": str(a.id), "studentId": str(a.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "activityId": str(a.activity_id or ""), "appealType": a.appeal_type,
            "claimCreditType": a.claim_credit_type,
            "claimValue": float(a.claim_value) if a.claim_value is not None else None,
            "reason": a.reason or "", "status": a.status,
            "statusLabel": _L_CAPPEAL.get(a.status, a.status), "reviewOpinion": a.review_opinion or "",
            "reviewer": a.reviewer or "", "reviewedAt": _iso(a.reviewed_at)}


def submit_credit_appeal(body, user) -> dict:
    from app.models import AffairsCreditAppeal, StudentProfile
    sid = int(getattr(body, "studentId", 0) or 0)
    atype = getattr(body, "appealType", "MISSING") or "MISSING"
    if atype not in ("MISSING", "WRONG"):
        raise AppException("VALIDATION_ERROR", "申诉类型非法")
    reason = (getattr(body, "reason", "") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 字")
    with session() as db:
        s = db.get(StudentProfile, sid) if sid else None
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        a = AffairsCreditAppeal(tenant_id=_tid(), student_id=sid,
                                activity_id=getattr(body, "activityId", None),
                                appeal_type=atype,
                                claim_credit_type=getattr(body, "claimCreditType", "SECOND_CLASS") or "SECOND_CLASS",
                                claim_value=getattr(body, "claimValue", None), reason=reason,
                                status="SUBMITTED", created_by=_uid_int(user))
        db.add(a); db.flush()
        _audit(db, a.id, "CREDIT_APPEAL_SUBMIT", atype)
        db.commit(); db.refresh(a)
        return _cappeal_row(a, s)


def list_credit_appeals(user, status=None, page=1, page_size=50):
    from app.models import AffairsCreditAppeal, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.is_deleted.is_(False)]
        status_counts = status_counts_by_column(
            db, AffairsCreditAppeal, AffairsCreditAppeal.status, base_conds,
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        conds = list(base_conds)
        if status:
            statuses = [s.strip() for s in str(status).split(",") if s.strip()]
            if len(statuses) == 1:
                conds.append(AffairsCreditAppeal.status == statuses[0])
            elif statuses:
                conds.append(AffairsCreditAppeal.status.in_(statuses))
        stmt = select(AffairsCreditAppeal).join(
            StudentProfile, StudentProfile.id == AffairsCreditAppeal.student_id
        ).where(*conds, StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))
        if allowed is not None:
            stmt = stmt.where(StudentProfile.class_id.in_(allowed or {-1}))
        rows = db.scalars(stmt.order_by(AffairsCreditAppeal.id.desc())).all()
        sids = {int(a.student_id) for a in rows if a.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        out = [_cappeal_row(a, students.get(int(a.student_id)) if a.student_id else None) for a in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total, status_counts


def review_credit_appeal(appeal_id, body, user) -> dict:
    """审核：APPROVE→按主张补记学分(source=MANUAL_ADJUST)+置 APPROVED；REJECT→置 REJECTED(意见≥5)。"""
    from app.models import AffairsCreditAppeal, AffairsActivityCredit, StudentProfile
    action = (getattr(body, "action", "") or "").strip().upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "审核动作非法")
    opinion = (getattr(body, "opinion", "") or "").strip()
    if action == "REJECT" and len(opinion) < 5:
        raise AppException("VALIDATION_ERROR", "驳回意见至少 5 字")
    with session() as db:
        a = db.get(AffairsCreditAppeal, int(appeal_id))
        if not a or a.is_deleted or a.tenant_id != _tid():
            raise not_found("申诉不存在")
        if a.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该申诉已审核")
        atomic_claim_version(db, a, getattr(body, "version", None))
        if action == "APPROVE":
            val = float(a.claim_value or 0)
            if val <= 0:
                raise AppException("DATA_CONFLICT", "主张学时须大于0方可补记")
            c = AffairsActivityCredit(tenant_id=_tid(), student_id=a.student_id,
                                      activity_id=a.activity_id, credit_type=a.claim_credit_type,
                                      credit_value=val, source="MANUAL_ADJUST",
                                      remark="积分申诉补记", created_by=_uid_int(user))
            db.add(c); db.flush()
            a.result_credit_id, a.status = c.id, "APPROVED"
        else:
            a.status = "REJECTED"
        a.review_opinion, a.reviewer = opinion, _op()[0]
        from datetime import datetime as _dt
        a.reviewed_at, a.version = _dt.utcnow(), a.version + 1
        _audit(db, a.id, "CREDIT_APPEAL_REVIEW", action)
        db.commit(); db.refresh(a)
        s = db.get(StudentProfile, int(a.student_id))
        return _cappeal_row(a, s)
