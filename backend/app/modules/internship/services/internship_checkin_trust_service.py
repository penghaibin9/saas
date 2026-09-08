"""Trusted evidence helpers for student internship check-in.

The token is short lived and bound to one tenant/student/placement/day.  Location
classification stays server side and prefers the immutable placement snapshot.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.tenant_scoped import tenant_get
from app.models import InternshipBatch
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot

TOKEN_PREFIX = "ick1"
TOKEN_TTL_SECONDS = 300
DEFAULT_MAX_ACCURACY_M = 200


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(encoded: str) -> str:
    message = f"internship-checkin.v1.{encoded}".encode("ascii")
    return _b64(hmac.new(settings.jwt_secret.encode("utf-8"), message, hashlib.sha256).digest())


def issue_token(*, tenant_id: int, student_id: int, internship_id: int, checkin_date: str) -> dict:
    expires_at = int(time.time()) + TOKEN_TTL_SECONDS
    payload = {
        "tenant_id": int(tenant_id), "student_id": int(student_id),
        "internship_id": int(internship_id), "checkin_date": str(checkin_date),
        "expires_at": expires_at, "nonce": secrets.token_urlsafe(18),
    }
    encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {"token": f"{TOKEN_PREFIX}.{encoded}.{_sign(encoded)}", "expiresAt": expires_at}


def verify_token(raw_token: str, *, tenant_id: int, student_id: int,
                 internship_id: int, checkin_date: str) -> None:
    value = str(raw_token or "").strip()
    parts = value.split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise AppException("INVALID_CHECKIN_TOKEN", "打卡凭证无效，请重新定位", http_status=400)
    if not hmac.compare_digest(_sign(parts[1]), parts[2]):
        raise AppException("INVALID_CHECKIN_TOKEN", "打卡凭证校验失败，请重新定位", http_status=400)
    try:
        payload = json.loads(_unb64(parts[1]).decode("utf-8"))
        same = (
            int(payload["tenant_id"]) == int(tenant_id)
            and int(payload["student_id"]) == int(student_id)
            and int(payload["internship_id"]) == int(internship_id)
            and str(payload["checkin_date"]) == str(checkin_date)
        )
        fresh = int(payload["expires_at"]) >= int(time.time())
        nonce_ok = len(str(payload["nonce"])) >= 16
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise AppException("INVALID_CHECKIN_TOKEN", "打卡凭证内容不完整，请重新定位", http_status=400)
    if not same:
        raise AppException("INVALID_CHECKIN_TOKEN", "打卡凭证与当前学生或实习记录不匹配", http_status=403)
    if not fresh:
        raise AppException("CHECKIN_TOKEN_EXPIRED", "定位已超过 5 分钟，请重新定位后打卡", http_status=409)
    if not nonce_ok:
        raise AppException("INVALID_CHECKIN_TOKEN", "打卡凭证内容不完整，请重新定位", http_status=400)


def resolve_rule(db, record, position) -> dict:
    """Return the frozen placement rule, falling back to current position for legacy rows."""
    batch = tenant_get(db, InternshipBatch, record.batch_id) if record.batch_id else None
    batch_checkin = ((batch.rules_config or {}).get("checkin") or {}) if batch else {}
    rule = {
        "configured": bool(position and position.geofence_lat is not None
                           and position.geofence_lng is not None and position.geofence_radius_m),
        "centerLat": position.geofence_lat if position else None,
        "centerLng": position.geofence_lng if position else None,
        "radiusM": position.geofence_radius_m if position else None,
        "maxAccuracyM": int(batch_checkin.get("maxAccuracyM") or DEFAULT_MAX_ACCURACY_M),
        "coordinateSystem": "GCJ02",
        "source": "CURRENT_POSITION_LEGACY",
    }
    snapshot_id = getattr(record, "current_placement_snapshot_id", None)
    snapshot = tenant_get(db, InternshipPlacementSnapshot, snapshot_id) if snapshot_id else None
    frozen = ((snapshot.snapshot_json or {}).get("checkinRule") or {}) if snapshot else {}
    if frozen:
        rule.update({
            "centerLat": frozen.get("centerLat"), "centerLng": frozen.get("centerLng"),
            "radiusM": frozen.get("radiusM"),
            "maxAccuracyM": int(frozen.get("maxAccuracyM") or rule["maxAccuracyM"]),
            "coordinateSystem": frozen.get("coordinateSystem") or "GCJ02",
            "source": "PLACEMENT_SNAPSHOT",
        })
        rule["configured"] = all(rule.get(key) is not None for key in ("centerLat", "centerLng", "radiusM"))
    return rule


def classify_location(*, lat, lng, accuracy, rule: dict, distance_m) -> tuple[str, str | None]:
    if lat is None or lng is None:
        return "NO_LOCATION", "MISSING"
    if not rule.get("configured"):
        return "RECORDED", None
    maximum = float(rule.get("maxAccuracyM") or DEFAULT_MAX_ACCURACY_M)
    if accuracy is None or float(accuracy) > maximum:
        return "LOW_ACCURACY", "LOW_ACCURACY"
    radius = float(rule["radiusM"])
    # If the reported accuracy circle crosses the fence, a human should verify it.
    if abs(float(distance_m) - radius) <= float(accuracy):
        return "LOCATION_UNCERTAIN", "LOCATION_UNCERTAIN"
    if float(distance_m) <= radius:
        return "NORMAL", None
    return "OUT_OF_RANGE", "OUT_OF_RANGE"
