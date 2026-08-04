"""13A-D 学生活动与第二课堂 · 波次1 活动底座 service（活动闭环 + 报名签到 + 二课学分）。

状态机（施工包 §7.1）：DRAFT→PUBLISHED→ENROLL_CLOSED→ONGOING→FINISHED→CONFIRMED→ARCHIVED；CANCELLED 旁路。
CONFIRMED 唯一出口生成 t_affairs_activity_credit（(student,activity,type) 唯一防重复）+ 进360。
数据范围复用 _allowed_class_ids；业务留痕复用 AffairsAuditTrail；进360 复用 StudentStageEvent。
依据中青联发〔2018〕5号《第二课堂成绩单》记录评价/价值应用体系（已核验原文）。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, func, select

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
_MAX_CREDIT = Decimal("9999.99")
_VOL_LABEL = {"PENDING": "待认定", "CONFIRMED": "已认定", "REJECTED": "已驳回"}
VOL_CATEGORY = "ZHIYUAN"


def _decimal(value, label: str, *, positive: bool = True) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}格式非法") from exc
    if not result.is_finite() or abs(result) > _MAX_CREDIT or result.as_tuple().exponent < -2:
        raise AppException("VALIDATION_ERROR", f"{label}绝对值不超过9999.99且最多2位小数")
    if positive and result <= 0:
        raise AppException("VALIDATION_ERROR", f"{label}必须大于0")
    return result


def _parse_datetime(value):
    if value in (None, ""):
        return None
    raw = str(value).strip().replace("/", "-")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", "日期时间格式不正确") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _validate_activity_body(body, activity=None) -> None:
    supplied_name = getattr(body, "activityName", None)
    name = str(supplied_name if supplied_name is not None else getattr(activity, "activity_name", "") or "").strip()
    if not 2 <= len(name) <= 200:
        raise AppException("VALIDATION_ERROR", "活动名称需2-200字")
    activity_type = str(getattr(body, "activityType", None) or getattr(activity, "activity_type", "ACTIVITY")).upper()
    if activity_type not in ACTIVITY_TYPES:
        raise AppException("VALIDATION_ERROR", "活动类型非法")
    start = (_parse_datetime(getattr(body, "startAt", None))
             if getattr(body, "startAt", None) is not None else getattr(activity, "start_at", None))
    end = (_parse_datetime(getattr(body, "endAt", None))
           if getattr(body, "endAt", None) is not None else getattr(activity, "end_at", None))
    deadline = (_parse_datetime(getattr(body, "enrollDeadline", None))
                if getattr(body, "enrollDeadline", None) is not None else getattr(activity, "enroll_deadline", None))
    if start and end and end <= start:
        raise AppException("VALIDATION_ERROR", "活动结束时间必须晚于开始时间")
    if deadline and start and deadline > start:
        raise AppException("VALIDATION_ERROR", "报名截止时间不能晚于活动开始时间")
    quota = getattr(body, "quota", None) if getattr(body, "quota", None) is not None else getattr(activity, "quota", None)
    if quota not in (None, ""):
        try:
            quota = int(quota)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "活动名额必须为整数") from exc
        if quota < 1 or quota > 100000:
            raise AppException("VALIDATION_ERROR", "活动名额应为1-100000")
    credit_type = (getattr(body, "creditType", None)
                   if getattr(body, "creditType", None) is not None else getattr(activity, "credit_type", None))
    credit_value = (getattr(body, "creditValue", None)
                    if getattr(body, "creditValue", None) is not None else getattr(activity, "credit_value", None))
    if credit_type and str(credit_type).upper() not in CREDIT_TYPES:
        raise AppException("VALIDATION_ERROR", "积分类型非法")
    if credit_value not in (None, ""):
        _decimal(credit_value, "积分值")


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
    allowed_actions = {
        "DRAFT": ["PUBLISH", "CANCEL", "EDIT"],
        "PUBLISHED": ["ENROLL_CLOSE", "CANCEL"],
        "ENROLL_CLOSED": ["START", "CANCEL"],
        "ONGOING": ["FINISH"],
        "FINISHED": ["CONFIRM"],
        "CONFIRMED": ["UNCONFIRM", "ARCHIVE"],
    }.get(a.status, [])
    return {"activityId": str(a.id), "activityName": a.activity_name, "activityType": a.activity_type,
            "activityTypeLabel": L_TYPE.get(a.activity_type, a.activity_type),
            "scopeType": a.scope_type, "scopeRef": a.scope_ref, "orgId": str(a.org_id or ""),
            "location": a.location or "", "description": a.description or "",
            "startAt": _iso(a.start_at), "endAt": _iso(a.end_at), "enrollDeadline": _iso(a.enroll_deadline),
            "quota": a.quota, "creditType": a.credit_type, "categoryCode": a.category_code,
            "creditValue": float(a.credit_value) if a.credit_value is not None else None,
            "status": a.status, "statusLabel": L_STATUS.get(a.status, a.status),
            "publisherName": a.publisher_name or "", "confirmAt": _iso(a.confirm_at),
            "version": int(a.version or 0), "signupCount": signup_count, "checkinCount": checkin_count,
            "allowedActions": allowed_actions}


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

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    with session() as db:
        base_conds = [AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False)]
        if activity_type:
            base_conds.append(AffairsActivity.activity_type == activity_type)
        conds = list(base_conds)
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            conds.append(AffairsActivity.status.in_(statuses))
        status_counts = status_counts_by_column(db, AffairsActivity, AffairsActivity.status, base_conds)
        total = int(db.scalar(select(func.count()).select_from(AffairsActivity).where(*conds)) or 0)
        signup_counts = (
            select(
                AffairsActivitySignup.activity_id.label("activity_id"),
                func.count(AffairsActivitySignup.id).label("signup_count"),
            )
            .where(
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.signup_status != "CANCELLED",
                AffairsActivitySignup.is_deleted.is_(False),
            )
            .group_by(AffairsActivitySignup.activity_id)
            .subquery()
        )
        rows = db.execute(
            select(AffairsActivity, func.coalesce(signup_counts.c.signup_count, 0))
            .outerjoin(signup_counts, signup_counts.c.activity_id == AffairsActivity.id)
            .where(*conds)
            .order_by(AffairsActivity.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [_row(activity, signup_count=int(count or 0)) for activity, count in rows], total, status_counts


def create_activity(body, user) -> dict:
    from app.models import AffairsActivity
    _validate_activity_body(body)
    name = str(getattr(body, "activityName", "") or "").strip()
    activity_type = str(getattr(body, "activityType", "ACTIVITY") or "ACTIVITY").upper()
    credit_value = getattr(body, "creditValue", None)
    if credit_value not in (None, ""):
        credit_value = _decimal(credit_value, "积分值")
    quota = getattr(body, "quota", None)
    quota = int(quota) if quota not in (None, "") else None
    with session() as db:
        publisher_name, _role, _uid = _op()
        row = AffairsActivity(
            tenant_id=_tid(), activity_name=name, activity_type=activity_type,
            scope_type=getattr(body, "scopeType", None), scope_ref=getattr(body, "scopeRef", None),
            location=getattr(body, "location", None), description=getattr(body, "description", None),
            start_at=_parse_datetime(getattr(body, "startAt", None)),
            end_at=_parse_datetime(getattr(body, "endAt", None)),
            enroll_deadline=_parse_datetime(getattr(body, "enrollDeadline", None)),
            quota=quota, credit_type=getattr(body, "creditType", None),
            credit_value=credit_value, category_code=getattr(body, "categoryCode", None),
            status="DRAFT", publisher_id=_uid_int(user), publisher_name=publisher_name,
        )
        db.add(row); db.flush()
        _audit(db, row.id, "ACTIVITY_CREATE", name)
        db.commit(); db.refresh(row)
        return _row(row)

def update_activity(activity_id, body, user) -> dict:
    from app.models import AffairsActivity
    with session() as db:
        row = db.scalars(select(AffairsActivity).where(
            AffairsActivity.tenant_id == _tid(), AffairsActivity.id == int(activity_id),
            AffairsActivity.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("活动不存在")
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿可编辑")
        expected = getattr(body, "version", None)
        atomic_claim_version(db, row, int(row.version or 0) if expected is None else expected)
        _validate_activity_body(body, row)
        mapping = {
            "activity_name": "activityName", "location": "location", "description": "description",
            "scope_type": "scopeType", "scope_ref": "scopeRef", "credit_type": "creditType",
            "category_code": "categoryCode",
        }
        for attr, key in mapping.items():
            value = getattr(body, key, None)
            if value is not None:
                setattr(row, attr, value.strip() if key == "activityName" and isinstance(value, str) else value)
        for attr, key in (("start_at", "startAt"), ("end_at", "endAt"), ("enroll_deadline", "enrollDeadline")):
            value = getattr(body, key, None)
            if value is not None:
                setattr(row, attr, _parse_datetime(value))
        if getattr(body, "quota", None) is not None:
            row.quota = int(body.quota)
        if getattr(body, "creditValue", None) is not None:
            row.credit_value = _decimal(body.creditValue, "积分值")
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "ACTIVITY_UPDATE")
        db.commit(); db.refresh(row)
        return _row(row)

def publish_activity(activity_id, user, action="PUBLISH", reason="", expected_version=None) -> dict:
    action = str(action or "").upper()
    with session() as db:
        row = _load(db, activity_id)
        atomic_claim_version(db, row, expected_version)
        if action == "PUBLISH":
            if row.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "仅草稿可发布")
            snapshot = type("ActivitySnapshot", (), {
                "activityName": row.activity_name, "activityType": row.activity_type,
                "startAt": row.start_at, "endAt": row.end_at, "enrollDeadline": row.enroll_deadline,
                "quota": row.quota, "creditType": row.credit_type, "creditValue": row.credit_value,
            })()
            _validate_activity_body(snapshot, row)
            row.status = "PUBLISHED"
            _audit(db, row.id, "ACTIVITY_PUBLISH")
        elif action == "CANCEL":
            if row.status not in ("PUBLISHED", "ENROLL_CLOSED", "DRAFT"):
                raise AppException("DATA_CONFLICT", "当前状态不可取消")
            reason = str(reason or "").strip()
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "取消原因不少于 5 字")
            row.status = "CANCELLED"
            _audit(db, row.id, "ACTIVITY_CANCEL", reason)
        else:
            raise AppException("VALIDATION_ERROR", "非法动作")
        row.version = int(row.version or 0) + 1
        db.commit(); db.refresh(row)
        return _row(row)

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
    """FINISHED→CONFIRMED；首次确认入账，撤销后的再次确认追加恢复流水。"""
    from app.models import AffairsActivityCredit, AffairsActivitySignup, StudentStageEvent

    with session() as db:
        activity = _load(db, activity_id)
        if activity.status != "FINISHED":
            raise AppException("DATA_CONFLICT", "仅已结束活动可确认")
        atomic_claim_version(db, activity, expected_version)
        signups = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(),
            AffairsActivitySignup.activity_id == activity.id,
            AffairsActivitySignup.signup_status == "CHECKED_IN",
            AffairsActivitySignup.is_deleted.is_(False),
        ).with_for_update()).all()
        credit_type = activity.credit_type or "SECOND_CLASS"
        credit_value = activity.credit_value if activity.credit_value is not None else 0
        student_ids = {int(signup.student_id) for signup in signups}
        originals = {
            int(credit.student_id): credit
            for credit in db.scalars(select(AffairsActivityCredit).where(
                AffairsActivityCredit.tenant_id == _tid(),
                AffairsActivityCredit.student_id.in_(student_ids) if student_ids else AffairsActivityCredit.student_id == -1,
                AffairsActivityCredit.activity_id == activity.id,
                AffairsActivityCredit.credit_type == credit_type,
                AffairsActivityCredit.source == "ACTIVITY",
            ).order_by(AffairsActivityCredit.id)).all()
        }
        made = restored = 0
        for signup in signups:
            original = originals.get(int(signup.student_id))
            if original:
                db.add(AffairsActivityCredit(
                    tenant_id=_tid(), student_id=signup.student_id, activity_id=None,
                    credit_type=original.credit_type,
                    credit_value=Decimal(str(original.credit_value or 0)),
                    category_code=original.category_code, source="MANUAL_ADJUST",
                    remark=(
                        f"活动#{activity.id}重新确认恢复；原流水#{original.id}；"
                        "对应最近一次撤销确认冲正"
                    ),
                    created_by=_uid_int(user),
                ))
                event_stage = "ACTIVITY_RECONFIRMED"
                event_reason = f"活动《{activity.activity_name}》重新确认并恢复积分"
                restored += 1
            else:
                db.add(AffairsActivityCredit(
                    tenant_id=_tid(), student_id=signup.student_id, activity_id=activity.id,
                    credit_type=credit_type, credit_value=credit_value,
                    category_code=activity.category_code, source="ACTIVITY",
                    remark=activity.activity_name, created_by=_uid_int(user),
                ))
                event_stage = "ACTIVITY_CONFIRMED"
                event_reason = (
                    f"参加《{activity.activity_name}》获"
                    f"{L_TYPE.get(activity.activity_type, '')} {credit_value}"
                )
                made += 1
            signup.signup_status = "CONFIRMED"
            signup.version = int(signup.version or 0) + 1
            db.add(StudentStageEvent(
                tenant_id=_tid(), student_id=signup.student_id, from_stage=None,
                to_stage=event_stage, reason=event_reason, source_module="student-affairs",
            ))
        activity.status = "CONFIRMED"
        activity.confirm_at = datetime.utcnow()
        activity.version = int(activity.version or 0) + 1
        _audit(
            db, activity.id, "ACTIVITY_RECONFIRM" if restored else "ACTIVITY_CONFIRM",
            f"首次{made}人;恢复{restored}人",
        )
        db.commit()
        db.refresh(activity)
        result = _row(activity)
        result["creditsGranted"] = made + restored
        return result


def unconfirm_activity(activity_id, user, reason="", expected_version=None) -> dict:
    """撤销确认只追加冲正流水，绝不删除正式积分原账。"""
    from app.models import AffairsActivity, AffairsActivityCredit, AffairsActivitySignup, StudentStageEvent
    reason = str(reason or "").strip()
    if not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "撤销原因需5-500字")
    with session() as db:
        row = db.scalars(select(AffairsActivity).where(
            AffairsActivity.tenant_id == _tid(), AffairsActivity.id == int(activity_id),
            AffairsActivity.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("活动不存在")
        if row.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", "仅已确认活动可撤销")
        atomic_claim_version(db, row, expected_version)
        credits = db.scalars(select(AffairsActivityCredit).where(
            AffairsActivityCredit.tenant_id == _tid(),
            AffairsActivityCredit.activity_id == row.id,
            AffairsActivityCredit.source == "ACTIVITY",
        )).all()
        for credit in credits:
            reversal = _decimal(-Decimal(str(credit.credit_value or 0)), "冲正数值", positive=False)
            db.add(AffairsActivityCredit(
                tenant_id=_tid(), student_id=credit.student_id, activity_id=None,
                credit_type=credit.credit_type, credit_value=reversal,
                category_code=credit.category_code, source="MANUAL_ADJUST",
                remark=f"活动#{row.id}撤销确认冲正；原流水#{credit.id}；原因：{reason}",
                created_by=_uid_int(user),
            ))
            db.add(StudentStageEvent(
                tenant_id=_tid(), student_id=int(credit.student_id), from_stage=None,
                to_stage="ACTIVITY_UNCONFIRMED", reason=f"活动《{row.activity_name}》积分已撤销",
                source_module="student-affairs",
            ))
        signups = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == row.id,
            AffairsActivitySignup.signup_status == "CONFIRMED", AffairsActivitySignup.is_deleted.is_(False),
        ).with_for_update()).all()
        for signup in signups:
            signup.signup_status = "CHECKED_IN"
            signup.version = int(signup.version or 0) + 1
        row.status, row.confirm_at = "FINISHED", None
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "ACTIVITY_UNCONFIRM", reason)
        db.commit(); db.refresh(row)
        return _row(row)

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
    from app.services import affairs_activity_reliability_service as reliability
    with session() as db:
        activity = _load(db, activity_id)
        tenant_all, class_tokens, college_tokens = reliability._teacher_scope_tokens(db, user)
        if not tenant_all and not reliability._activity_matches(activity, class_tokens, college_tokens):
            raise AppException("NO_DATA_SCOPE", "该活动不在您的数据范围内")
        rows = db.execute(select(AffairsActivitySignup, StudentProfile).join(
            StudentProfile, StudentProfile.id == AffairsActivitySignup.student_id,
        ).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == activity.id,
            AffairsActivitySignup.is_deleted.is_(False), StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ).order_by(AffairsActivitySignup.id)).all()
        return [{
            "signupId": str(signup.id), "studentId": str(signup.student_id),
            "studentNo": student.student_no or "", "realName": student.real_name or "",
            "signupStatus": signup.signup_status, "enrolledAt": _iso(signup.enrolled_at),
            "checkinAt": _iso(signup.checkin_at), "version": int(signup.version or 0),
        } for signup, student in rows]

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
    """学生端：可报名(PUBLISHED) + 我已报名；活动信息批量加载。"""
    from app.models import AffairsActivity, AffairsActivitySignup

    with session() as db:
        try:
            sid = _resolve_student_id(db, user)
        except AppException:
            sid = None
        published = db.scalars(select(AffairsActivity).where(
            AffairsActivity.tenant_id == _tid(), AffairsActivity.status == "PUBLISHED",
            AffairsActivity.is_deleted.is_(False),
        ).order_by(AffairsActivity.id.desc())).all()
        mine_rows = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.student_id == sid,
            AffairsActivitySignup.is_deleted.is_(False),
        )).all() if sid else []
        mine_map = {int(signup.activity_id): signup for signup in mine_rows}
        activity_ids = {int(signup.activity_id) for signup in mine_rows}
        activity_map = {
            int(activity.id): activity
            for activity in db.scalars(select(AffairsActivity).where(
                AffairsActivity.tenant_id == _tid(),
                AffairsActivity.id.in_(activity_ids) if activity_ids else AffairsActivity.id == -1,
                AffairsActivity.is_deleted.is_(False),
            )).all()
        }
        available = [{
            **_row(activity),
            "mySignupStatus": mine_map[int(activity.id)].signup_status if int(activity.id) in mine_map else None,
        } for activity in published]
        mine = [{
            **_row(activity_map[int(signup.activity_id)]), "mySignupStatus": signup.signup_status,
        } for signup in mine_rows if int(signup.activity_id) in activity_map]
        return {"available": available, "mine": mine}


# ═══════════ 二课积分台账 / 类目 ═══════════

def credit_ledger(user, credit_type=None, page=1, page_size=50):
    from app.models import AffairsActivityCredit, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 200))
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [AffairsActivityCredit.tenant_id == _tid()]
        if credit_type:
            conds.append(AffairsActivityCredit.credit_type == credit_type)
        if allowed is not None:
            if not allowed:
                return [], 0
            conds.append(StudentProfile.class_id.in_(allowed))
        base = select(AffairsActivityCredit, StudentProfile).join(
            StudentProfile,
            and_(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == AffairsActivityCredit.student_id,
                StudentProfile.is_deleted.is_(False),
            ),
        ).where(*conds)
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = db.execute(
            base.order_by(AffairsActivityCredit.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [{
            "creditId": str(credit.id), "studentId": str(credit.student_id),
            "studentNo": student.student_no, "realName": student.real_name,
            "creditType": credit.credit_type, "creditValue": float(credit.credit_value or 0),
            "categoryCode": credit.category_code or "", "source": credit.source,
            "remark": credit.remark or "", "grantedAt": _iso(credit.granted_at),
        } for credit, student in rows], total


def student_report(student_id, user):
    """个人第二课堂成绩单：数据范围校验后按类型/类目汇总，原账保持不可变。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import AffairsActivityCredit, AffairsCreditCategory
    student_id = int(student_id)
    with session() as db:
        student = build_affairs_context(user, db).require_student(db, student_id)
        rows = db.scalars(select(AffairsActivityCredit).where(
            AffairsActivityCredit.tenant_id == _tid(), AffairsActivityCredit.student_id == student_id,
        ).order_by(AffairsActivityCredit.id.desc())).all()
        categories = db.scalars(select(AffairsCreditCategory).where(
            AffairsCreditCategory.tenant_id == _tid(), AffairsCreditCategory.is_deleted.is_(False),
        )).all()
        weights = {row.category_code: Decimal(str(row.weight or 1)) for row in categories}
        by_type: dict[str, Decimal] = {}
        by_category: dict[str, Decimal] = {}
        for row in rows:
            value = Decimal(str(row.credit_value or 0))
            by_type[row.credit_type] = by_type.get(row.credit_type, Decimal("0")) + value
            if row.category_code:
                by_category[row.category_code] = by_category.get(row.category_code, Decimal("0")) + value
        weighted = {key: value * weights.get(key, Decimal("1")) for key, value in by_category.items()}
        return {
            "studentId": str(student_id), "realName": student.real_name or "", "studentNo": student.student_no or "",
            "byType": [{"key": key, "value": float(value)} for key, value in by_type.items()],
            "byCategory": [{"key": key, "value": float(value)} for key, value in by_category.items()],
            "byCategoryWeighted": [{
                "key": key, "value": float(value), "weight": float(weights.get(key, 1)),
                "rawValue": float(by_category[key]),
            } for key, value in weighted.items()],
            "rawTotal": float(sum(by_category.values(), Decimal("0"))),
            "weightedTotal": float(sum(weighted.values(), Decimal("0"))),
            "items": [{
                "activityId": str(row.activity_id or ""), "creditType": row.credit_type,
                "creditValue": float(row.credit_value or 0), "categoryCode": row.category_code or "",
                "source": row.source, "remark": row.remark or "", "grantedAt": _iso(row.granted_at),
            } for row in rows],
        }

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
    code = str(getattr(body, "categoryCode", None) or "").strip().upper()
    name = str(getattr(body, "categoryName", None) or "").strip()
    if not 2 <= len(code) <= 50 or not 2 <= len(name) <= 100:
        raise AppException("VALIDATION_ERROR", "类目编码需2-50字符，名称需2-100字")
    credit_type = str(getattr(body, "creditType", None) or "").upper()
    if credit_type and credit_type not in CREDIT_TYPES:
        raise AppException("VALIDATION_ERROR", "类目积分类型非法")
    weight = _decimal(getattr(body, "weight", 1) or 1, "类目权重")
    if weight > Decimal("100"):
        raise AppException("VALIDATION_ERROR", "类目权重应大于0、不超过100且最多2位小数")
    with session() as db:
        duplicate = db.scalars(select(AffairsCreditCategory.id).where(
            AffairsCreditCategory.tenant_id == _tid(),
            AffairsCreditCategory.category_code == code,
            AffairsCreditCategory.is_deleted.is_(False),
        ).limit(1)).first()
        if duplicate:
            raise AppException("DATA_CONFLICT", "类目编码已存在")
        row = AffairsCreditCategory(
            tenant_id=_tid(), category_code=code, category_name=name,
            credit_type=credit_type or None, weight=weight,
            description=getattr(body, "description", None),
            sort_order=getattr(body, "sortOrder", 0) or 0, status="ENABLED",
        )
        db.add(row); db.flush()
        _audit(db, None, "CREDIT_CATEGORY_CREATE", code)
        db.commit()
        return {"categoryCode": code, "categoryName": name, "weight": float(row.weight)}

