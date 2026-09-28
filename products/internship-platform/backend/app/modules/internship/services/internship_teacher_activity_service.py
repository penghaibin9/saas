"""Yiyang C08/G16 teacher activity and persisted emergency notice authority."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipBatch,
    InternshipEmergencyNotice,
    InternshipRecord,
    InternshipTeacherCheckin,
    InternshipTeacherWorkReport,
)
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_identity import stable_user_id
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services import file_service
from app.services.db_service import _iso, _tid, session


def _teacher_identity(user: dict) -> tuple[int, str]:
    user_id = stable_user_id(user)
    if not user_id:
        raise no_permission("当前账号缺少稳定教师身份，不能登记教师业务事实")
    name = str((user or {}).get("realName") or (user or {}).get("loginName") or "教师").strip()
    return user_id, name[:100]


def _batch(db, batch_id) -> InternshipBatch:
    try:
        bid = int(batch_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "batchId 格式非法") from None
    row = db.get(InternshipBatch, bid)
    if not row or row.tenant_id != _tid() or row.is_deleted:
        raise not_found("实习批次不存在")
    return row


def _scope_mode(user: dict) -> str:
    from app.modules.internship.services.internship_student_service import _current_scope
    return str((_current_scope(user) or {}).get("mode") or "")


def _assert_teacher_batch_scope(db, batch_id: int, user: dict) -> InternshipBatch:
    row = _batch(db, batch_id)
    if _scope_mode(user) == "ADMIN_TENANT":
        return row
    scoped = apply_internship_record_scope(
        select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == row.id,
            InternshipRecord.is_deleted.is_(False),
        ),
        user,
    )
    if db.scalar(scoped.limit(1)) is None:
        raise no_permission("当前实习批次不在你的指导或管理范围内")
    return row


def _require_school_admin(user: dict) -> None:
    if _scope_mode(user) != "ADMIN_TENANT":
        raise no_permission("批次紧急通知仅限校级岗位实习管理员发布或撤回")


def _zone(name: str | None) -> tuple[str, ZoneInfo]:
    value = str(name or "Asia/Shanghai").strip() or "Asia/Shanghai"
    try:
        return value, ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise AppException("VALIDATION_ERROR", "timezoneName 不是有效的 IANA 时区") from None


def _location(body: dict) -> tuple[float | None, float | None, float | None]:
    lat_raw, lng_raw = body.get("latitude"), body.get("longitude")
    if (lat_raw is None) != (lng_raw is None):
        raise AppException("VALIDATION_ERROR", "纬度和经度必须同时提供")
    lat = lng = None
    if lat_raw is not None:
        try:
            lat, lng = float(lat_raw), float(lng_raw)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "定位坐标格式非法") from None
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise AppException("VALIDATION_ERROR", "定位坐标超出合法范围")
    accuracy = body.get("accuracyM")
    if accuracy is not None:
        try:
            accuracy = float(accuracy)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "定位精度格式非法") from None
        if accuracy < 0:
            raise AppException("VALIDATION_ERROR", "定位精度不能为负数")
    return lat, lng, accuracy


def _checkin_view(row: InternshipTeacherCheckin, *, already=False) -> dict:
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "teacherUserId": str(row.teacher_user_id),
        "teacherName": row.teacher_name_snapshot,
        "localDate": row.local_date.isoformat() if row.local_date else "",
        "timezoneName": row.timezone_name,
        "checkedInAt": _iso(row.checked_in_at) or "",
        "latitude": float(row.latitude) if row.latitude is not None else None,
        "longitude": float(row.longitude) if row.longitude is not None else None,
        "accuracyM": float(row.accuracy_m) if row.accuracy_m is not None else None,
        "address": row.address or "",
        "note": row.note or "",
        "alreadyCheckedIn": bool(already),
    }


def checkin(user: dict, body: dict) -> dict:
    payload = body or {}
    teacher_id, teacher_name = _teacher_identity(user)
    timezone_name, tz = _zone(payload.get("timezoneName"))
    lat, lng, accuracy = _location(payload)
    now_utc = datetime.now(timezone.utc)
    local_date = now_utc.astimezone(tz).date()
    with session() as db:
        batch = _assert_teacher_batch_scope(db, payload.get("batchId"), user)
        existing = db.scalar(select(InternshipTeacherCheckin).where(
            InternshipTeacherCheckin.tenant_id == _tid(),
            InternshipTeacherCheckin.batch_id == batch.id,
            InternshipTeacherCheckin.teacher_user_id == teacher_id,
            InternshipTeacherCheckin.local_date == local_date,
            InternshipTeacherCheckin.is_deleted.is_(False),
        ))
        if existing:
            return _checkin_view(existing, already=True)

        row = InternshipTeacherCheckin(
            tenant_id=_tid(),
            batch_id=batch.id,
            teacher_user_id=teacher_id,
            teacher_name_snapshot=teacher_name,
            local_date=local_date,
            timezone_name=timezone_name,
            checked_in_at=now_utc.replace(tzinfo=None),
            latitude=lat,
            longitude=lng,
            accuracy_m=accuracy,
            address=str(payload.get("address") or "").strip()[:500] or None,
            note=str(payload.get("note") or "").strip()[:500] or None,
        )
        db.add(row)
        db.flush()
        add_audit(
            db,
            target_type="TEACHER_CHECKIN",
            target_id=row.id,
            action="TEACHER_CHECKIN_CREATE",
            user=user,
            batch_id=batch.id,
            detail={
                "teacherUserId": str(teacher_id),
                "localDate": local_date.isoformat(),
                "timezoneName": timezone_name,
                "hasLocation": lat is not None,
            },
        )
        db.commit()
        return _checkin_view(row)


def list_my_checkins(user: dict, *, batch_id, limit: int = 31) -> list[dict]:
    teacher_id, _ = _teacher_identity(user)
    limit = min(366, max(1, int(limit or 31)))
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        rows = db.scalars(select(InternshipTeacherCheckin).where(
            InternshipTeacherCheckin.tenant_id == _tid(),
            InternshipTeacherCheckin.batch_id == batch.id,
            InternshipTeacherCheckin.teacher_user_id == teacher_id,
            InternshipTeacherCheckin.is_deleted.is_(False),
        ).order_by(
            InternshipTeacherCheckin.local_date.desc(),
            InternshipTeacherCheckin.id.desc(),
        ).limit(limit)).all()
        return [_checkin_view(row) for row in rows]


def _validate_attachments(file_ids) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in file_ids or []:
        fid = str(raw or "").strip()
        if not fid or fid in seen:
            continue
        if len(result) >= 9:
            raise AppException("VALIDATION_ERROR", "教师工作报告附件最多 9 个")
        if not file_service.get_file_meta(fid):
            raise AppException("VALIDATION_ERROR", f"附件 {fid} 不存在或无权访问")
        seen.add(fid)
        result.append(fid)
    return result


def _parse_report_date(raw) -> date:
    try:
        value = date.fromisoformat(str(raw or "").strip())
    except ValueError:
        raise AppException("VALIDATION_ERROR", "reportDate 必须为 YYYY-MM-DD") from None
    if value > date.today():
        raise AppException("VALIDATION_ERROR", "不能提交未来日期的教师工作报告")
    return value


def _report_view(row: InternshipTeacherWorkReport) -> dict:
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "teacherUserId": str(row.teacher_user_id),
        "teacherName": row.teacher_name_snapshot,
        "reportDate": row.report_date.isoformat() if row.report_date else "",
        "workContent": row.work_content,
        "issueContent": row.issue_content or "",
        "nextPlan": row.next_plan or "",
        "studentCount": row.student_count,
        "attachmentFileIds": list(row.attachment_file_ids_json or []),
        "submittedAt": _iso(row.submitted_at) or "",
        "version": int(row.version or 0),
    }


def save_work_report(user: dict, body: dict) -> dict:
    payload = body or {}
    teacher_id, teacher_name = _teacher_identity(user)
    report_date = _parse_report_date(payload.get("reportDate"))
    work_content = str(payload.get("workContent") or "").strip()
    if len(work_content) < 10:
        raise AppException("VALIDATION_ERROR", "教师工作内容至少填写 10 个字")
    if len(work_content) > 8000:
        raise AppException("VALIDATION_ERROR", "教师工作内容不能超过 8000 字")
    attachments = _validate_attachments(payload.get("attachmentFileIds"))
    student_count = payload.get("studentCount")
    if student_count not in (None, ""):
        try:
            student_count = int(student_count)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "涉及学生人数格式非法") from None
        if student_count < 0:
            raise AppException("VALIDATION_ERROR", "涉及学生人数不能为负数")
    else:
        student_count = None

    with session() as db:
        batch = _assert_teacher_batch_scope(db, payload.get("batchId"), user)
        row = db.scalar(select(InternshipTeacherWorkReport).where(
            InternshipTeacherWorkReport.tenant_id == _tid(),
            InternshipTeacherWorkReport.batch_id == batch.id,
            InternshipTeacherWorkReport.teacher_user_id == teacher_id,
            InternshipTeacherWorkReport.report_date == report_date,
            InternshipTeacherWorkReport.is_deleted.is_(False),
        ).with_for_update())
        action = "TEACHER_WORK_REPORT_CREATE"
        if row:
            expected = payload.get("expectedVersion")
            if expected is None:
                raise AppException("DATA_CONFLICT", "当天工作报告已存在，修改时必须提供 expectedVersion")
            try:
                expected = int(expected)
            except (TypeError, ValueError):
                raise AppException("DATA_CONFLICT", "expectedVersion 格式非法，请刷新后重试") from None
            if expected != int(row.version or 0):
                raise AppException("DATA_CONFLICT", "教师工作报告已被更新，请刷新后重试")
            row.version = int(row.version or 0) + 1
            action = "TEACHER_WORK_REPORT_UPDATE"
        else:
            row = InternshipTeacherWorkReport(
                tenant_id=_tid(),
                batch_id=batch.id,
                teacher_user_id=teacher_id,
                teacher_name_snapshot=teacher_name,
                report_date=report_date,
            )
            db.add(row)

        row.teacher_name_snapshot = teacher_name
        row.work_content = work_content
        row.issue_content = str(payload.get("issueContent") or "").strip()[:4000] or None
        row.next_plan = str(payload.get("nextPlan") or "").strip()[:4000] or None
        row.student_count = student_count
        row.attachment_file_ids_json = attachments
        row.submitted_at = datetime.utcnow()
        db.flush()
        for fid in attachments:
            file_service.bind_file_biz(
                fid,
                "INTERNSHIP_TEACHER_WORK_REPORT",
                str(row.id),
                user=user,
                db=db,
            )
        add_audit(
            db,
            target_type="TEACHER_WORK_REPORT",
            target_id=row.id,
            action=action,
            user=user,
            batch_id=batch.id,
            expected_version=payload.get("expectedVersion"),
            new_version=int(row.version or 0),
            file_ids=attachments,
            detail={
                "teacherUserId": str(teacher_id),
                "reportDate": report_date.isoformat(),
                "workLength": len(work_content),
                "studentCount": student_count,
            },
        )
        db.commit()
        return _report_view(row)


def list_my_work_reports(user: dict, *, batch_id, page: int = 1, page_size: int = 20) -> dict:
    teacher_id, _ = _teacher_identity(user)
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        base = select(InternshipTeacherWorkReport).where(
            InternshipTeacherWorkReport.tenant_id == _tid(),
            InternshipTeacherWorkReport.batch_id == batch.id,
            InternshipTeacherWorkReport.teacher_user_id == teacher_id,
            InternshipTeacherWorkReport.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = db.scalars(base.order_by(
            InternshipTeacherWorkReport.report_date.desc(),
            InternshipTeacherWorkReport.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).all()
        return {
            "items": [_report_view(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def _notice_view(row: InternshipEmergencyNotice) -> dict:
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "title": row.title,
        "content": row.content,
        "senderName": row.sender_name_snapshot or "",
        "recipientCount": int(row.recipient_count or 0),
        "status": row.status,
        "publishedAt": _iso(row.published_at) or "",
        "withdrawnAt": _iso(row.withdrawn_at) or "",
        "withdrawReason": row.withdraw_reason or "",
    }


def publish_emergency_notice(user: dict, body: dict) -> dict:
    payload = body or {}
    _require_school_admin(user)
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if len(title) < 2 or len(title) > 200:
        raise AppException("VALIDATION_ERROR", "紧急通知标题需为 2 到 200 个字")
    if len(content) < 5 or len(content) > 5000:
        raise AppException("VALIDATION_ERROR", "紧急通知正文需为 5 到 5000 个字")
    sender_id, sender_name = _teacher_identity(user)
    with session() as db:
        batch = _batch(db, payload.get("batchId"))
        recipient_count = int(db.scalar(select(func.count(func.distinct(InternshipRecord.student_id))).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        )) or 0)
        row = InternshipEmergencyNotice(
            tenant_id=_tid(),
            batch_id=batch.id,
            title=title,
            content=content,
            sender_user_id=sender_id,
            sender_name_snapshot=sender_name,
            recipient_count=recipient_count,
            status="PUBLISHED",
            outbox_id=None,
            published_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
        add_audit(
            db,
            target_type="EMERGENCY_NOTICE",
            target_id=row.id,
            action="EMERGENCY_NOTICE_PUBLISH",
            user=user,
            batch_id=batch.id,
            detail={"recipientCount": recipient_count, "delivery": "PERSISTED_IN_APP"},
        )
        db.commit()
        return _notice_view(row)


def list_teacher_notices(user: dict, *, batch_id, include_withdrawn: bool = True) -> list[dict]:
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        query = select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.is_deleted.is_(False),
        )
        if not include_withdrawn:
            query = query.where(InternshipEmergencyNotice.status == "PUBLISHED")
        rows = db.scalars(query.order_by(
            InternshipEmergencyNotice.published_at.desc(),
            InternshipEmergencyNotice.id.desc(),
        ).limit(100)).all()
        return [_notice_view(row) for row in rows]


def withdraw_emergency_notice(user: dict, notice_id, reason: str) -> dict:
    _require_school_admin(user)
    reason = str(reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "撤回原因至少填写 2 个字")
    with session() as db:
        try:
            nid = int(notice_id)
        except (TypeError, ValueError):
            raise not_found("紧急通知不存在") from None
        row = db.scalar(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.id == nid,
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("紧急通知不存在")
        if row.status == "WITHDRAWN":
            return _notice_view(row)
        row.status = "WITHDRAWN"
        row.withdrawn_at = datetime.utcnow()
        row.withdraw_reason = reason[:500]
        row.version = int(row.version or 0) + 1
        add_audit(
            db,
            target_type="EMERGENCY_NOTICE",
            target_id=row.id,
            action="EMERGENCY_NOTICE_WITHDRAW",
            user=user,
            batch_id=row.batch_id,
            new_version=int(row.version or 0),
            reason=reason[:500],
        )
        db.commit()
        return _notice_view(row)


def list_student_notices(user: dict, *, batch_id) -> list[dict]:
    with session() as db:
        batch = _batch(db, batch_id)
        ctx = resolve_student_internship_context(
            db,
            student_no=(user or {}).get("studentNo"),
            batch_id=batch.id,
            for_write=False,
        )
        if not ctx.record or int(ctx.record.batch_id or 0) != int(batch.id):
            raise no_permission("当前学生不属于该实习批次")
        rows = db.scalars(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.status == "PUBLISHED",
            InternshipEmergencyNotice.is_deleted.is_(False),
        ).order_by(
            InternshipEmergencyNotice.published_at.desc(),
            InternshipEmergencyNotice.id.desc(),
        ).limit(50)).all()
        return [_notice_view(row) for row in rows]
