"""O5 signed, one-time orientation check-in credential and现场确认 service."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.timeutil import local_today_bounds_utc
from app.models import (
    DormBed,
    DormBuilding,
    DormRoom,
    DormStay,
    OrientationBatch,
    OrientationCheckinPoint,
    OrientationCheckinRecord,
    OrientationCheckinToken,
    OrientationStudent,
    RoleAssignmentScope,
    StudentProfile,
)
from app.services.db_service import _iso, _tid, session
from app.services.message_identity import resolve_message_user_id

TOKEN_PREFIX = "oci1"
TOKEN_TTL_MINUTES = 10


def _actor_id(user=None) -> int | None:
    actor_id = resolve_message_user_id(user or get_current_user_ctx() or {})
    return actor_id if actor_id > 0 else None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(encoded_payload: str) -> str:
    message = f"orientation-checkin.v1.{encoded_payload}".encode("ascii")
    return _b64(hmac.new(settings.jwt_secret.encode("utf-8"), message, hashlib.sha256).digest())


def _encode(payload: dict) -> str:
    encoded = _b64(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
    return f"{TOKEN_PREFIX}.{encoded}.{_sign(encoded)}"


def _decode(raw_token: str) -> dict:
    value = str(raw_token or "").strip()
    if len(value) < 80 or len(value) > 2048:
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证格式不正确", http_status=400)
    parts = value.split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证格式不正确", http_status=400)
    expected = _sign(parts[1])
    if not hmac.compare_digest(expected, parts[2]):
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证签名校验失败", http_status=400)
    try:
        payload = json.loads(_unb64(parts[1]).decode("utf-8"))
        normalized = {
            "tenant_id": int(payload["tenant_id"]),
            "batch_id": int(payload["batch_id"]),
            "orientation_student_id": int(payload["orientation_student_id"]),
            "nonce": str(payload["nonce"]),
            "expires_at": int(payload["expires_at"]),
        }
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证载荷不完整", http_status=400)
    if normalized["tenant_id"] <= 0 or normalized["batch_id"] <= 0:
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证载荷不正确", http_status=400)
    if normalized["orientation_student_id"] <= 0 or len(normalized["nonce"]) < 24:
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证载荷不正确", http_status=400)
    return normalized


def _nonce_hash(nonce: str) -> str:
    return hashlib.sha256(str(nonce).encode("utf-8")).hexdigest()


def _qr_data_url(token: str) -> tuple[str, str]:
    """Render locally; never send the credential to a third-party QR service."""
    try:
        import qrcode
        image = qrcode.make(
            token,
            box_size=5,
            border=3,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
        )
        output = io.BytesIO()
        image.save(output, format="PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii"), "READY"
    except ImportError:
        return "", "RENDERER_UNAVAILABLE"


def _self_orientation_student(db, user) -> OrientationStudent:
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    profile = resolve_student(db, user)
    if not profile:
        raise not_found("尚未建立你的稳定学生档案")
    row = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == _tid(),
        OrientationStudent.student_id == profile.id,
        OrientationStudent.record_status == "ACTIVE",
        OrientationStudent.is_deleted.is_(False),
    ).order_by(OrientationStudent.id.desc())).first()
    if not row:
        raise not_found("你暂无有效迎新报到记录")
    return row


def token_status(db, student: OrientationStudent, *, qualification: dict | None = None) -> dict:
    from app.services.orientation_qualification_service import evaluate

    decision = qualification or evaluate(db, student)
    latest = db.scalars(select(OrientationCheckinToken).where(
        OrientationCheckinToken.tenant_id == student.tenant_id,
        OrientationCheckinToken.orientation_student_id == student.id,
        OrientationCheckinToken.is_deleted.is_(False),
    ).order_by(OrientationCheckinToken.id.desc())).first()
    finalized = student.stage == "ENROLLED" or student.report_status == "COLLEGE_CONFIRMED"
    checked = student.report_status in ("CHECKED_IN", "COLLEGE_CONFIRMED")
    checkin_eligibility = decision.get("checkinEligibility") or {}
    can_issue = bool(checkin_eligibility.get("eligible")) and not checked and not finalized
    status = "FINALIZED" if finalized else "CHECKED_IN" if checked else "ELIGIBLE" if can_issue else "BLOCKED"
    active_issued = bool(
        latest and latest.status == "ISSUED"
        and latest.expires_at > datetime.utcnow() and can_issue
    )
    if active_issued:
        status = "ISSUED"
    return {
        "status": status,
        "canIssue": can_issue,
        "expiresAt": _iso(latest.expires_at) if active_issued else None,
        "note": (
            "学院已完成入学确认" if finalized else
            "已完成现场报到，等待学院确认" if checked else
            "可签发一次性报到凭证；学校办理事项不影响到校核验" if can_issue else
            "请先完成身份与个人信息核验"
        ),
    }


def issue_for_student(user: dict) -> dict:
    from app.services.orientation_qualification_service import evaluate
    from app.services.orientation_service import _audit

    with session() as db:
        student = _self_orientation_student(db, user)
        student = db.scalars(select(OrientationStudent).where(
            OrientationStudent.id == student.id,
            OrientationStudent.tenant_id == _tid(),
        ).with_for_update()).first()
        decision = evaluate(db, student)
        status = token_status(db, student, qualification=decision)
        if not status["canIssue"]:
            raise AppException(
                "ORIENTATION_NOT_QUALIFIED",
                status["note"],
                http_status=409,
                details={"verdict": decision.get("verdict"), "blockers": decision.get("blockers", [])},
            )
        batch = db.get(OrientationBatch, int(student.batch_id))
        # MySQL DATETIME(0) may round fractional seconds.  Sign exactly the same
        # second that is persisted so a token issued in the upper half-second
        # can never fail its own record-consistency check.
        now = datetime.utcnow().replace(microsecond=0)
        if (
            not batch or batch.is_deleted or int(batch.tenant_id) != int(_tid())
            or batch.status != "ACTIVE"
        ):
            raise AppException("INVALID_STATE", "迎新批次当前未开放", http_status=409)
        if batch.report_start_date and now < batch.report_start_date:
            raise AppException("INVALID_STATE", "现场报到尚未开始", http_status=409)
        if batch.report_end_date and now > batch.report_end_date:
            raise AppException("INVALID_STATE", "现场报到已结束", http_status=409)
        prior = list(db.scalars(select(OrientationCheckinToken).where(
            OrientationCheckinToken.tenant_id == _tid(),
            OrientationCheckinToken.orientation_student_id == student.id,
            OrientationCheckinToken.status == "ISSUED",
            OrientationCheckinToken.is_deleted.is_(False),
        ).with_for_update()).all())
        for item in prior:
            item.status = "EXPIRED" if item.expires_at <= now else "REVOKED"
            item.version = int(item.version or 0) + 1
        nonce = secrets.token_urlsafe(32)
        expires = now + timedelta(minutes=TOKEN_TTL_MINUTES)
        row = OrientationCheckinToken(
            tenant_id=_tid(), batch_id=student.batch_id,
            orientation_student_id=student.id, nonce_hash=_nonce_hash(nonce),
            expires_at=expires, issued_at=now, issued_by=_actor_id(user), status="ISSUED",
        )
        db.add(row)
        db.flush()
        payload = {
            "tenant_id": int(_tid()),
            "batch_id": int(student.batch_id),
            "orientation_student_id": int(student.id),
            "nonce": nonce,
            "expires_at": int(expires.replace(tzinfo=timezone.utc).timestamp()),
        }
        token = _encode(payload)
        qr, qr_status = _qr_data_url(token)
        _audit(db, "CHECKIN", student.id, "签发一次性现场报到凭证", f"有效期 {TOKEN_TTL_MINUTES} 分钟")
        db.commit()
        return {
            "token": token,
            "qrDataUrl": qr,
            "qrStatus": qr_status,
            "expiresAt": _iso(expires),
            "ttlSeconds": TOKEN_TTL_MINUTES * 60,
            "student": {"name": student.name, "admissionNo": student.admission_no},
        }


def _load_token(db, raw_token: str, *, for_update: bool = False):
    claims = _decode(raw_token)
    if claims["tenant_id"] != int(_tid()):
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证不属于当前学校", http_status=400)
    query = select(OrientationCheckinToken).where(
        OrientationCheckinToken.tenant_id == _tid(),
        OrientationCheckinToken.nonce_hash == _nonce_hash(claims["nonce"]),
        OrientationCheckinToken.is_deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    row = db.scalars(query).first()
    if not row:
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证不存在或已撤销", http_status=400)
    if (
        int(row.batch_id) != claims["batch_id"]
        or int(row.orientation_student_id) != claims["orientation_student_id"]
        or int(row.expires_at.replace(tzinfo=timezone.utc).timestamp()) != claims["expires_at"]
    ):
        raise AppException("INVALID_CHECKIN_TOKEN", "报到凭证与签发记录不一致", http_status=400)
    # A consumed credential is a transaction receipt as well as a one-time secret.
    # Allow confirm retries to return the existing record even after the original
    # credential expires; an unconsumed credential still fails closed at expiry.
    if datetime.utcnow() >= row.expires_at and row.status != "CONSUMED":
        raise AppException("CHECKIN_TOKEN_EXPIRED", "报到凭证已过期，请学生刷新后重试", http_status=409)
    return claims, row


def _dorm_projection(db, student: OrientationStudent) -> dict:
    if not student.student_id:
        return {"status": "UNLINKED", "label": "尚未绑定学生主档"}
    stay = db.scalars(select(DormStay).where(
        DormStay.tenant_id == _tid(), DormStay.student_id == student.student_id,
        DormStay.status.in_(("RESERVED", "ACTIVE")), DormStay.is_deleted.is_(False),
    ).order_by(DormStay.id.desc())).first()
    if not stay:
        return {"status": "UNASSIGNED", "label": "未分配宿舍"}
    bed = db.scalars(select(DormBed).where(
        DormBed.id == int(stay.bed_id), DormBed.tenant_id == _tid(),
        DormBed.is_deleted.is_(False),
    )).first()
    room = db.scalars(select(DormRoom).where(
        DormRoom.id == int(stay.room_id), DormRoom.tenant_id == _tid(),
        DormRoom.is_deleted.is_(False),
    )).first()
    building = db.scalars(select(DormBuilding).where(
        DormBuilding.id == int(stay.building_id), DormBuilding.tenant_id == _tid(),
        DormBuilding.is_deleted.is_(False),
    )).first()
    return {
        "status": stay.status,
        "label": " / ".join(x for x in (
            building.building_name if building else "",
            room.room_no if room else "",
            f"{bed.bed_no}床" if bed else "",
        ) if x) or "住宿信息待核查",
        "buildingId": str(stay.building_id),
        "roomId": str(stay.room_id),
        "bedId": str(stay.bed_id),
    }


def preflight(raw_token: str, user: dict) -> dict:
    from app.services.orientation_qualification_service import evaluate
    from app.services.orientation_service import assert_orientation_student_scope

    with session() as db:
        _claims, token_row = _load_token(db, raw_token)
        if token_row.status != "ISSUED":
            raise AppException("CHECKIN_TOKEN_USED", "报到凭证已使用或已撤销", http_status=409)
        student = db.get(OrientationStudent, int(token_row.orientation_student_id))
        if not student or student.is_deleted or int(student.tenant_id) != int(_tid()):
            raise not_found("报到凭证对应的新生记录不存在")
        assert_orientation_student_scope(db, student, user)
        decision = evaluate(db, student)
        if not (decision.get("checkinEligibility") or {}).get("eligible"):
            raise AppException(
                "ORIENTATION_QUALIFICATION_CHANGED",
                "学生身份或个人信息状态已变化，请先处理阻断项",
                http_status=409,
                details={"verdict": decision["verdict"], "blockers": decision["blockers"]},
            )
        return {
            "tokenId": str(token_row.id),
            "expiresAt": _iso(token_row.expires_at),
            "student": {
                "id": str(student.id), "name": student.name,
                "admissionNo": student.admission_no,
                "collegeName": student.college_name or "",
                "majorName": student.major_name or "",
                "className": student.class_name or "",
                "reportStatus": student.report_status,
            },
            "qualification": decision,
            "dorm": _dorm_projection(db, student),
            "canConfirm": True,
        }


def _point_scope(db, user) -> tuple[bool, set[int]]:
    uid = _actor_id(user)
    if not uid:
        return False, set()
    now = datetime.utcnow()
    rows = list(db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == _tid(),
        RoleAssignmentScope.user_id == uid,
        RoleAssignmentScope.status == "ACTIVE",
        RoleAssignmentScope.is_deleted.is_(False),
        RoleAssignmentScope.effective_at <= now,
        or_(RoleAssignmentScope.expires_at.is_(None), RoleAssignmentScope.expires_at > now),
        RoleAssignmentScope.scope_type.in_(("SCHOOL", "CHECKIN_POINT")),
    )).all())
    school = any(row.scope_type == "SCHOOL" for row in rows)
    return school, {int(row.scope_id) for row in rows if row.scope_type == "CHECKIN_POINT"}


def list_teacher_points(user: dict) -> dict:
    from app.services.mobile_teacher_service import _require_teacher

    _require_teacher(user)
    with session() as db:
        school, point_ids = _point_scope(db, user)
        query = select(OrientationCheckinPoint).where(
            OrientationCheckinPoint.tenant_id == _tid(),
            OrientationCheckinPoint.status == "ENABLED",
            OrientationCheckinPoint.is_deleted.is_(False),
        )
        # Explicit CHECKIN_POINT assignments narrow the list; legacy class/college roles keep
        # their student scope until a point assignment is configured.
        if point_ids and not school:
            query = query.where(OrientationCheckinPoint.id.in_(point_ids))
        rows = list(db.scalars(query.order_by(OrientationCheckinPoint.id)).all())
        return {
            "items": [{"id": str(row.id), "name": row.name, "location": row.location or ""} for row in rows],
            "total": len(rows),
            "scopeMode": "SCHOOL" if school else "CHECKIN_POINT" if point_ids else "STUDENT_SCOPE_COMPAT",
        }


def _assert_point(db, point_id, user) -> OrientationCheckinPoint:
    try:
        pid = int(point_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "请选择现场报到点")
    point = db.get(OrientationCheckinPoint, pid)
    if not point or point.is_deleted or point.status != "ENABLED" or int(point.tenant_id) != int(_tid()):
        raise not_found("现场报到点不存在或已停用")
    school, point_ids = _point_scope(db, user)
    if point_ids and not school and pid not in point_ids:
        raise AppException("NO_DATA_SCOPE", "当前账号未获授权使用该现场报到点", http_status=403)
    return point


def _record_payload(db, record: OrientationCheckinRecord) -> dict:
    student = db.get(OrientationStudent, int(record.orientation_student_id))
    point = db.get(OrientationCheckinPoint, int(record.checkin_point_id))
    return {
        "id": str(record.id),
        "studentId": str(record.orientation_student_id),
        "name": student.name if student else "",
        "className": student.class_name if student else "",
        "collegeName": student.college_name if student else "",
        "checkinPointId": str(record.checkin_point_id),
        "checkinPointName": point.name if point else "",
        "reportStatus": student.report_status if student else "CHECKED_IN",
        "checkinTime": _iso(record.checked_in_at),
        "idempotent": False,
    }


def confirm(raw_token: str, checkin_point_id, user: dict) -> dict:
    from app.services.orientation_flow_service import set_student_step_status
    from app.services.orientation_qualification_service import evaluate
    from app.services.orientation_service import _audit, assert_orientation_student_scope

    actor_id = _actor_id(user)
    if not actor_id:
        raise AppException("NO_PERMISSION", "无法识别现场核验教师账号", http_status=403)
    with session() as db:
        _claims, token_row = _load_token(db, raw_token, for_update=True)
        if token_row.status == "CONSUMED" and token_row.checkin_record_id:
            existing = db.get(OrientationCheckinRecord, int(token_row.checkin_record_id))
            if existing and not existing.is_deleted:
                result = _record_payload(db, existing)
                result["idempotent"] = True
                return result
        if token_row.status != "ISSUED":
            raise AppException("CHECKIN_TOKEN_USED", "报到凭证已使用或已撤销", http_status=409)
        student = db.scalars(select(OrientationStudent).where(
            OrientationStudent.id == token_row.orientation_student_id,
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("报到凭证对应的新生记录不存在")
        assert_orientation_student_scope(db, student, user)
        point = _assert_point(db, checkin_point_id, user)
        prior = db.scalars(select(OrientationCheckinRecord).where(
            OrientationCheckinRecord.tenant_id == _tid(),
            OrientationCheckinRecord.orientation_student_id == student.id,
            OrientationCheckinRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if prior:
            raise AppException("ORIENTATION_ALREADY_CHECKED_IN", "该生已完成现场报到，请勿重复确认", http_status=409)
        decision = evaluate(db, student)
        if not (decision.get("checkinEligibility") or {}).get("eligible"):
            raise AppException("ORIENTATION_QUALIFICATION_CHANGED", "学生身份或个人信息状态已变化，请重新核查", http_status=409)
        now = datetime.utcnow()
        record = OrientationCheckinRecord(
            tenant_id=_tid(), batch_id=student.batch_id,
            orientation_student_id=student.id, checkin_point_id=point.id,
            token_id=token_row.id, nonce_hash=token_row.nonce_hash,
            checked_in_at=now, checked_in_by=actor_id,
            checkin_method="SIGNED_TOKEN", status="CONFIRMED",
        )
        db.add(record)
        db.flush()
        token_row.status = "CONSUMED"
        token_row.consumed_at = now
        token_row.consumed_by = actor_id
        token_row.checkin_record_id = record.id
        token_row.version = int(token_row.version or 0) + 1
        before = student.report_status
        student.report_status = "CHECKED_IN"
        student.checkin_time = now
        if student.stage not in ("ENROLLED", "CANCELLED"):
            student.stage = "REGISTERED_PENDING_ENROLLMENT"
        set_student_step_status(
            db, student, "CHECKIN", "DONE", status_source="PROCESS_FACT",
            source_biz_id=f"checkin-record:{record.id}",
        )
        student.version = int(student.version or 0) + 1
        _audit(
            db, "CHECKIN", student.id, "签名凭证现场报到确认",
            f"报到点：{point.name}", before, "CHECKED_IN",
        )
        db.commit()
        return _record_payload(db, record)


def today_records(user: dict) -> dict:
    from app.services.mobile_teacher_service import _require_teacher
    from app.services.orientation_service import assert_orientation_student_scope

    _require_teacher(user)
    start, end = local_today_bounds_utc()
    with session() as db:
        rows = list(db.scalars(select(OrientationCheckinRecord).where(
            OrientationCheckinRecord.tenant_id == _tid(),
            OrientationCheckinRecord.checked_in_at >= start,
            OrientationCheckinRecord.checked_in_at < end,
            OrientationCheckinRecord.status == "CONFIRMED",
            OrientationCheckinRecord.is_deleted.is_(False),
        ).order_by(OrientationCheckinRecord.checked_in_at.desc())).all())
        visible = []
        for row in rows:
            student = db.get(OrientationStudent, int(row.orientation_student_id))
            try:
                assert_orientation_student_scope(db, student, user)
            except AppException:
                continue
            visible.append(_record_payload(db, row))
        return {"hasData": bool(visible), "list": visible, "total": len(visible)}