def activity_stats(user):
    """活动统计：活动、报名和学分全部使用数据库聚合。"""
    from app.models import AffairsActivity, AffairsActivityCredit, AffairsActivitySignup
    with session() as db:
        type_rows = db.execute(
            select(AffairsActivity.activity_type, func.count(AffairsActivity.id))
            .where(AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False))
            .group_by(AffairsActivity.activity_type)
        ).all()
        status_rows = db.execute(
            select(AffairsActivity.status, func.count(AffairsActivity.id))
            .where(AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False))
            .group_by(AffairsActivity.status)
        ).all()
        credit_type_rows = db.execute(
            select(AffairsActivityCredit.credit_type, func.sum(AffairsActivityCredit.credit_value))
            .where(AffairsActivityCredit.tenant_id == _tid())
            .group_by(AffairsActivityCredit.credit_type)
        ).all()
        credit_category_rows = db.execute(
            select(AffairsActivityCredit.category_code, func.sum(AffairsActivityCredit.credit_value))
            .where(
                AffairsActivityCredit.tenant_id == _tid(),
                AffairsActivityCredit.category_code.is_not(None),
            ).group_by(AffairsActivityCredit.category_code)
        ).all()
        signups = int(db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(),
            AffairsActivitySignup.signup_status != "CANCELLED",
            AffairsActivitySignup.is_deleted.is_(False),
        )) or 0)
        checkins = int(db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(),
            AffairsActivitySignup.signup_status.in_(("CHECKED_IN", "CONFIRMED")),
            AffairsActivitySignup.is_deleted.is_(False),
        )) or 0)
        credit_students = int(db.scalar(select(func.count(func.distinct(AffairsActivityCredit.student_id))).where(
            AffairsActivityCredit.tenant_id == _tid(),
        )) or 0)
        by_type = {str(key or ""): int(count or 0) for key, count in type_rows}
        by_status = {str(key or ""): int(count or 0) for key, count in status_rows}
        credit_by_type = {str(key or ""): round(float(value or 0), 2) for key, value in credit_type_rows}
        credit_by_cat = {str(key or ""): round(float(value or 0), 2) for key, value in credit_category_rows}
        return {
            "totalActivities": sum(by_status.values()),
            "totalSignups": signups, "totalCheckins": checkins,
            "creditStudents": credit_students,
            "byType": [{"key": key, "count": count} for key, count in by_type.items()],
            "byStatus": [{"key": key, "count": count} for key, count in by_status.items()],
            "creditByType": [{"key": key, "value": value} for key, value in credit_by_type.items()],
            "creditByCategory": [{"key": key, "value": value} for key, value in credit_by_cat.items()],
        }

