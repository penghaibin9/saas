"""Yiyang C08/G16 teacher activity and persisted emergency notice authority."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    College,
    Major,
    SchoolClass,
    StudentProfile,
    InternshipBatch,
    InternshipEmergencyNotice,
    InternshipEmergencyNoticeTeacherReceipt,
    InternshipGuidance,
    InternshipRecord,
    InternshipTeacherCheckin,
    InternshipTeacherMakeup,
    InternshipTeacherPeriodReport,
    InternshipTeacherWorkReport,
    InternshipVisit,
    User,
)
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_checkin_evidence_service import watermark_photo
from app.modules.internship.services.internship_identity import stable_user_id
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services import file_service
from app.services.db_service import _iso, _tid, session


NOTICE_TYPES = {"AGREEMENT", "TRAINING", "SAFETY", "NOTICE", "OTHER"}
NOTICE_URGENCY = {"NORMAL", "IMPORTANT", "URGENT"}
NOTICE_ATTACHMENT_EXTENSIONS = {"rar", "zip", "doc", "docx", "pdf", "xls", "xlsx"}
MAX_NOTICE_ATTACHMENTS = 9


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


def _notice_datetime(value, label: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            raise AppException("VALIDATION_ERROR", f"{label}格式不正确") from None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _notice_attachment_ids(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AppException("VALIDATION_ERROR", "通知附件必须以列表提交")
    out = []
    for raw in value:
        fid = str(raw or "").strip()
        if not fid or fid in out:
            continue
        meta = file_service.get_file_meta(fid)
        if not meta:
            raise AppException("VALIDATION_ERROR", "通知附件不存在或无权访问")
        ext = str(meta.get("ext") or "").lower()
        if ext not in NOTICE_ATTACHMENT_EXTENSIONS:
            raise AppException(
                "VALIDATION_ERROR",
                "通知附件仅支持 RAR、ZIP、WORD、EXCEL、PDF 格式",
            )
        out.append(fid)
    if len(out) > MAX_NOTICE_ATTACHMENTS:
        raise AppException("VALIDATION_ERROR", f"通知附件最多上传{MAX_NOTICE_ATTACHMENTS}个")
    return out


def _notice_audience(payload: dict) -> tuple[str, list[int]]:
    scope = str((payload or {}).get("audienceScope") or "ALL").strip().upper()
    if scope not in ("ALL", "COLLEGE"):
        raise AppException("VALIDATION_ERROR", "通知接收范围仅支持全校或指定学院")
    raw = (payload or {}).get("recipientCollegeIds") or []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "指定学院必须以列表提交")
    ids = []
    for value in raw:
        try:
            cid = int(value)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "学院ID格式不正确") from None
        if cid > 0 and cid not in ids:
            ids.append(cid)
    if scope == "COLLEGE" and not ids:
        raise AppException("VALIDATION_ERROR", "指定学院发布时至少选择一个学院")
    if scope == "ALL":
        ids = []
    return scope, ids


def _student_college_id(db, student: StudentProfile | None) -> int | None:
    if student is None:
        return None
    if getattr(student, "college_id", None):
        return int(student.college_id)
    major_id = getattr(student, "major_id", None)
    if major_id:
        major = db.get(Major, int(major_id))
        if major and major.tenant_id == _tid() and not major.is_deleted and major.college_id:
            return int(major.college_id)
    class_id = getattr(student, "class_id", None)
    if class_id:
        cls = db.get(SchoolClass, int(class_id))
        if cls and cls.tenant_id == _tid() and not cls.is_deleted and cls.major_id:
            major = db.get(Major, int(cls.major_id))
            if major and major.tenant_id == _tid() and not major.is_deleted and major.college_id:
                return int(major.college_id)
    return None


def notice_applies_to_student(db, row: InternshipEmergencyNotice, student: StudentProfile | None) -> bool:
    scope = str(getattr(row, "audience_scope", None) or "ALL").upper()
    if scope == "ALL":
        return True
    if scope != "COLLEGE":
        return False
    target_ids = {int(x) for x in (row.recipient_college_ids_json or []) if str(x).isdigit()}
    college_id = _student_college_id(db, student)
    return bool(college_id and college_id in target_ids)


def _notice_applies_to_teacher(db, row: InternshipEmergencyNotice, user: dict, teacher_id: int) -> bool:
    scope = str(getattr(row, "audience_scope", None) or "ALL").upper()
    if scope == "ALL":
        return True
    if scope != "COLLEGE":
        return False
    target_ids = {int(x) for x in (row.recipient_college_ids_json or []) if str(x).isdigit()}
    if not target_ids:
        return False

    from app.services.mobile_teacher_service import resolve_teacher_scope
    teacher_scope = resolve_teacher_scope(user)
    if teacher_scope.get("mode") == "ADMIN_TENANT":
        return True

    college_names = {str(x) for x in (teacher_scope.get("collegeNames") or set()) if str(x)}
    if college_names:
        visible_ids = set(db.scalars(select(College.id).where(
            College.tenant_id == _tid(),
            College.college_name.in_(college_names),
            College.is_deleted.is_(False),
        )).all())
        if target_ids.intersection(int(x) for x in visible_ids):
            return True

    records = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == row.batch_id,
        InternshipRecord.advisor_user_id == teacher_id,
        InternshipRecord.is_deleted.is_(False),
    )).all()
    student_ids = {int(rec.student_id) for rec in records if rec.student_id}
    if not student_ids:
        return False
    students = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id.in_(student_ids),
        StudentProfile.is_deleted.is_(False),
    )).all()
    return any((_student_college_id(db, student) in target_ids) for student in students)


def _recipient_student_count(db, batch_id: int, audience_scope: str, college_ids: list[int]) -> int:
    records = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch_id,
        InternshipRecord.is_deleted.is_(False),
    )).all()
    student_ids = {int(rec.student_id) for rec in records if rec.student_id}
    if not student_ids:
        return 0
    if audience_scope == "ALL":
        return len(student_ids)
    students = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id.in_(student_ids),
        StudentProfile.is_deleted.is_(False),
    )).all()
    targets = set(college_ids)
    return sum(1 for student in students if _student_college_id(db, student) in targets)


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
        "result": row.result or "RECORDED",
        "distanceM": float(row.distance_m) if row.distance_m is not None else None,
        "coordinateSystem": row.coordinate_system or "",
        "countryRegion": row.country_region or "",
        "locationProvider": row.location_provider or "",
        "photoFileId": row.photo_file_id or "",
        "watermarkedFileId": row.watermarked_file_id or "",
        "photoSha256": row.photo_sha256 or "",
        "watermarkedSha256": row.watermarked_sha256 or "",
        "watermarkText": row.watermark_text or "",
        "evidenceAvailable": bool(row.photo_file_id and row.watermarked_file_id),
        "alreadyCheckedIn": bool(already),
    }


def checkin(user: dict, body: dict) -> dict:
    payload = body or {}
    teacher_id, teacher_name = _teacher_identity(user)
    timezone_name, tz = _zone(payload.get("timezoneName"))
    lat, lng, accuracy = _location(payload)
    photo_file_id = str(payload.get("photoFileId") or "").strip() or None
    if photo_file_id and lat is None:
        raise AppException("VALIDATION_ERROR", "教师签到上传现场照片时必须同时提供定位，才能生成可信位置水印")

    coordinate_system = str(
        payload.get("coordinateSystem") or ("GCJ02" if lat is not None else "")
    ).strip().upper() or None
    if coordinate_system not in (None, "GCJ02", "WGS84"):
        raise AppException("VALIDATION_ERROR", "coordinateSystem 仅支持 GCJ02/WGS84")
    country_region = str(payload.get("countryRegion") or "").strip()[:100] or None
    location_provider = str(payload.get("locationProvider") or "").strip()[:50] or None
    address = str(payload.get("address") or "").strip()[:500] or None
    result = "NO_LOCATION" if lat is None else (
        "LOW_ACCURACY" if accuracy is not None and accuracy > 200 else "NORMAL"
    )

    now_utc = datetime.now(timezone.utc)
    local_now = now_utc.astimezone(tz)
    local_date = local_now.date()
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
            address=address,
            note=str(payload.get("note") or "").strip()[:500] or None,
            result=result,
            coordinate_system=coordinate_system,
            country_region=country_region,
            location_provider=location_provider,
            photo_file_id=photo_file_id,
        )
        db.add(row)
        db.flush()

        evidence = None
        if photo_file_id:
            location_text = address or f"{lat:.6f},{lng:.6f}"
            watermark_text = (
                f"教师签到 · {teacher_name}\n"
                f"{local_now.strftime('%Y-%m-%d %H:%M:%S')} {timezone_name}\n"
                f"{location_text}\n"
                f"{coordinate_system or 'GCJ02'} {lat:.6f},{lng:.6f}"
            )
            evidence = watermark_photo(
                original_file_id=photo_file_id,
                checkin_id=int(row.id),
                watermark_text=watermark_text,
                actor=user,
                batch_id=str(batch.id),
                subject_type="TEACHER",
                subject_id=teacher_id,
                biz_type="INTERNSHIP_TEACHER_CHECKIN",
                db=db,
            )
            row.photo_file_id = evidence["originalFileId"]
            row.watermarked_file_id = evidence["watermarkedFileId"]
            row.photo_sha256 = evidence["originalSha256"] or None
            row.watermarked_sha256 = evidence["watermarkedSha256"] or None
            row.watermark_text = watermark_text

        add_audit(
            db,
            target_type="TEACHER_CHECKIN",
            target_id=row.id,
            action="TEACHER_CHECKIN_CREATE",
            user=user,
            batch_id=batch.id,
            file_ids=[
                fid for fid in [row.photo_file_id, row.watermarked_file_id] if fid
            ],
            detail={
                "teacherUserId": str(teacher_id),
                "localDate": local_date.isoformat(),
                "timezoneName": timezone_name,
                "hasLocation": lat is not None,
                "result": result,
                "coordinateSystem": coordinate_system or "",
                "countryRegion": country_region or "",
                "hasTrustedPhotoEvidence": bool(evidence),
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


def _normalize_period(report_type, period_key) -> tuple[str, str]:
    kind = str(report_type or "").strip().upper()
    key = str(period_key or "").strip().upper()
    if kind == "WEEKLY":
        match = re.fullmatch(r"(\d{4})-W(\d{2})", key)
        if not match:
            raise AppException("VALIDATION_ERROR", "周报 periodKey 必须为 YYYY-Www，例如 2026-W39")
        try:
            start = date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            raise AppException("VALIDATION_ERROR", "周报 periodKey 不是有效 ISO 周") from None
        if start > date.today():
            raise AppException("VALIDATION_ERROR", "不能提交未来周的教师周报")
        return kind, key
    if kind == "MONTHLY":
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", key):
            raise AppException("VALIDATION_ERROR", "月报 periodKey 必须为 YYYY-MM")
        if date.fromisoformat(key + "-01") > date.today().replace(day=1):
            raise AppException("VALIDATION_ERROR", "不能提交未来月份的教师月报")
        return kind, key
    if kind == "SUMMARY":
        if key not in {"", "SUMMARY", "FINAL"}:
            raise AppException("VALIDATION_ERROR", "总结 periodKey 只能为 SUMMARY")
        return kind, "SUMMARY"
    raise AppException("VALIDATION_ERROR", "reportType 必须是 WEEKLY/MONTHLY/SUMMARY")


def _period_report_view(row: InternshipTeacherPeriodReport) -> dict:
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "teacherUserId": str(row.teacher_user_id),
        "teacherName": row.teacher_name_snapshot,
        "reportType": row.report_type,
        "periodKey": row.period_key,
        "content": row.content,
        "issueContent": row.issue_content or "",
        "nextPlan": row.next_plan or "",
        "studentCount": row.student_count,
        "attachmentFileIds": list(row.attachment_file_ids_json or []),
        "submittedAt": _iso(row.submitted_at) or "",
        "version": int(row.version or 0),
    }


def save_period_report(user: dict, body: dict) -> dict:
    payload = body or {}
    teacher_id, teacher_name = _teacher_identity(user)
    report_type, period_key = _normalize_period(
        payload.get("reportType"), payload.get("periodKey"))
    content = str(payload.get("content") or "").strip()
    minimum = 300 if report_type == "SUMMARY" else (100 if report_type == "MONTHLY" else 30)
    if len(content) < minimum:
        label = {"WEEKLY": "周报", "MONTHLY": "月报", "SUMMARY": "总结"}[report_type]
        raise AppException("VALIDATION_ERROR", f"教师{label}至少填写 {minimum} 个字")
    if len(content) > 12000:
        raise AppException("VALIDATION_ERROR", "教师周期报告不能超过 12000 字")
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
        row = db.scalar(select(InternshipTeacherPeriodReport).where(
            InternshipTeacherPeriodReport.tenant_id == _tid(),
            InternshipTeacherPeriodReport.batch_id == batch.id,
            InternshipTeacherPeriodReport.teacher_user_id == teacher_id,
            InternshipTeacherPeriodReport.report_type == report_type,
            InternshipTeacherPeriodReport.period_key == period_key,
            InternshipTeacherPeriodReport.is_deleted.is_(False),
        ).with_for_update())
        action = "TEACHER_PERIOD_REPORT_CREATE"
        if row:
            expected = payload.get("expectedVersion")
            if expected is None:
                raise AppException(
                    "DATA_CONFLICT", "该周期教师报告已存在，修改时必须提供 expectedVersion")
            try:
                expected = int(expected)
            except (TypeError, ValueError):
                raise AppException(
                    "DATA_CONFLICT", "expectedVersion 格式非法，请刷新后重试") from None
            if expected != int(row.version or 0):
                raise AppException("DATA_CONFLICT", "教师周期报告已被更新，请刷新后重试")
            row.version = int(row.version or 0) + 1
            action = "TEACHER_PERIOD_REPORT_UPDATE"
        else:
            row = InternshipTeacherPeriodReport(
                tenant_id=_tid(),
                batch_id=batch.id,
                teacher_user_id=teacher_id,
                teacher_name_snapshot=teacher_name,
                report_type=report_type,
                period_key=period_key,
            )
            db.add(row)

        row.teacher_name_snapshot = teacher_name
        row.content = content
        row.issue_content = str(payload.get("issueContent") or "").strip()[:4000] or None
        row.next_plan = str(payload.get("nextPlan") or "").strip()[:4000] or None
        row.student_count = student_count
        row.attachment_file_ids_json = attachments
        row.submitted_at = datetime.utcnow()
        db.flush()
        for fid in attachments:
            file_service.bind_file_biz(
                fid,
                "INTERNSHIP_TEACHER_PERIOD_REPORT",
                str(row.id),
                user=user,
                db=db,
            )
        add_audit(
            db,
            target_type="TEACHER_PERIOD_REPORT",
            target_id=row.id,
            action=action,
            user=user,
            batch_id=batch.id,
            expected_version=payload.get("expectedVersion"),
            new_version=int(row.version or 0),
            file_ids=attachments,
            detail={
                "teacherUserId": str(teacher_id),
                "reportType": report_type,
                "periodKey": period_key,
                "contentLength": len(content),
                "studentCount": student_count,
            },
        )
        db.commit()
        return _period_report_view(row)


def list_my_period_reports(
    user: dict, *, batch_id, report_type: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    teacher_id, _ = _teacher_identity(user)
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    normalized_type = None
    if report_type:
        normalized_type = str(report_type).strip().upper()
        if normalized_type not in {"WEEKLY", "MONTHLY", "SUMMARY"}:
            raise AppException(
                "VALIDATION_ERROR", "reportType 必须是 WEEKLY/MONTHLY/SUMMARY")
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        base = select(InternshipTeacherPeriodReport).where(
            InternshipTeacherPeriodReport.tenant_id == _tid(),
            InternshipTeacherPeriodReport.batch_id == batch.id,
            InternshipTeacherPeriodReport.teacher_user_id == teacher_id,
            InternshipTeacherPeriodReport.is_deleted.is_(False),
        )
        if normalized_type:
            base = base.where(
                InternshipTeacherPeriodReport.report_type == normalized_type)
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = db.scalars(base.order_by(
            InternshipTeacherPeriodReport.submitted_at.desc(),
            InternshipTeacherPeriodReport.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).all()
        return {
            "items": [_period_report_view(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }



def _parse_teacher_makeup_date(raw) -> date:
    try:
        value = date.fromisoformat(str(raw or "").strip())
    except ValueError:
        raise AppException("VALIDATION_ERROR", "补签日期必须为 YYYY-MM-DD") from None
    local_today = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date()
    if value > local_today:
        raise AppException("VALIDATION_ERROR", "不能申请未来日期的教师补签")
    return value


def _makeup_view(row: InternshipTeacherMakeup) -> dict:
    evidence = None
    if row.evidence_file_id:
        try:
            evidence = file_service.attachment_view(str(row.evidence_file_id))
        except Exception:  # noqa: BLE001
            evidence = None
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "teacherUserId": str(row.teacher_user_id),
        "teacherName": row.teacher_name_snapshot,
        "localDate": row.local_date.isoformat() if row.local_date else "",
        "reason": row.reason,
        "evidenceFileId": row.evidence_file_id or "",
        "evidence": evidence,
        "status": row.status,
        "reviewedByName": row.reviewed_by_name or "",
        "reviewedAt": _iso(row.reviewed_at) or "",
        "reviewComment": row.review_comment or "",
        "version": int(row.version or 0),
    }


def apply_teacher_makeup(user: dict, body: dict) -> dict:
    payload = body or {}
    teacher_id, teacher_name = _teacher_identity(user)
    target_date = _parse_teacher_makeup_date(payload.get("localDate"))
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5 or len(reason) > 500:
        raise AppException("VALIDATION_ERROR", "教师补签原因需为 5 到 500 个字")
    evidence_file_id = str(payload.get("evidenceFileId") or "").strip() or None
    if evidence_file_id and not file_service.get_file_meta(evidence_file_id):
        raise AppException("VALIDATION_ERROR", "补签佐证文件不存在或无权访问")

    with session() as db:
        batch = _assert_teacher_batch_scope(db, payload.get("batchId"), user)
        start = batch.start_date.date() if batch.start_date else None
        end = batch.end_date.date() if batch.end_date else None
        if start and target_date < start:
            raise AppException("VALIDATION_ERROR", "补签日期早于当前实习批次开始日期")
        if end and target_date > end:
            raise AppException("VALIDATION_ERROR", "补签日期晚于当前实习批次结束日期")

        existing_checkin = db.scalar(select(InternshipTeacherCheckin).where(
            InternshipTeacherCheckin.tenant_id == _tid(),
            InternshipTeacherCheckin.batch_id == batch.id,
            InternshipTeacherCheckin.teacher_user_id == teacher_id,
            InternshipTeacherCheckin.local_date == target_date,
            InternshipTeacherCheckin.is_deleted.is_(False),
        ))
        if existing_checkin:
            raise AppException("DATA_CONFLICT", "该日期已有教师签到记录，无需补签")

        pending = db.scalar(select(InternshipTeacherMakeup).where(
            InternshipTeacherMakeup.tenant_id == _tid(),
            InternshipTeacherMakeup.batch_id == batch.id,
            InternshipTeacherMakeup.teacher_user_id == teacher_id,
            InternshipTeacherMakeup.local_date == target_date,
            InternshipTeacherMakeup.status == "PENDING",
            InternshipTeacherMakeup.is_deleted.is_(False),
        ))
        if pending:
            raise AppException("DATA_CONFLICT", "该日期已有待审核教师补签申请")

        row = InternshipTeacherMakeup(
            tenant_id=_tid(),
            batch_id=batch.id,
            teacher_user_id=teacher_id,
            teacher_name_snapshot=teacher_name,
            local_date=target_date,
            reason=reason,
            evidence_file_id=evidence_file_id,
            status="PENDING",
            active_pending_key="1",
        )
        db.add(row)
        db.flush()
        if evidence_file_id:
            file_service.bind_file_biz(
                evidence_file_id,
                "INTERNSHIP_TEACHER_MAKEUP",
                str(row.id),
                user=user,
                db=db,
            )
        add_audit(
            db,
            target_type="TEACHER_MAKEUP",
            target_id=row.id,
            action="TEACHER_MAKEUP_APPLY",
            user=user,
            batch_id=batch.id,
            file_ids=[evidence_file_id] if evidence_file_id else [],
            detail={
                "teacherUserId": str(teacher_id),
                "localDate": target_date.isoformat(),
                "reason": reason,
            },
        )
        db.commit()
        return _makeup_view(row)


def list_my_teacher_makeups(
    user: dict, *, batch_id, status: str | None = None,
    page: int = 1, page_size: int = 50,
) -> dict:
    teacher_id, _ = _teacher_identity(user)
    normalized = str(status or "").strip().upper()
    if normalized and normalized not in {"PENDING", "APPROVED", "REJECTED", "WITHDRAWN"}:
        raise AppException("VALIDATION_ERROR", "补签状态不合法")
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 50)))
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        query = select(InternshipTeacherMakeup).where(
            InternshipTeacherMakeup.tenant_id == _tid(),
            InternshipTeacherMakeup.batch_id == batch.id,
            InternshipTeacherMakeup.teacher_user_id == teacher_id,
            InternshipTeacherMakeup.is_deleted.is_(False),
        )
        if normalized:
            query = query.where(InternshipTeacherMakeup.status == normalized)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.scalars(query.order_by(
            InternshipTeacherMakeup.local_date.desc(),
            InternshipTeacherMakeup.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).all()
        return {
            "items": [_makeup_view(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def withdraw_teacher_makeup(user: dict, makeup_id) -> dict:
    teacher_id, _ = _teacher_identity(user)
    with session() as db:
        row = db.scalar(select(InternshipTeacherMakeup).where(
            InternshipTeacherMakeup.id == int(makeup_id),
            InternshipTeacherMakeup.tenant_id == _tid(),
            InternshipTeacherMakeup.teacher_user_id == teacher_id,
            InternshipTeacherMakeup.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("教师补签申请不存在")
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核教师补签申请可以撤回")
        _assert_teacher_batch_scope(db, row.batch_id, user)
        row.status = "WITHDRAWN"
        row.active_pending_key = None
        row.version = int(row.version or 0) + 1
        add_audit(
            db,
            target_type="TEACHER_MAKEUP",
            target_id=row.id,
            action="TEACHER_MAKEUP_WITHDRAW",
            user=user,
            batch_id=row.batch_id,
            detail={"teacherUserId": str(teacher_id), "localDate": row.local_date.isoformat()},
        )
        db.commit()
        return _makeup_view(row)


def list_teacher_makeups_admin(
    user: dict, *, batch_id, status: str | None = None,
    page: int = 1, page_size: int = 100,
) -> dict:
    _require_school_admin(user)
    normalized = str(status or "").strip().upper()
    if normalized and normalized not in {"PENDING", "APPROVED", "REJECTED", "WITHDRAWN"}:
        raise AppException("VALIDATION_ERROR", "补签状态不合法")
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 100)))
    with session() as db:
        batch = _batch(db, batch_id)
        query = select(InternshipTeacherMakeup).where(
            InternshipTeacherMakeup.tenant_id == _tid(),
            InternshipTeacherMakeup.batch_id == batch.id,
            InternshipTeacherMakeup.is_deleted.is_(False),
        )
        if normalized:
            query = query.where(InternshipTeacherMakeup.status == normalized)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.scalars(query.order_by(
            InternshipTeacherMakeup.status.asc(),
            InternshipTeacherMakeup.local_date.desc(),
            InternshipTeacherMakeup.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).all()
        return {
            "items": [_makeup_view(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def review_teacher_makeup(user: dict, makeup_id, body: dict) -> dict:
    _require_school_admin(user)
    payload = body or {}
    action = str(payload.get("action") or "").strip().upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 仅支持 APPROVE/REJECT")
    comment = str(payload.get("comment") or "").strip()
    if action == "REJECT" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回教师补签时必须填写不少于 5 个字的原因")

    with session() as db:
        row = db.scalar(select(InternshipTeacherMakeup).where(
            InternshipTeacherMakeup.id == int(makeup_id),
            InternshipTeacherMakeup.tenant_id == _tid(),
            InternshipTeacherMakeup.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("教师补签申请不存在")
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该教师补签申请已处理，请刷新")
        batch = _batch(db, row.batch_id)

        if action == "APPROVE":
            existing = db.scalar(select(InternshipTeacherCheckin).where(
                InternshipTeacherCheckin.tenant_id == _tid(),
                InternshipTeacherCheckin.batch_id == batch.id,
                InternshipTeacherCheckin.teacher_user_id == row.teacher_user_id,
                InternshipTeacherCheckin.local_date == row.local_date,
                InternshipTeacherCheckin.is_deleted.is_(False),
            ))
            if existing:
                raise AppException("DATA_CONFLICT", "该日期已存在教师签到，不能重复审批补签")
            checkin = InternshipTeacherCheckin(
                tenant_id=_tid(),
                batch_id=batch.id,
                teacher_user_id=row.teacher_user_id,
                teacher_name_snapshot=row.teacher_name_snapshot,
                local_date=row.local_date,
                timezone_name="Asia/Shanghai",
                checked_in_at=datetime.utcnow(),
                result="MAKEUP",
                note=f"教师补签审批通过：{row.reason}"[:500],
            )
            db.add(checkin)
            db.flush()
            status = "APPROVED"
            add_audit(
                db,
                target_type="TEACHER_CHECKIN",
                target_id=checkin.id,
                action="TEACHER_CHECKIN_MAKEUP_MATERIALIZE",
                user=user,
                batch_id=batch.id,
                detail={
                    "teacherUserId": str(row.teacher_user_id),
                    "localDate": row.local_date.isoformat(),
                    "makeupId": str(row.id),
                },
            )
        else:
            status = "REJECTED"

        row.status = status
        row.active_pending_key = None
        row.reviewed_by_name = str((user or {}).get("realName") or "实习管理员")[:100]
        row.reviewed_at = datetime.utcnow()
        row.review_comment = comment[:500] or None
        row.version = int(row.version or 0) + 1
        add_audit(
            db,
            target_type="TEACHER_MAKEUP",
            target_id=row.id,
            action=f"TEACHER_MAKEUP_{status}",
            user=user,
            batch_id=batch.id,
            expected_version=payload.get("expectedVersion"),
            new_version=int(row.version or 0),
            detail={
                "teacherUserId": str(row.teacher_user_id),
                "localDate": row.local_date.isoformat(),
                "comment": comment,
            },
        )
        db.commit()
        return _makeup_view(row)


def teacher_management_ledger(user: dict, *, batch_id, keyword: str = "") -> dict:
    _require_school_admin(user)
    search = str(keyword or "").strip().lower()
    with session() as db:
        batch = _batch(db, batch_id)
        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        )).all()
        record_ids = [int(row.id) for row in records]
        assigned = defaultdict(list)
        teacher_ids = set()
        for row in records:
            if row.advisor_user_id:
                tid = int(row.advisor_user_id)
                teacher_ids.add(tid)
                assigned[tid].append(int(row.id))

        checkins = db.scalars(select(InternshipTeacherCheckin).where(
            InternshipTeacherCheckin.tenant_id == _tid(),
            InternshipTeacherCheckin.batch_id == batch.id,
            InternshipTeacherCheckin.is_deleted.is_(False),
        )).all()
        work_reports = db.scalars(select(InternshipTeacherWorkReport).where(
            InternshipTeacherWorkReport.tenant_id == _tid(),
            InternshipTeacherWorkReport.batch_id == batch.id,
            InternshipTeacherWorkReport.is_deleted.is_(False),
        )).all()
        period_reports = db.scalars(select(InternshipTeacherPeriodReport).where(
            InternshipTeacherPeriodReport.tenant_id == _tid(),
            InternshipTeacherPeriodReport.batch_id == batch.id,
            InternshipTeacherPeriodReport.is_deleted.is_(False),
        )).all()
        makeups = db.scalars(select(InternshipTeacherMakeup).where(
            InternshipTeacherMakeup.tenant_id == _tid(),
            InternshipTeacherMakeup.batch_id == batch.id,
            InternshipTeacherMakeup.is_deleted.is_(False),
        )).all()

        for row in [*checkins, *work_reports, *period_reports, *makeups]:
            teacher_ids.add(int(row.teacher_user_id))

        users = {
            int(row.id): row for row in db.scalars(select(User).where(
                User.tenant_id == _tid(),
                User.id.in_(teacher_ids or {0}),
                User.is_deleted.is_(False),
            )).all()
        }

        guidance = []
        visits = []
        if record_ids:
            guidance = db.scalars(select(InternshipGuidance).where(
                InternshipGuidance.tenant_id == _tid(),
                InternshipGuidance.internship_id.in_(record_ids),
                InternshipGuidance.status == "NORMAL",
                InternshipGuidance.is_deleted.is_(False),
            )).all()
            visits = db.scalars(select(InternshipVisit).where(
                InternshipVisit.tenant_id == _tid(),
                InternshipVisit.internship_id.in_(record_ids),
                InternshipVisit.is_deleted.is_(False),
            )).all()

        checkin_map = defaultdict(list)
        work_map = defaultdict(list)
        period_map = defaultdict(list)
        makeup_map = defaultdict(list)
        for row in checkins: checkin_map[int(row.teacher_user_id)].append(row)
        for row in work_reports: work_map[int(row.teacher_user_id)].append(row)
        for row in period_reports: period_map[int(row.teacher_user_id)].append(row)
        for row in makeups: makeup_map[int(row.teacher_user_id)].append(row)

        guidance_by_record = defaultdict(int)
        visit_by_record = defaultdict(int)
        for row in guidance: guidance_by_record[int(row.internship_id)] += 1
        for row in visits: visit_by_record[int(row.internship_id)] += 1

        rows = []
        for teacher_id in sorted(teacher_ids):
            user_row = users.get(teacher_id)
            snapshots = (
                checkin_map[teacher_id] + work_map[teacher_id]
                + period_map[teacher_id] + makeup_map[teacher_id]
            )
            snapshot_name = next(
                (str(getattr(item, "teacher_name_snapshot", "") or "") for item in snapshots
                 if getattr(item, "teacher_name_snapshot", None)),
                "",
            )
            name = (user_row.real_name if user_row else snapshot_name) or f"教师{teacher_id}"
            employee_no = user_row.login_name if user_row else ""
            if search and search not in name.lower() and search not in employee_no.lower():
                continue
            own_records = assigned.get(teacher_id, [])
            periods = period_map[teacher_id]
            last_checkin = max(
                (row.checked_in_at for row in checkin_map[teacher_id] if row.checked_in_at),
                default=None,
            )
            rows.append({
                "teacherUserId": str(teacher_id),
                "teacherName": name,
                "employeeNo": employee_no,
                "studentCount": len(own_records),
                "checkinCount": len(checkin_map[teacher_id]),
                "makeupApprovedCount": sum(1 for row in makeup_map[teacher_id] if row.status == "APPROVED"),
                "makeupPendingCount": sum(1 for row in makeup_map[teacher_id] if row.status == "PENDING"),
                "workReportCount": len(work_map[teacher_id]),
                "weeklyReportCount": sum(1 for row in periods if row.report_type == "WEEKLY"),
                "monthlyReportCount": sum(1 for row in periods if row.report_type == "MONTHLY"),
                "summaryReportCount": sum(1 for row in periods if row.report_type == "SUMMARY"),
                "guidanceCount": sum(guidance_by_record[rid] for rid in own_records),
                "visitCount": sum(visit_by_record[rid] for rid in own_records),
                "lastCheckinAt": _iso(last_checkin) or "",
            })
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name or "",
            "items": rows,
            "total": len(rows),
        }


def export_teacher_management_ledger(user: dict, *, batch_id, keyword: str = "") -> dict:
    from app.services import xlsx_util

    data = teacher_management_ledger(user, batch_id=batch_id, keyword=keyword)
    headers = [
        "教师姓名", "教工号", "所带学生", "本人签到", "已通过补签", "待审补签",
        "工作日报", "本人周报", "本人月报", "本人总结", "指导记录", "巡访记录", "最近签到",
    ]
    rows = [[
        row["teacherName"], row["employeeNo"], row["studentCount"], row["checkinCount"],
        row["makeupApprovedCount"], row["makeupPendingCount"], row["workReportCount"],
        row["weeklyReportCount"], row["monthlyReportCount"], row["summaryReportCount"],
        row["guidanceCount"], row["visitCount"], row["lastCheckinAt"],
    ] for row in data["items"]]
    content = xlsx_util.build_ledger_xlsx(
        "教师管理台账",
        headers,
        rows,
        watermark=f"跃科岗位实习管理平台 · 教师管理 · {datetime.now():%Y-%m-%d %H:%M}",
    )
    return xlsx_util.pack_xlsx_result(content, "岗位实习教师管理台账.xlsx", len(rows))


def _notice_view(row: InternshipEmergencyNotice) -> dict:
    attachments = []
    for file_id in list(row.attachment_file_ids_json or []):
        try:
            meta = file_service.attachment_view(str(file_id))
        except Exception:  # noqa: BLE001 - one unavailable attachment must not hide the notice
            meta = None
        if meta:
            attachments.append(meta)
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "title": row.title,
        "content": row.content,
        "noticeType": row.notice_type or "NOTICE",
        "urgency": row.urgency or "NORMAL",
        "validFrom": _iso(row.valid_from) or "",
        "validUntil": _iso(row.valid_until) or "",
        "forcePopup": (row.urgency or "NORMAL") in ("IMPORTANT", "URGENT"),
        "attachmentFileIds": list(row.attachment_file_ids_json or []),
        "attachments": attachments,
        "audienceScope": row.audience_scope or "ALL",
        "recipientCollegeIds": [str(x) for x in (row.recipient_college_ids_json or [])],
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
    notice_type = str(payload.get("noticeType") or "NOTICE").strip().upper()
    urgency = str(payload.get("urgency") or "IMPORTANT").strip().upper()
    valid_from = _notice_datetime(payload.get("validFrom"), "有效期开始时间")
    valid_until = _notice_datetime(payload.get("validUntil"), "有效期结束时间")
    attachment_ids = _notice_attachment_ids(payload.get("attachmentFileIds"))
    audience_scope, college_ids = _notice_audience(payload)
    if len(title) < 2 or len(title) > 200:
        raise AppException("VALIDATION_ERROR", "通知标题需为 2 到 200 个字")
    if len(content) < 5 or len(content) > 5000:
        raise AppException("VALIDATION_ERROR", "通知正文需为 5 到 5000 个字")
    if notice_type not in NOTICE_TYPES:
        raise AppException("VALIDATION_ERROR", "公告类型不合法")
    if urgency not in NOTICE_URGENCY:
        raise AppException("VALIDATION_ERROR", "紧急程度不合法")
    if valid_from and valid_until and valid_from > valid_until:
        raise AppException("VALIDATION_ERROR", "有效期结束时间不能早于开始时间")
    sender_id, sender_name = _teacher_identity(user)
    with session() as db:
        batch = _batch(db, payload.get("batchId"))
        if audience_scope == "COLLEGE":
            existing_colleges = set(db.scalars(select(College.id).where(
                College.tenant_id == _tid(),
                College.id.in_(college_ids),
                College.is_deleted.is_(False),
            )).all())
            if existing_colleges != set(college_ids):
                raise AppException("VALIDATION_ERROR", "指定接收学院不存在或不在当前学校")
        recipient_count = _recipient_student_count(
            db, batch.id, audience_scope, college_ids)
        row = InternshipEmergencyNotice(
            tenant_id=_tid(),
            batch_id=batch.id,
            title=title,
            content=content,
            notice_type=notice_type,
            urgency=urgency,
            valid_from=valid_from,
            valid_until=valid_until,
            attachment_file_ids_json=attachment_ids or None,
            audience_scope=audience_scope,
            recipient_college_ids_json=college_ids or None,
            sender_user_id=sender_id,
            sender_name_snapshot=sender_name,
            recipient_count=recipient_count,
            status="PUBLISHED",
            outbox_id=None,
            published_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
        for file_id in attachment_ids:
            file_service.bind_file_biz(
                file_id, "INTERNSHIP_NOTICE", str(row.id), user=user, db=db)
        add_audit(
            db,
            target_type="EMERGENCY_NOTICE",
            target_id=row.id,
            action="EMERGENCY_NOTICE_PUBLISH",
            user=user,
            batch_id=batch.id,
            detail={
                "recipientCount": recipient_count,
                "delivery": "PERSISTED_IN_APP",
                "noticeType": notice_type,
                "urgency": urgency,
                "attachmentCount": len(attachment_ids),
                "audienceScope": audience_scope,
                "recipientCollegeIds": [str(x) for x in college_ids],
                "validFrom": _iso(valid_from) or "",
                "validUntil": _iso(valid_until) or "",
            },
        )
        db.commit()
        return _notice_view(row)


def list_teacher_notices(user: dict, *, batch_id, include_withdrawn: bool = True) -> list[dict]:
    teacher_id, _teacher_name = _teacher_identity(user)
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
        return [
            _notice_view(row) for row in rows
            if _notice_applies_to_teacher(db, row, user, teacher_id)
        ]


def pending_teacher_notices(user: dict, *, batch_id) -> list[dict]:
    teacher_id, _teacher_name = _teacher_identity(user)
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        now = datetime.utcnow()
        notices = db.scalars(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.status == "PUBLISHED",
            InternshipEmergencyNotice.urgency.in_(("IMPORTANT", "URGENT")),
            InternshipEmergencyNotice.is_deleted.is_(False),
            ((InternshipEmergencyNotice.valid_from.is_(None)) | (InternshipEmergencyNotice.valid_from <= now)),
            ((InternshipEmergencyNotice.valid_until.is_(None)) | (InternshipEmergencyNotice.valid_until >= now)),
        ).order_by(
            InternshipEmergencyNotice.published_at.asc(),
            InternshipEmergencyNotice.id.asc(),
        ).limit(100)).all()
        if not notices:
            return []
        acknowledged = set(db.scalars(select(
            InternshipEmergencyNoticeTeacherReceipt.notice_id
        ).where(
            InternshipEmergencyNoticeTeacherReceipt.tenant_id == _tid(),
            InternshipEmergencyNoticeTeacherReceipt.batch_id == batch.id,
            InternshipEmergencyNoticeTeacherReceipt.teacher_user_id == teacher_id,
            InternshipEmergencyNoticeTeacherReceipt.notice_id.in_([int(row.id) for row in notices]),
            InternshipEmergencyNoticeTeacherReceipt.is_deleted.is_(False),
        )).all())
        return [
            {**_notice_view(row), "requiresPopup": True}
            for row in notices
            if int(row.id) not in acknowledged
            and _notice_applies_to_teacher(db, row, user, teacher_id)
        ]


def acknowledge_teacher_notice(user: dict, notice_id, *, batch_id) -> dict:
    teacher_id, _teacher_name = _teacher_identity(user)
    try:
        nid = int(notice_id)
    except (TypeError, ValueError):
        raise not_found("紧急通知不存在") from None
    with session() as db:
        batch = _assert_teacher_batch_scope(db, batch_id, user)
        notice = db.scalar(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.id == nid,
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.status == "PUBLISHED",
            InternshipEmergencyNotice.is_deleted.is_(False),
        ))
        if not notice:
            raise not_found("紧急通知不存在、已撤回或不属于当前批次")
        if not _notice_applies_to_teacher(db, notice, user, teacher_id):
            raise no_permission("该通知不属于你的接收范围")
        receipt = db.scalar(select(InternshipEmergencyNoticeTeacherReceipt).where(
            InternshipEmergencyNoticeTeacherReceipt.tenant_id == _tid(),
            InternshipEmergencyNoticeTeacherReceipt.notice_id == notice.id,
            InternshipEmergencyNoticeTeacherReceipt.teacher_user_id == teacher_id,
            InternshipEmergencyNoticeTeacherReceipt.is_deleted.is_(False),
        ))
        if receipt:
            return {
                **_notice_view(notice),
                "receiptId": str(receipt.id),
                "acknowledgedAt": _iso(receipt.acknowledged_at) or "",
                "alreadyAcknowledged": True,
            }
        now = datetime.utcnow()
        receipt = InternshipEmergencyNoticeTeacherReceipt(
            tenant_id=_tid(),
            notice_id=notice.id,
            batch_id=batch.id,
            teacher_user_id=teacher_id,
            acknowledged_at=now,
            acknowledged_channel="TEACHER_MOBILE_FORCE_POPUP",
        )
        db.add(receipt)
        db.flush()
        add_audit(
            db,
            target_type="EMERGENCY_NOTICE_TEACHER_RECEIPT",
            target_id=receipt.id,
            action="EMERGENCY_NOTICE_TEACHER_ACKNOWLEDGED",
            user=user,
            batch_id=batch.id,
            detail={"noticeId": str(notice.id), "teacherUserId": str(teacher_id)},
        )
        db.commit()
        return {
            **_notice_view(notice),
            "receiptId": str(receipt.id),
            "acknowledgedAt": _iso(now) or "",
            "alreadyAcknowledged": False,
        }


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
        now = datetime.utcnow()
        rows = db.scalars(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.status == "PUBLISHED",
            InternshipEmergencyNotice.is_deleted.is_(False),
            ((InternshipEmergencyNotice.valid_from.is_(None)) | (InternshipEmergencyNotice.valid_from <= now)),
            ((InternshipEmergencyNotice.valid_until.is_(None)) | (InternshipEmergencyNotice.valid_until >= now)),
        ).order_by(
            InternshipEmergencyNotice.published_at.desc(),
            InternshipEmergencyNotice.id.desc(),
        ).limit(50)).all()
        return [
            _notice_view(row) for row in rows
            if notice_applies_to_student(db, row, ctx.student)
        ]
