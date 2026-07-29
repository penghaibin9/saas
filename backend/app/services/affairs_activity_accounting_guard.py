"""活动与第二课堂安全门：范围、日期、DTO动作、志愿version与append-only差额冲正。"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

_INSTALLED = False
_MAX_CREDIT = Decimal("9999.99")


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
    name = str(getattr(body, "activityName", None) if getattr(body, "activityName", None) is not None
               else getattr(activity, "activity_name", "") or "").strip()
    if not 2 <= len(name) <= 200:
        raise AppException("VALIDATION_ERROR", "活动名称需2-200字")
    activity_type = str(getattr(body, "activityType", None) or getattr(activity, "activity_type", "ACTIVITY")).upper()
    if activity_type not in ("ACTIVITY", "VOLUNTEER", "LECTURE", "COMPETITION", "PRACTICE"):
        raise AppException("VALIDATION_ERROR", "活动类型非法")
    start = _parse_datetime(getattr(body, "startAt", None)) if getattr(body, "startAt", None) is not None else getattr(activity, "start_at", None)
    end = _parse_datetime(getattr(body, "endAt", None)) if getattr(body, "endAt", None) is not None else getattr(activity, "end_at", None)
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
    credit_type = getattr(body, "creditType", None) if getattr(body, "creditType", None) is not None else getattr(activity, "credit_type", None)
    credit_value = getattr(body, "creditValue", None) if getattr(body, "creditValue", None) is not None else getattr(activity, "credit_value", None)
    if credit_type and str(credit_type).upper() not in ("SECOND_CLASS", "MORAL", "VOLUNTEER_HOUR"):
        raise AppException("VALIDATION_ERROR", "积分类型非法")
    if credit_value not in (None, ""):
        _decimal(credit_value, "积分值")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import (
        AffairsActivity, AffairsActivityCredit, AffairsActivitySignup, AffairsCreditAppeal,
        AffairsCreditCategory, AffairsVolunteerRecord, StudentProfile, StudentStageEvent,
    )
    from app.services import affairs_activity_reliability_service as reliability
    from app.services import affairs_activity_service as activity

    old_row = activity._row
    old_create = activity.create_activity
    old_publish = activity.publish_activity
    old_category = activity.create_category

    def activity_row(row, signup_count=None, checkin_count=None):
        data = old_row(row, signup_count, checkin_count)
        data["allowedActions"] = {
            "DRAFT": ["PUBLISH", "CANCEL", "EDIT"],
            "PUBLISHED": ["ENROLL_CLOSE", "CANCEL"],
            "ENROLL_CLOSED": ["START", "CANCEL"],
            "ONGOING": ["FINISH"],
            "FINISHED": ["CONFIRM"],
            "CONFIRMED": ["UNCONFIRM", "ARCHIVE"],
        }.get(row.status, [])
        return data

    def volunteer_row(row, student=None):
        data = {
            "recordId": str(row.id), "studentId": str(row.student_id),
            "studentNo": student.student_no if student else "", "realName": student.real_name if student else "",
            "serviceName": row.service_name, "orgName": row.org_name or "",
            "hours": float(row.hours or 0), "serviceDate": activity._iso(row.service_date),
            "status": row.status, "statusLabel": activity._VOL_LABEL.get(row.status, row.status),
            "rejectReason": row.reject_reason or "", "version": int(row.version or 0),
            "allowedActions": ["CONFIRM", "REJECT"] if row.status == "PENDING" else [],
        }
        return data

    def appeal_row(row, student=None):
        return {
            "appealId": str(row.id), "studentId": str(row.student_id),
            "studentNo": student.student_no if student else "", "realName": student.real_name if student else "",
            "activityId": str(row.activity_id or ""), "appealType": row.appeal_type,
            "claimCreditType": row.claim_credit_type,
            "claimValue": float(row.claim_value) if row.claim_value is not None else None,
            "reason": row.reason or "", "status": row.status,
            "statusLabel": activity._L_CAPPEAL.get(row.status, row.status),
            "reviewOpinion": row.review_opinion or "", "reviewer": row.reviewer or "",
            "reviewedAt": activity._iso(row.reviewed_at), "version": int(row.version or 0),
            "allowedActions": ["APPROVE", "REJECT"] if row.status == "SUBMITTED" else [],
        }

    def create_activity(body, user):
        _validate_activity_body(body)
        for field in ("startAt", "endAt", "enrollDeadline"):
            value = getattr(body, field, None)
            if value not in (None, ""):
                setattr(body, field, _parse_datetime(value).strftime("%Y-%m-%d %H:%M:%S"))
        if getattr(body, "creditValue", None) not in (None, ""):
            body.creditValue = _decimal(body.creditValue, "积分值")
        return old_create(body, user)

    def update_activity(activity_id, body, user):
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
            activity.atomic_claim_version(db, row, int(row.version or 0) if expected is None else expected)
            _validate_activity_body(body, row)
            mapping = {
                "activity_name": "activityName", "location": "location", "description": "description",
                "scope_type": "scopeType", "scope_ref": "scopeRef", "credit_type": "creditType",
                "category_code": "categoryCode",
            }
            for attr, key in mapping.items():
                value = getattr(body, key, None)
                if value is not None:
                    setattr(row, attr, value)
            for attr, key in (("start_at", "startAt"), ("end_at", "endAt"), ("enroll_deadline", "enrollDeadline")):
                value = getattr(body, key, None)
                if value is not None:
                    setattr(row, attr, _parse_datetime(value))
            if getattr(body, "quota", None) is not None:
                row.quota = int(body.quota)
            if getattr(body, "creditValue", None) is not None:
                row.credit_value = _decimal(body.creditValue, "积分值")
            row.version = int(row.version or 0) + 1
            activity._audit(db, row.id, "ACTIVITY_UPDATE")
            db.commit(); db.refresh(row)
            return activity_row(row)

    def publish_activity(activity_id, user, action="PUBLISH", reason="", expected_version=None):
        if str(action or "").upper() == "PUBLISH":
            with session() as db:
                row = activity._load(db, activity_id)
                _validate_activity_body(type("Snapshot", (), {
                    "activityName": row.activity_name, "activityType": row.activity_type,
                    "startAt": row.start_at, "endAt": row.end_at, "enrollDeadline": row.enroll_deadline,
                    "quota": row.quota, "creditType": row.credit_type, "creditValue": row.credit_value,
                })(), row)
        return old_publish(activity_id, user, action, reason, expected_version)

    def require_activity_scope(db, row, user):
        tenant_all, class_tokens, college_tokens = reliability._teacher_scope_tokens(db, user)
        if not tenant_all and not reliability._activity_matches(row, class_tokens, college_tokens):
            raise AppException("NO_DATA_SCOPE", "该活动不在您的数据范围内")

    def list_participants(activity_id, user):
        with session() as db:
            row = activity._load(db, activity_id)
            require_activity_scope(db, row, user)
            signups = db.execute(select(AffairsActivitySignup, StudentProfile).join(
                StudentProfile, StudentProfile.id == AffairsActivitySignup.student_id,
            ).where(
                AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == row.id,
                AffairsActivitySignup.is_deleted.is_(False), StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ).order_by(AffairsActivitySignup.id)).all()
            return [{
                "signupId": str(signup.id), "studentId": str(signup.student_id),
                "studentNo": student.student_no or "", "realName": student.real_name or "",
                "signupStatus": signup.signup_status, "enrolledAt": activity._iso(signup.enrolled_at),
                "checkinAt": activity._iso(signup.checkin_at), "version": int(signup.version or 0),
            } for signup, student in signups]

    def student_report(student_id, user):
        from app.core.affairs_security import build_affairs_context
        sid = int(student_id)
        with session() as db:
            student = build_affairs_context(user, db).require_student(db, sid)
            rows = db.scalars(select(AffairsActivityCredit).where(
                AffairsActivityCredit.tenant_id == _tid(), AffairsActivityCredit.student_id == sid,
            ).order_by(AffairsActivityCredit.id.desc())).all()
            categories = db.scalars(select(AffairsCreditCategory).where(
                AffairsCreditCategory.tenant_id == _tid(), AffairsCreditCategory.is_deleted.is_(False),
            )).all()
            weights = {row.category_code: Decimal(str(row.weight or 1)) for row in categories}
            by_type, by_category = {}, {}
            for row in rows:
                value = Decimal(str(row.credit_value or 0))
                by_type[row.credit_type] = by_type.get(row.credit_type, Decimal("0")) + value
                if row.category_code:
                    by_category[row.category_code] = by_category.get(row.category_code, Decimal("0")) + value
            weighted = {key: value * weights.get(key, Decimal("1")) for key, value in by_category.items()}
            return {
                "studentId": str(sid), "realName": student.real_name or "", "studentNo": student.student_no or "",
                "byType": [{"key": key, "value": float(value)} for key, value in by_type.items()],
                "byCategory": [{"key": key, "value": float(value)} for key, value in by_category.items()],
                "byCategoryWeighted": [{"key": key, "value": float(value), "weight": float(weights.get(key, 1)),
                                        "rawValue": float(by_category[key])} for key, value in weighted.items()],
                "rawTotal": float(sum(by_category.values(), Decimal("0"))),
                "weightedTotal": float(sum(weighted.values(), Decimal("0"))),
                "items": [{"activityId": str(row.activity_id or ""), "creditType": row.credit_type,
                           "creditValue": float(row.credit_value or 0), "categoryCode": row.category_code or "",
                           "source": row.source, "remark": row.remark or "", "grantedAt": activity._iso(row.granted_at)}
                          for row in rows],
            }

    def create_volunteer(body, user):
        body.hours = _decimal(getattr(body, "hours", None), "志愿时长")
        name = str(getattr(body, "serviceName", None) or "").strip()
        if not 2 <= len(name) <= 200:
            raise AppException("VALIDATION_ERROR", "服务名称需2-200字")
        body.serviceName = name
        if getattr(body, "serviceDate", None):
            body.serviceDate = _parse_datetime(body.serviceDate).strftime("%Y-%m-%d %H:%M:%S")
        # 复用原函数的学生存在性、范围和事务。
        original = old_create_volunteer
        return original(body, user)

    def submit_credit_appeal(body, user):
        appeal_type = str(getattr(body, "appealType", "MISSING") or "MISSING").upper()
        if appeal_type not in ("MISSING", "WRONG"):
            raise AppException("VALIDATION_ERROR", "申诉类型非法")
        reason = str(getattr(body, "reason", None) or "").strip()
        if not 5 <= len(reason) <= 1000:
            raise AppException("VALIDATION_ERROR", "申诉理由需5-1000字")
        credit_type = str(getattr(body, "claimCreditType", "SECOND_CLASS") or "SECOND_CLASS").upper()
        if credit_type not in activity.CREDIT_TYPES:
            raise AppException("VALIDATION_ERROR", "主张积分类型非法")
        claim = _decimal(getattr(body, "claimValue", None), "主张数值")
        raw_sid = str(getattr(body, "studentId", None) or "")
        if not raw_sid.isdigit():
            raise AppException("VALIDATION_ERROR", "学生ID非法")
        sid = int(raw_sid)
        activity_id = int(body.activityId) if str(getattr(body, "activityId", None) or "").isdigit() else None
        from app.core.affairs_security import build_affairs_context
        with session() as db:
            student = build_affairs_context(user, db).require_student(db, sid)
            if (user or {}).get("userType", "").upper() == "STUDENT":
                from app.services.mobile_student_service import resolve_student
                me = resolve_student(db, user)
                if not me or int(me.id) != sid:
                    raise AppException("NO_PERMISSION", "学生只能提交本人的积分申诉")
            if activity_id:
                related = db.scalars(select(AffairsActivity).where(
                    AffairsActivity.tenant_id == _tid(), AffairsActivity.id == activity_id,
                    AffairsActivity.is_deleted.is_(False),
                )).first()
                if not related:
                    raise not_found("涉及活动不存在")
            duplicate = db.scalars(select(AffairsCreditAppeal.id).where(
                AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.student_id == sid,
                AffairsCreditAppeal.activity_id == activity_id, AffairsCreditAppeal.appeal_type == appeal_type,
                AffairsCreditAppeal.status == "SUBMITTED", AffairsCreditAppeal.is_deleted.is_(False),
            )).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "该记录已有待审核申诉")
            existing = Decimal(str(db.scalar(select(func.coalesce(func.sum(AffairsActivityCredit.credit_value), 0)).where(
                AffairsActivityCredit.tenant_id == _tid(), AffairsActivityCredit.student_id == sid,
                AffairsActivityCredit.activity_id == activity_id,
                AffairsActivityCredit.credit_type == credit_type,
            )) or 0)) if activity_id else Decimal("0")
            if appeal_type == "WRONG" and existing == 0:
                raise AppException("DATA_CONFLICT", "没有可供更正的该活动积分记录")
            if appeal_type == "MISSING" and existing != 0:
                raise AppException("DATA_CONFLICT", "该活动已有积分，请选择记错申诉")
            row = AffairsCreditAppeal(
                tenant_id=_tid(), student_id=sid, activity_id=activity_id, appeal_type=appeal_type,
                claim_credit_type=credit_type, claim_value=claim, reason=reason,
                status="SUBMITTED", created_by=activity._uid_int(user),
            )
            db.add(row); db.flush()
            activity._audit(db, row.id, "CREDIT_APPEAL_SUBMIT", appeal_type)
            db.commit(); db.refresh(row)
            return appeal_row(row, student)

    def review_credit_appeal(appeal_id, body, user):
        action = str(getattr(body, "action", None) or "").upper()
        if action not in ("APPROVE", "REJECT"):
            raise AppException("VALIDATION_ERROR", "审核动作非法")
        opinion = str(getattr(body, "opinion", None) or "").strip()
        if not 5 <= len(opinion) <= 1000:
            raise AppException("VALIDATION_ERROR", "审核意见需5-1000字")
        from app.core.affairs_security import build_affairs_context
        with session() as db:
            appeal = db.get(AffairsCreditAppeal, int(appeal_id))
            if not appeal or appeal.is_deleted or appeal.tenant_id != _tid():
                raise not_found("申诉不存在")
            student = build_affairs_context(user, db).require_student(db, int(appeal.student_id))
            if appeal.status != "SUBMITTED":
                raise AppException("DATA_CONFLICT", "该申诉已审核")
            activity.atomic_claim_version(db, appeal, getattr(body, "version", None))
            result_credit_id = None
            if action == "APPROVE":
                claim = _decimal(appeal.claim_value, "主张数值")
                current = Decimal(str(db.scalar(select(func.coalesce(func.sum(AffairsActivityCredit.credit_value), 0)).where(
                    AffairsActivityCredit.tenant_id == _tid(),
                    AffairsActivityCredit.student_id == int(appeal.student_id),
                    AffairsActivityCredit.activity_id == appeal.activity_id,
                    AffairsActivityCredit.credit_type == appeal.claim_credit_type,
                )) or 0)) if appeal.activity_id else Decimal("0")
                adjustment = claim if appeal.appeal_type == "MISSING" else claim - current
                if adjustment:
                    adjustment = _decimal(adjustment, "调整数值", positive=False)
                    credit = AffairsActivityCredit(
                        tenant_id=_tid(), student_id=appeal.student_id, activity_id=None,
                        credit_type=appeal.claim_credit_type, credit_value=adjustment,
                        source="MANUAL_ADJUST", remark=(
                            f"积分申诉#{appeal.id}差额调整；原活动#{appeal.activity_id or '-'}；目标值{claim}"
                        ), created_by=activity._uid_int(user),
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
            appeal.review_opinion, appeal.reviewer = opinion, activity._op()[0]
            appeal.reviewed_at, appeal.version = datetime.utcnow(), int(appeal.version or 0) + 1
            activity._audit(db, appeal.id, "CREDIT_APPEAL_REVIEW", f"{action}:{opinion[:160]}")
            db.commit(); db.refresh(appeal)
            return appeal_row(appeal, student)

    def unconfirm_activity(activity_id, user, reason="", expected_version=None):
        reason = str(reason or "").strip()
        if not 5 <= len(reason) <= 500:
            raise AppException("VALIDATION_ERROR", "撤销原因需5-500字")
        with session() as db:
            row = activity._load(db, activity_id)
            if row.status != "CONFIRMED":
                raise AppException("DATA_CONFLICT", "仅已确认活动可撤销")
            activity.atomic_claim_version(db, row, expected_version)
            credits = db.scalars(select(AffairsActivityCredit).where(
                AffairsActivityCredit.tenant_id == _tid(), AffairsActivityCredit.activity_id == row.id,
                AffairsActivityCredit.source == "ACTIVITY",
            )).all()
            for credit in credits:
                reversal = _decimal(-Decimal(str(credit.credit_value or 0)), "冲正数值", positive=False)
                db.add(AffairsActivityCredit(
                    tenant_id=_tid(), student_id=credit.student_id, activity_id=None,
                    credit_type=credit.credit_type, credit_value=reversal,
                    category_code=credit.category_code, source="MANUAL_ADJUST",
                    remark=f"活动#{row.id}撤销确认冲正；原流水#{credit.id}；原因：{reason}",
                    created_by=activity._uid_int(user),
                ))
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(credit.student_id), from_stage=None,
                    to_stage="ACTIVITY_UNCONFIRMED", reason=f"活动《{row.activity_name}》积分已撤销",
                    source_module="student-affairs",
                ))
            for signup in db.scalars(select(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(), AffairsActivitySignup.activity_id == row.id,
                AffairsActivitySignup.signup_status == "CONFIRMED", AffairsActivitySignup.is_deleted.is_(False),
            )).all():
                signup.signup_status = "CHECKED_IN"
                signup.version = int(signup.version or 0) + 1
            row.status, row.confirm_at = "FINISHED", None
            row.version = int(row.version or 0) + 1
            activity._audit(db, row.id, "ACTIVITY_UNCONFIRM", reason)
            db.commit(); db.refresh(row)
            return activity_row(row)

    def create_category(body, user):
        code = str(getattr(body, "categoryCode", None) or "").strip().upper()
        name = str(getattr(body, "categoryName", None) or "").strip()
        if not 2 <= len(code) <= 50 or not 2 <= len(name) <= 100:
            raise AppException("VALIDATION_ERROR", "类目编码需2-50字符，名称需2-100字")
        credit_type = str(getattr(body, "creditType", None) or "").upper()
        if credit_type and credit_type not in activity.CREDIT_TYPES:
            raise AppException("VALIDATION_ERROR", "类目积分类型非法")
        weight = Decimal(str(getattr(body, "weight", 1) or 1))
        if weight <= 0 or weight > Decimal("100") or weight.as_tuple().exponent < -2:
            raise AppException("VALIDATION_ERROR", "类目权重应大于0、不超过100且最多2位小数")
        body.categoryCode, body.categoryName = code, name
        body.creditType, body.weight = credit_type or None, weight
        return old_category(body, user)

    old_create_volunteer = activity.create_volunteer
    activity._parse = _parse_datetime
    activity._row = activity_row
    activity._vol_row = volunteer_row
    activity._cappeal_row = appeal_row
    activity.create_activity = create_activity
    activity.update_activity = update_activity
    activity.publish_activity = publish_activity
    activity.list_participants = list_participants
    activity.student_report = student_report
    activity.create_volunteer = create_volunteer
    activity.submit_credit_appeal = submit_credit_appeal
    activity.review_credit_appeal = review_credit_appeal
    activity.unconfirm_activity = unconfirm_activity
    activity.create_category = create_category
    _INSTALLED = True