def _parse(value):
    return _parse_datetime(value)

def _vol_row(row, student=None) -> dict:
    return {
        "recordId": str(row.id), "studentId": str(row.student_id),
        "studentNo": student.student_no if student else "", "realName": student.real_name if student else "",
        "serviceName": row.service_name, "orgName": row.org_name or "",
        "hours": float(row.hours or 0), "serviceDate": _iso(row.service_date),
        "status": row.status, "statusLabel": _VOL_LABEL.get(row.status, row.status),
        "rejectReason": row.reject_reason or "", "version": int(row.version or 0),
        "allowedActions": ["CONFIRM", "REJECT"] if row.status == "PENDING" else [],
    }

def list_volunteer(user, status=None, page=1, page_size=50):
    """志愿时长补录列表：SQL 真分页、学生信息单次 JOIN。"""
    from app.models import AffairsVolunteerRecord, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 200))
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [AffairsVolunteerRecord.tenant_id == _tid(), AffairsVolunteerRecord.is_deleted.is_(False)]
        status_counts = status_counts_by_column(
            db, AffairsVolunteerRecord, AffairsVolunteerRecord.status, base_conds,
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        conds = list(base_conds) + [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if status:
            statuses = [value.strip() for value in str(status).split(",") if value.strip()]
            if len(statuses) == 1:
                conds.append(AffairsVolunteerRecord.status == statuses[0])
            elif statuses:
                conds.append(AffairsVolunteerRecord.status.in_(statuses))
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        total = int(db.scalar(select(func.count(AffairsVolunteerRecord.id)).select_from(
            AffairsVolunteerRecord).join(
                StudentProfile, StudentProfile.id == AffairsVolunteerRecord.student_id
            ).where(*conds)) or 0)
        rows = db.execute(select(AffairsVolunteerRecord, StudentProfile).join(
            StudentProfile, StudentProfile.id == AffairsVolunteerRecord.student_id
        ).where(*conds).order_by(AffairsVolunteerRecord.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_vol_row(row, student) for row, student in rows], total, status_counts


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
    """补录一条志愿时长（PENDING），金额式数值使用 Decimal 严格校验。"""
    from app.models import AffairsVolunteerRecord, StudentProfile
    raw_student_id = str(getattr(body, "studentId", None) or "")
    if not raw_student_id.isdigit():
        raise AppException("VALIDATION_ERROR", "学生ID非法")
    student_id = int(raw_student_id)
    hours = _decimal(getattr(body, "hours", None), "志愿时长")
    service_name = str(getattr(body, "serviceName", None) or "").strip()
    if not 2 <= len(service_name) <= 200:
        raise AppException("VALIDATION_ERROR", "服务名称需2-200字")
    service_date = _parse_datetime(getattr(body, "serviceDate", None))
    with session() as db:
        student = db.get(StudentProfile, student_id)
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("学生不存在")
        _vol_scope_or_403(db, student_id, user)
        row = AffairsVolunteerRecord(
            tenant_id=_tid(), student_id=student_id, service_name=service_name,
            org_name=getattr(body, "orgName", None), hours=hours, service_date=service_date,
            status="PENDING", created_by=_uid_int(user),
        )
        db.add(row); db.flush()
        _audit(db, row.id, "VOLUNTEER_CREATE", f"{service_name} {hours}h")
        db.commit(); db.refresh(row)
        return _vol_row(row, student)

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


def _cappeal_row(row, student=None) -> dict:
    return {
        "appealId": str(row.id), "studentId": str(row.student_id),
        "studentNo": student.student_no if student else "", "realName": student.real_name if student else "",
        "activityId": str(row.activity_id or ""), "appealType": row.appeal_type,
        "claimCreditType": row.claim_credit_type,
        "claimValue": float(row.claim_value) if row.claim_value is not None else None,
        "reason": row.reason or "", "status": row.status,
        "statusLabel": _L_CAPPEAL.get(row.status, row.status),
        "reviewOpinion": row.review_opinion or "", "reviewer": row.reviewer or "",
        "reviewedAt": _iso(row.reviewed_at), "version": int(row.version or 0),
        "allowedActions": ["APPROVE", "REJECT"] if row.status == "SUBMITTED" else [],
    }

def submit_credit_appeal(body, user) -> dict:
    from app.core.affairs_security import build_affairs_context
    from app.models import AffairsActivity, AffairsActivityCredit, AffairsCreditAppeal, StudentProfile
    raw_student_id = str(getattr(body, "studentId", None) or "")
    if not raw_student_id.isdigit():
        raise AppException("VALIDATION_ERROR", "学生ID非法")
    student_id = int(raw_student_id)
    appeal_type = str(getattr(body, "appealType", "MISSING") or "MISSING").upper()
    if appeal_type not in ("MISSING", "WRONG"):
        raise AppException("VALIDATION_ERROR", "申诉类型非法")
    reason = str(getattr(body, "reason", "") or "").strip()
    if not 5 <= len(reason) <= 1000:
        raise AppException("VALIDATION_ERROR", "申诉理由需5-1000字")
    credit_type = str(getattr(body, "claimCreditType", "SECOND_CLASS") or "SECOND_CLASS").upper()
    if credit_type not in CREDIT_TYPES:
        raise AppException("VALIDATION_ERROR", "主张积分类型非法")
    claim_value = _decimal(getattr(body, "claimValue", None), "主张数值")
    raw_activity_id = str(getattr(body, "activityId", None) or "")
    activity_id = int(raw_activity_id) if raw_activity_id.isdigit() else None
    with session() as db:
        context = build_affairs_context(user, db)
        context.require_student(db, student_id)
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id == student_id,
            StudentProfile.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("学生不存在")
        if str((user or {}).get("userType", "")).upper() == "STUDENT":
            from app.services.mobile_student_service import resolve_student
            current = resolve_student(db, user)
            if not current or int(current.id) != student_id:
                raise AppException("NO_PERMISSION", "学生只能提交本人的积分申诉")
        if activity_id is not None:
            activity = db.scalars(select(AffairsActivity).where(
                AffairsActivity.tenant_id == _tid(), AffairsActivity.id == activity_id,
                AffairsActivity.is_deleted.is_(False),
            )).first()
            if not activity:
                raise not_found("涉及活动不存在")
        current_value = Decimal("0")
        if activity_id is not None:
            current_value = Decimal(str(db.scalar(select(func.coalesce(func.sum(AffairsActivityCredit.credit_value), 0)).where(
                AffairsActivityCredit.tenant_id == _tid(), AffairsActivityCredit.student_id == student_id,
                AffairsActivityCredit.activity_id == activity_id,
                AffairsActivityCredit.credit_type == credit_type,
            )) or 0))
        if appeal_type == "WRONG" and current_value == 0:
            raise AppException("DATA_CONFLICT", "没有可供更正的该活动积分记录")
        if appeal_type == "MISSING" and current_value != 0:
            raise AppException("DATA_CONFLICT", "该活动已有积分，请选择记错申诉")
        duplicate_conditions = [
            AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.student_id == student_id,
            AffairsCreditAppeal.appeal_type == appeal_type, AffairsCreditAppeal.status == "SUBMITTED",
            AffairsCreditAppeal.is_deleted.is_(False),
            AffairsCreditAppeal.activity_id == activity_id if activity_id is not None else AffairsCreditAppeal.activity_id.is_(None),
        ]
        if db.scalars(select(AffairsCreditAppeal.id).where(*duplicate_conditions).limit(1)).first():
            raise AppException("DATA_CONFLICT", "该记录已有待审核申诉")
        from app.services import affairs_appeal_todo_service as appeal_todo
        appeal_todo.require_submission_assignee(db, "SECOND_CLASS_APPEAL_REVIEW", student_id)
        row = AffairsCreditAppeal(
            tenant_id=_tid(), student_id=student_id, activity_id=activity_id, appeal_type=appeal_type,
            claim_credit_type=credit_type, claim_value=claim_value, reason=reason,
            status="SUBMITTED", created_by=_uid_int(user),
        )
        db.add(row); db.flush()
        _audit(db, row.id, "CREDIT_APPEAL_SUBMIT", appeal_type)
        db.commit(); db.refresh(row)
        result = _cappeal_row(row, student)
    return appeal_todo.sync_after_submit("SECOND_CLASS_APPEAL_REVIEW", result, "appealId", "id")

def list_credit_appeals(user, status=None, page=1, page_size=50):
    from app.models import AffairsCreditAppeal, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 200))
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.is_deleted.is_(False)]
        status_counts = status_counts_by_column(
            db, AffairsCreditAppeal, AffairsCreditAppeal.status, base_conds,
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        conds = list(base_conds) + [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if status:
            statuses = [value.strip() for value in str(status).split(",") if value.strip()]
            if len(statuses) == 1:
                conds.append(AffairsCreditAppeal.status == statuses[0])
            elif statuses:
                conds.append(AffairsCreditAppeal.status.in_(statuses))
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        total = int(db.scalar(select(func.count(AffairsCreditAppeal.id)).select_from(
            AffairsCreditAppeal).join(
                StudentProfile, StudentProfile.id == AffairsCreditAppeal.student_id
            ).where(*conds)) or 0)
        rows = db.execute(select(AffairsCreditAppeal, StudentProfile).join(
            StudentProfile, StudentProfile.id == AffairsCreditAppeal.student_id
        ).where(*conds).order_by(AffairsCreditAppeal.id.desc()).offset(
            (page - 1) * page_size).limit(page_size)).all()
        return [_cappeal_row(row, student) for row, student in rows], total, status_counts


def review_credit_appeal(appeal_id, body, user) -> dict:
    """审核通过按目标值追加差额流水；驳回只改状态，原积分账永不回写。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import AffairsActivityCredit, AffairsCreditAppeal, StudentStageEvent
    action = str(getattr(body, "action", None) or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "审核动作非法")
    opinion = str(getattr(body, "opinion", None) or "").strip()
    if not 5 <= len(opinion) <= 1000:
        raise AppException("VALIDATION_ERROR", "审核意见需5-1000字")
    with session() as db:
        appeal = db.scalars(select(AffairsCreditAppeal).where(
            AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.id == int(appeal_id),
            AffairsCreditAppeal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not appeal:
            raise not_found("申诉不存在")
        student = build_affairs_context(user, db).require_student(db, int(appeal.student_id))
        if appeal.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该申诉已审核")
        atomic_claim_version(db, appeal, getattr(body, "version", None))
        result_credit_id = None
        if action == "APPROVE":
            claim = _decimal(appeal.claim_value, "主张数值")
            current = Decimal("0")
            if appeal.activity_id:
                current = Decimal(str(db.scalar(select(func.coalesce(func.sum(AffairsActivityCredit.credit_value), 0)).where(
                    AffairsActivityCredit.tenant_id == _tid(),
                    AffairsActivityCredit.student_id == int(appeal.student_id),
                    AffairsActivityCredit.activity_id == appeal.activity_id,
                    AffairsActivityCredit.credit_type == appeal.claim_credit_type,
                )) or 0))
            adjustment = claim if appeal.appeal_type == "MISSING" else claim - current
            if adjustment:
                adjustment = _decimal(adjustment, "调整数值", positive=False)
                credit = AffairsActivityCredit(
                    tenant_id=_tid(), student_id=appeal.student_id, activity_id=None,
                    credit_type=appeal.claim_credit_type, credit_value=adjustment,
                    source="MANUAL_ADJUST",
                    remark=f"积分申诉#{appeal.id}差额调整；原活动#{appeal.activity_id or '-'}；目标值{claim}",
                    created_by=_uid_int(user),
                )
                db.add(credit); db.flush()
                result_credit_id = credit.id
            appeal.status = "APPROVED"
            db.add(StudentStageEvent(
                tenant_id=_tid(), student_id=int(appeal.student_id), from_stage=None,
                to_stage="SECOND_CLASS_APPEAL_APPROVED", reason="第二课堂积分申诉已复核调整",
                source_module="student-affairs",
            ))
        else:
            appeal.status = "REJECTED"
        appeal.result_credit_id = result_credit_id
        appeal.review_opinion, appeal.reviewer = opinion, _op()[0]
        appeal.reviewed_at, appeal.version = datetime.utcnow(), int(appeal.version or 0) + 1
        _audit(db, appeal.id, "CREDIT_APPEAL_REVIEW", f"{action}:{opinion[:160]}")
        db.commit(); db.refresh(appeal)
        result = _cappeal_row(appeal, student)
    from app.services import affairs_appeal_todo_service as appeal_todo
    return appeal_todo.sync_after_review("SECOND_CLASS_APPEAL_REVIEW", int(appeal_id), result)
