"""学生活动现场动态签到码。

采用租户 + 活动 + 5分钟时间窗的 HMAC 六位码，不把密钥或可伪造参数下发前端。
学生只在活动进行中、已报名且当前时间窗内可签到；失败尝试按学生+活动持久化限次。
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_WINDOW_SECONDS = 300
_MAX_ATTEMPTS_PER_WINDOW = 8


def _code(activity_id: int, bucket: int) -> str:
    raw = f"{_tid()}:{int(activity_id)}:{int(bucket)}".encode("utf-8")
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), raw, hashlib.sha256).digest()
    value = int.from_bytes(digest[:8], "big") % 1_000_000
    return f"{value:06d}"


def _uid_int(user) -> int | None:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else None


def _require_activity_manager(db, activity, user) -> None:
    if not has_permission(user, "studentAffairs.activity.publish"):
        raise no_permission("当前身份无权生成活动签到码")
    from app.services.affairs_activity_reliability_service import (
        _activity_matches, _teacher_scope_tokens,
    )
    tenant_all, class_tokens, college_tokens = _teacher_scope_tokens(db, user)
    if tenant_all:
        return
    uid = _uid_int(user)
    if uid and activity.publisher_id and int(activity.publisher_id) == uid:
        return
    scope_type = str(activity.scope_type or "SCHOOL").upper()
    if scope_type in ("CLASS", "COLLEGE") and _activity_matches(activity, class_tokens, college_tokens):
        return
    raise AppException("NO_DATA_SCOPE", "该活动不在你的管理范围内")


def issue_activity_token(activity_id: int, user: dict) -> dict:
    from app.models import AffairsActivity

    with session() as db:
        activity = db.get(AffairsActivity, int(activity_id))
        if not activity or activity.is_deleted or activity.tenant_id != _tid():
            raise AppException("DATA_NOT_FOUND", "活动不存在")
        _require_activity_manager(db, activity, user)
        if activity.status != "ONGOING":
            raise AppException("DATA_CONFLICT", "只有进行中的活动才能生成签到码")
        activity_name = activity.activity_name
    now = int(time.time())
    bucket = now // _WINDOW_SECONDS
    expires = (bucket + 1) * _WINDOW_SECONDS
    return {
        "activityId": str(activity_id),
        "activityName": activity_name,
        "checkinCode": _code(activity_id, bucket),
        "expiresAt": datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
        "validSeconds": max(1, expires - now),
    }


def _register_attempt(activity_id: int, user: dict, credential: str) -> None:
    """独立安全审计计数；锁活动行保证多 worker 下 count+insert 原子。"""
    from app.models import AffairsActivity, AffairsActivitySignup, SecurityAuditLog
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=_WINDOW_SECONDS)
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        activity = db.scalars(select(AffairsActivity).where(
            AffairsActivity.id == int(activity_id),
            AffairsActivity.tenant_id == _tid(),
            AffairsActivity.is_deleted.is_(False),
        ).with_for_update()).first()
        if not activity:
            raise AppException("DATA_NOT_FOUND", "活动不存在")
        signup = db.scalars(select(AffairsActivitySignup).where(
            AffairsActivitySignup.tenant_id == _tid(),
            AffairsActivitySignup.activity_id == int(activity_id),
            AffairsActivitySignup.student_id == int(student.id),
            AffairsActivitySignup.signup_status == "ENROLLED",
            AffairsActivitySignup.is_deleted.is_(False),
        )).first()
        if not signup:
            raise AppException("DATA_CONFLICT", "未报名或状态异常，不能签到")
        action = "AFFAIRS_ACTIVITY_CHECKIN_ATTEMPT"
        count = int(db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == _tid(),
            SecurityAuditLog.operator_id == int(student.id),
            SecurityAuditLog.action == action,
            SecurityAuditLog.resource_id == str(activity_id),
            SecurityAuditLog.created_at >= window_start,
        )) or 0)
        if count >= _MAX_ATTEMPTS_PER_WINDOW:
            raise AppException(
                "RATE_LIMITED",
                "签到码尝试次数过多，请稍后再试或联系现场老师",
                http_status=429,
            )
        db.add(SecurityAuditLog(
            tenant_id=_tid(), operator_id=int(student.id),
            operator_name=student.real_name or student.student_no or "学生",
            current_role="STUDENT", data_scope="SELF",
            action=action, resource="AFFAIRS_ACTIVITY", resource_id=str(activity_id),
            result="ATTEMPT", detail_json={
                "credentialSha256": hashlib.sha256(
                    str(credential or "").encode("utf-8")
                ).hexdigest(),
                "windowSeconds": _WINDOW_SECONDS,
            },
            created_by=int(student.id),
        ))
        db.commit()


def secure_activity_checkin(activity_id: int, credential: str, user: dict) -> dict:
    value = str(credential or "").strip()
    if not (len(value) == 6 and value.isdigit()):
        raise AppException("VALIDATION_ERROR", "请输入老师现场展示的6位动态签到码")
    _register_attempt(activity_id, user, value)
    bucket = int(time.time()) // _WINDOW_SECONDS
    if not hmac.compare_digest(value, _code(activity_id, bucket)):
        raise AppException("DATA_CONFLICT", "签到码无效或已过期，请向老师获取新码")

    from app.services.affairs_four_end_contract import original_activity_checkin
    original = original_activity_checkin()
    if original is None:
        raise AppException("SERVER_ERROR", "签到服务尚未初始化", http_status=503)
    return original(activity_id, user, "CODE")


def install() -> None:
    """替换四端契约层的JWT长串实现为现场可用、限次的六位动态码。"""
    from app.services import affairs_four_end_contract as contract
    contract.issue_activity_token = issue_activity_token
    contract.secure_activity_checkin = secure_activity_checkin
