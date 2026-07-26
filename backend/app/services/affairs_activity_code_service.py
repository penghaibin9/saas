"""学生活动现场动态签到码。

采用租户 + 活动 + 5分钟时间窗的 HMAC 六位码，不把密钥或可伪造参数下发前端。
学生只在活动进行中、已报名且当前时间窗内可签到；重复签到仍由活动核心服务拒绝。
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.core.exceptions import AppException, no_permission
from app.services.db_service import _tid, session

_WINDOW_SECONDS = 300


def _code(activity_id: int, bucket: int) -> str:
    raw = f"{_tid()}:{int(activity_id)}:{int(bucket)}".encode("utf-8")
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), raw, hashlib.sha256).digest()
    value = int.from_bytes(digest[:8], "big") % 1_000_000
    return f"{value:06d}"


def issue_activity_token(activity_id: int, user: dict) -> dict:
    from app.models import AffairsActivity

    with session() as db:
        activity = db.get(AffairsActivity, int(activity_id))
        if not activity or activity.is_deleted or activity.tenant_id != _tid():
            raise AppException("DATA_NOT_FOUND", "活动不存在")
        if activity.status != "ONGOING":
            raise AppException("DATA_CONFLICT", "只有进行中的活动才能生成签到码")
    now = int(time.time())
    bucket = now // _WINDOW_SECONDS
    expires = (bucket + 1) * _WINDOW_SECONDS
    return {
        "activityId": str(activity_id),
        "activityName": activity.activity_name,
        "checkinCode": _code(activity_id, bucket),
        "expiresAt": datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
        "validSeconds": max(1, expires - now),
    }


def secure_activity_checkin(activity_id: int, credential: str, user: dict) -> dict:
    value = str(credential or "").strip()
    if not (len(value) == 6 and value.isdigit()):
        raise AppException("VALIDATION_ERROR", "请输入老师现场展示的6位动态签到码")
    bucket = int(time.time()) // _WINDOW_SECONDS
    if not hmac.compare_digest(value, _code(activity_id, bucket)):
        raise AppException("DATA_CONFLICT", "签到码无效或已过期，请向老师获取新码")

    from app.services.mobile_student_service import _require_student
    _require_student(user)
    from app.services.affairs_four_end_contract import original_activity_checkin
    original = original_activity_checkin()
    if original is None:
        raise AppException("SERVER_ERROR", "签到服务尚未初始化", http_status=503)
    return original(activity_id, user, "CODE")


def install() -> None:
    """替换四端契约层的JWT长串实现为现场可用的六位动态码。"""
    from app.services import affairs_four_end_contract as contract
    contract.issue_activity_token = issue_activity_token
    contract.secure_activity_checkin = secure_activity_checkin
