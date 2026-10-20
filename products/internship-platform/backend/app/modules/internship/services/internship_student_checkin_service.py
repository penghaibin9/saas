"""Yiyang C02 / G05-G08 student check-in authority for Standalone."""
from __future__ import annotations

import calendar as _calendar
from datetime import date, datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.config import settings
from app.core.exceptions import AppException
from app.core.tenant_scoped import tenant_get
from app.db.session import db_enabled, get_sessionmaker
from app.models import (
    AttendanceException,
    InternshipAuditTrail,
    InternshipBatch,
    InternshipCheckin,
    InternshipCheckinExemption,
    InternshipLeave,
    InternshipMakeup,
    InternshipPosition,
)
from app.modules.internship.services import internship_checkin_trust_service as trust
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.services import mobile_student_service
from app.services.db_service import _iso, _tid
from app.modules.internship.services import internship_checkin_evidence_service as evidence_svc

_COORDINATE_SYSTEMS = {"GCJ02", "WGS84"}


def _session():
    return get_sessionmaker()()


def _require_db():
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "真实签到需要独立数据库", http_status=503)


def _student_record(db, user: dict, *, batch_id=None, for_write=False):
    student = mobile_student_service.resolve_student(db, user or {})
    if not student:
        raise AppException("DATA_NOT_FOUND", "未找到当前学生档案", http_status=404)
    ctx = resolve_student_internship_context(
        db,
        student=student,
        batch_id=batch_id,
        for_write=for_write,
    )
    if not ctx.record:
        raise AppException("DATA_NOT_FOUND", ctx.message or "未找到当前实习记录", http_status=404)
    return ctx.record, student, ctx.batch


def _zone(name: str | None) -> ZoneInfo:
    value = str(name or settings.TENANT_TIMEZONE or "Asia/Shanghai").strip()
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise AppException("VALIDATION_ERROR", "timezoneName 必须是有效 IANA 时区") from None


def _local_clock(timezone_name: str | None):
    zone = _zone(timezone_name)
    now = datetime.now(timezone.utc).astimezone(zone)
    offset = now.utcoffset() or timedelta(0)
    return zone, now, int(offset.total_seconds() // 60)


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _distance_m(lat1, lng1, lat2, lng2) -> float:
    d_lat, d_lng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


def _trail(db, *, target_id: int, action: str, user: dict, detail: dict):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=target_id,
        target_type="CHECKIN",
        action=action,
        operator_name=str((user or {}).get("realName") or "学生"),
        detail_json=detail,
        occurred_at=datetime.utcnow(),
    ))


def preflight(user: dict, *, batch_id=None, timezone_name: str | None = None) -> dict:
    _require_db()
    zone, local_now, offset_minutes = _local_clock(timezone_name)
    with _session() as db:
        record, student, _batch = _student_record(db, user, batch_id=batch_id, for_write=True)
        if record.status not in {"ONBOARD", "ASSESSING"}:
            raise AppException("DATA_CONFLICT", "仅在岗或考核中的实习学生可以打卡")
        position = tenant_get(db, InternshipPosition, record.position_id) if record.position_id else None
        rule = trust.resolve_rule(db, record, position)
        day = local_now.date().isoformat()
        credential = trust.issue_token(
            tenant_id=_tid(),
            student_id=student.id,
            internship_id=record.id,
            checkin_date=day,
        )
        return {
            **credential,
            "date": day,
            "timezoneName": str(zone.key),
            "timezoneOffsetMinutes": offset_minutes,
            "serverLocalTime": local_now.isoformat(timespec="seconds"),
            "rule": {
                "configured": rule["configured"],
                "radiusM": rule["radiusM"],
                "maxAccuracyM": rule["maxAccuracyM"],
                "coordinateSystem": rule["coordinateSystem"],
                "source": rule["source"],
                "place": record.position_name or record.enterprise_name or "当前实习岗位",
            },
            "privacyNotice": "仅在点击打卡时采集一次定位、现场照片和必要设备风险信息，不后台持续定位",
        }


def checkin(user: dict, body: dict, *, batch_id=None) -> dict:
    _require_db()
    payload = body or {}
    key = str(payload.get("idempotencyKey") or "").strip()[:100] or None
    client_risk = str(payload.get("deviceRiskFlag") or "").lower().strip()
    if client_risk not in {"", "normal", "mock", "rooted"}:
        raise AppException("VALIDATION_ERROR", "deviceRiskFlag 必须是 normal、mock 或 rooted")
    risk_flag = client_risk if client_risk in {"mock", "rooted"} else "not_available"

    lat, lng = _float_or_none(payload.get("lat")), _float_or_none(payload.get("lng"))
    accuracy = _float_or_none(payload.get("gpsAccuracy"))
    if (lat is None) != (lng is None):
        raise AppException("VALIDATION_ERROR", "经纬度必须同时提供")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise AppException("VALIDATION_ERROR", "定位经纬度不合法")
    if accuracy is not None and not (0 <= accuracy <= 10000):
        raise AppException("VALIDATION_ERROR", "定位精度不合法")

    coordinate_system = str(payload.get("coordinateSystem") or "GCJ02").strip().upper()
    if coordinate_system not in _COORDINATE_SYSTEMS:
        raise AppException("VALIDATION_ERROR", "coordinateSystem 仅支持 GCJ02 或 WGS84")
    timezone_name = str(payload.get("timezoneName") or settings.TENANT_TIMEZONE or "Asia/Shanghai").strip()
    zone, local_now, offset_minutes = _local_clock(timezone_name)
    today = local_now.date().isoformat()
    address = str(payload.get("address") or payload.get("locationLabel") or "").strip()[:300]
    country_region = str(payload.get("countryRegion") or "").strip()[:100] or None
    photo_file_id = str(payload.get("photoFileId") or payload.get("evidenceFileId") or "").strip() or None
    if photo_file_id and not address and lat is not None:
        address = f"坐标 {lat:.6f},{lng:.6f}"
    if photo_file_id and not address:
        raise AppException("VALIDATION_ERROR", "上传现场照片时必须同时提供定位位置，服务端才能生成完整水印")

    with _session() as db:
        record, student, _batch = _student_record(db, user, batch_id=batch_id, for_write=True)
        if record.status not in {"ONBOARD", "ASSESSING"}:
            raise AppException("DATA_CONFLICT", "仅在岗或考核中的实习学生可以打卡")

        duplicate = db.scalar(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(),
            InternshipCheckin.internship_id == record.id,
            InternshipCheckin.checkin_date == today,
            InternshipCheckin.is_deleted.is_(False),
        ))
        if duplicate:
            if key and duplicate.idempotency_key == key:
                return {
                    "id": str(duplicate.id),
                    "date": today,
                    "result": duplicate.result,
                    "idempotentReplay": True,
                    "photoFileId": duplicate.evidence_file_id or "",
                    "watermarkedFileId": duplicate.watermarked_file_id or "",
                    "message": "打卡请求已成功处理",
                }
            raise AppException("DATA_CONFLICT", "当地日期今日已打卡，请勿重复打卡")

        position = tenant_get(db, InternshipPosition, record.position_id) if record.position_id else None
        rule = trust.resolve_rule(db, record, position)
        distance_m = None
        radius_m = rule.get("radiusM") if rule.get("configured") else None

        if lat is not None:
            trust.verify_token(
                str(payload.get("checkinToken") or ""),
                tenant_id=_tid(),
                student_id=student.id,
                internship_id=record.id,
                checkin_date=today,
            )

        if risk_flag in {"mock", "rooted"}:
            result, exception_type = "MOCK_LOCATION", "MOCK_LOCATION"
        elif lat is not None and rule.get("configured") and coordinate_system != str(rule.get("coordinateSystem") or "GCJ02").upper():
            # Never compare coordinates in different systems and call it cheating.
            result, exception_type = "LOCATION_UNCERTAIN", "LOCATION_UNCERTAIN"
        else:
            if lat is not None and rule.get("configured"):
                distance_m = _distance_m(lat, lng, rule["centerLat"], rule["centerLng"])
            result, exception_type = trust.classify_location(
                lat=lat,
                lng=lng,
                accuracy=accuracy,
                rule=rule,
                distance_m=distance_m,
            )

        row = InternshipCheckin(
            tenant_id=_tid(),
            internship_id=record.id,
            checkin_date=today,
            checkin_at=datetime.utcnow(),
            lat=lat,
            lng=lng,
            address=address or None,
            result=result,
            note=str(payload.get("note") or "").strip()[:500] or None,
            gps_accuracy=accuracy,
            device_risk_flag=risk_flag,
            distance_m=distance_m,
            evidence_file_id=photo_file_id,
            timezone_name=str(zone.key),
            timezone_offset_minutes=offset_minutes,
            coordinate_system=coordinate_system,
            location_provider=str(payload.get("locationProvider") or "")[:50] or None,
            country_region=country_region,
            idempotency_key=key,
        )
        db.add(row)
        db.flush()

        if photo_file_id:
            watermark_text = (
                f"{local_now:%Y-%m-%d %H:%M:%S} {zone.key} | {address}"
                + (f" | {lat:.6f},{lng:.6f}" if lat is not None else "")
            )
            evidence = evidence_svc.watermark_photo(
                original_file_id=photo_file_id,
                checkin_id=row.id,
                watermark_text=watermark_text,
                actor=user or {},
                student_id=student.id,
                batch_id=str(record.batch_id or "") or None,
                db=db,
            )
            row.evidence_sha256 = evidence["originalSha256"]
            row.watermarked_file_id = evidence["watermarkedFileId"]
            row.watermarked_sha256 = evidence["watermarkedSha256"]
            row.watermark_text = watermark_text

        exception = None
        if exception_type:
            exception = AttendanceException(
                tenant_id=_tid(),
                internship_id=record.id,
                exception_type=exception_type,
                exception_date=datetime.utcnow(),
                distance_km=(distance_m / 1000 if distance_m is not None else None),
                gps_accuracy=accuracy,
                device_risk_flag=risk_flag,
                address=row.address,
                student_note=row.note,
                status="PENDING_HANDLE",
            )
            db.add(exception)
            db.flush()
            try:
                from app.modules.internship.services import internship_todo_helper as todo
                todo.push_exception_todo(db, exception, record)
            except ImportError:
                # Todo projection is useful but must not become a second write authority.
                pass

        _trail(
            db,
            target_id=row.id,
            action="CHECKIN_CREATE",
            user=user,
            detail={
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "result": result,
                "localDate": today,
                "timezoneName": str(zone.key),
                "coordinateSystem": coordinate_system,
                "distanceM": distance_m,
                "photoFileId": photo_file_id,
                "watermarkedFileId": row.watermarked_file_id,
                "evidenceSha256": row.evidence_sha256,
                "watermarkedSha256": row.watermarked_sha256,
            },
        )
        db.commit()

        return {
            "id": str(row.id),
            "date": today,
            "serverLocalTime": local_now.isoformat(timespec="seconds"),
            "timezoneName": str(zone.key),
            "timezoneOffsetMinutes": offset_minutes,
            "result": result,
            "distanceM": distance_m,
            "geofenceRadiusM": radius_m,
            "geofenceConfigured": radius_m is not None,
            "coordinateSystem": coordinate_system,
            "photoFileId": row.evidence_file_id or "",
            "watermarkedFileId": row.watermarked_file_id or "",
            "evidenceSha256": row.evidence_sha256 or "",
            "watermarkedSha256": row.watermarked_sha256 or "",
            "watermarkText": row.watermark_text or "",
            "message": {
                "NORMAL": "打卡成功（围栏内）",
                "OUT_OF_RANGE": "已打卡，但超出企业围栏，已记异常待核验",
                "LOW_ACCURACY": "已记录，但定位精度不足，已转教师核验",
                "LOCATION_UNCERTAIN": "已记录，定位坐标系或精度需人工核验",
                "NO_LOCATION": "已记录打卡时间（无定位，不作作弊认定）",
                "RECORDED": "已打卡留痕（岗位未配置围栏）",
                "MOCK_LOCATION": "已打卡，设备风险标记异常，已转异常台",
            }.get(result, "打卡已提交"),
        }


def _date_range(start: str, end: str):
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        yield current.isoformat()
        current += timedelta(days=1)


def calendar(user: dict, *, month: str | None = None, batch_id=None,
             timezone_name: str | None = None) -> dict:
    _require_db()
    zone, local_now, _offset = _local_clock(timezone_name)
    month_value = str(month or local_now.strftime("%Y-%m")).strip()
    try:
        year, month_no = [int(x) for x in month_value.split("-", 1)]
        if not 1 <= month_no <= 12:
            raise ValueError
    except ValueError:
        raise AppException("VALIDATION_ERROR", "month 格式必须为 YYYY-MM") from None

    first = date(year, month_no, 1)
    last = date(year, month_no, _calendar.monthrange(year, month_no)[1])
    with _session() as db:
        record, _student, batch = _student_record(db, user, batch_id=batch_id, for_write=False)
        start = record.intern_start_date.date() if record.intern_start_date else (batch.start_date.date() if batch and batch.start_date else first)
        end = record.intern_end_date.date() if record.intern_end_date else (batch.end_date.date() if batch and batch.end_date else last)

        checkins = db.scalars(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(),
            InternshipCheckin.internship_id == record.id,
            InternshipCheckin.checkin_date >= first.isoformat(),
            InternshipCheckin.checkin_date <= last.isoformat(),
            InternshipCheckin.is_deleted.is_(False),
        )).all()
        checkin_by_day = {row.checkin_date: row for row in checkins}

        leaves = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(),
            InternshipLeave.internship_id == record.id,
            InternshipLeave.status == "APPROVED",
            InternshipLeave.end_date >= first.isoformat(),
            InternshipLeave.start_date <= last.isoformat(),
            InternshipLeave.is_deleted.is_(False),
        )).all()
        leave_days = set()
        for row in leaves:
            leave_days.update(_date_range(max(row.start_date, first.isoformat()), min(row.end_date, last.isoformat())))

        exemptions = db.scalars(select(InternshipCheckinExemption).where(
            InternshipCheckinExemption.tenant_id == _tid(),
            InternshipCheckinExemption.internship_id == record.id,
            InternshipCheckinExemption.status == "APPROVED",
            InternshipCheckinExemption.end_date >= first.isoformat(),
            InternshipCheckinExemption.start_date <= last.isoformat(),
            InternshipCheckinExemption.is_deleted.is_(False),
        )).all()
        exempt_days = set()
        for row in exemptions:
            exempt_days.update(_date_range(max(row.start_date, first.isoformat()), min(row.end_date, last.isoformat())))

        makeups = db.scalars(select(InternshipMakeup).where(
            InternshipMakeup.tenant_id == _tid(),
            InternshipMakeup.internship_id == record.id,
            InternshipMakeup.status == "APPROVED",
            InternshipMakeup.checkin_date >= first.isoformat(),
            InternshipMakeup.checkin_date <= last.isoformat(),
            InternshipMakeup.is_deleted.is_(False),
        )).all()
        makeup_days = {row.checkin_date for row in makeups}

        days = []
        summary = {"CHECKIN": 0, "ABSENT": 0, "PENDING": 0, "LEAVE": 0, "EXEMPT": 0, "MAKEUP": 0}
        today = local_now.date()
        for day_no in range(1, last.day + 1):
            current = date(year, month_no, day_no)
            ds = current.isoformat()
            row = checkin_by_day.get(ds)
            if current < start or current > end:
                status = "OUTSIDE"
            elif row:
                status = "MAKEUP" if ds in makeup_days else "CHECKIN"
            elif ds in exempt_days:
                status = "EXEMPT"
            elif ds in leave_days:
                status = "LEAVE"
            elif current > today:
                status = "FUTURE"
            elif current == today:
                status = "PENDING"
            else:
                status = "ABSENT"
            if status in summary:
                summary[status] += 1
            days.append({
                "date": ds,
                "day": day_no,
                "status": status,
                "result": row.result if row else "",
                "time": _iso(row.checkin_at) if row else None,
                "address": row.address if row else "",
                "photoFileId": row.evidence_file_id if row else "",
                "watermarkedFileId": row.watermarked_file_id if row else "",
                "canApplyMakeup": status == "ABSENT",
            })

        return {
            "hasData": True,
            "batchId": str(record.batch_id or ""),
            "internshipId": str(record.id),
            "month": month_value,
            "timezoneName": str(zone.key),
            "internshipStartDate": start.isoformat(),
            "internshipEndDate": end.isoformat(),
            "summary": summary,
            "days": days,
        }


def week(user: dict, *, batch_id=None, timezone_name: str | None = None) -> dict:
    zone, local_now, _offset = _local_clock(timezone_name)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    sunday = min(monday + timedelta(days=6), local_now.date())
    months = {monday.strftime("%Y-%m"), sunday.strftime("%Y-%m")}
    merged = {}
    for month_value in sorted(months):
        monthly = calendar(
            user,
            month=month_value,
            batch_id=batch_id,
            timezone_name=str(zone.key),
        )
        for item in monthly["days"]:
            merged[item["date"]] = item
    rows = [
        merged[ds]
        for ds in sorted(merged)
        if monday <= date.fromisoformat(ds) <= sunday
    ]
    legacy = []
    for item in rows:
        mapping = {
            "CHECKIN": item["result"] or "NORMAL",
            "MAKEUP": "NORMAL",
            "EXEMPT": "EXEMPT",
            "LEAVE": "LEAVE",
            "PENDING": "PENDING",
            "ABSENT": "ABSENT",
        }
        legacy.append({
            "date": item["date"],
            "status": mapping.get(item["status"], item["status"]),
            "time": item["time"],
        })
    return {"hasData": True, "timezoneName": str(zone.key), "days": legacy}



def _month_keys(start: date, end: date):
    current = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while current <= last:
        yield current.strftime("%Y-%m")
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def attendance_history(user: dict, *, batch_id=None, timezone_name: str | None = None) -> dict:
    """SP03 projection over the canonical C02 calendar, never a second attendance authority."""
    _require_db()
    zone, local_now, _offset = _local_clock(timezone_name)
    with _session() as db:
        record, _student, batch = _student_record(
            db, user, batch_id=batch_id, for_write=False)
        start = (
            record.intern_start_date.date()
            if record.intern_start_date
            else batch.start_date.date()
            if batch and batch.start_date
            else local_now.date()
        )
        configured_end = (
            record.intern_end_date.date()
            if record.intern_end_date
            else batch.end_date.date()
            if batch and batch.end_date
            else local_now.date()
        )
        visible_end = min(configured_end, local_now.date())
        selected_batch_id = str(record.batch_id or "")
        internship_id = str(record.id)

    if visible_end < start:
        rows = []
    else:
        rows = []
        for month_value in _month_keys(start, visible_end):
            monthly = calendar(
                user,
                month=month_value,
                batch_id=batch_id,
                timezone_name=str(zone.key),
            )
            rows.extend(
                item for item in monthly["days"]
                if item["status"] not in ("OUTSIDE", "FUTURE")
                and start.isoformat() <= item["date"] <= visible_end.isoformat()
            )

    summary = {
        "CHECKIN": sum(1 for item in rows if item["status"] == "CHECKIN"),
        "ABSENT": sum(1 for item in rows if item["status"] in ("ABSENT", "PENDING")),
        "LEAVE": sum(1 for item in rows if item["status"] == "LEAVE"),
        "MAKEUP": sum(1 for item in rows if item["status"] == "MAKEUP"),
        "EXEMPT": sum(1 for item in rows if item["status"] == "EXEMPT"),
    }
    return {
        "hasData": True,
        "batchId": selected_batch_id,
        "internshipId": internship_id,
        "timezoneName": str(zone.key),
        "internshipStartDate": start.isoformat(),
        "internshipEndDate": configured_end.isoformat(),
        "throughDate": visible_end.isoformat(),
        "summary": summary,
        "totalCountedDays": sum(summary.values()),
        "items": sorted(rows, key=lambda item: item["date"], reverse=True),
    }


def attendance_history_pdf(user: dict, *, batch_id=None,
                           timezone_name: str | None = None) -> dict:
    """SP03 real PDF, generated from the exact same history projection shown on screen."""
    from app.services import pdf_util

    data = attendance_history(
        user, batch_id=batch_id, timezone_name=timezone_name)
    summary = data["summary"]
    lines = [
        f"实习期间：{data['internshipStartDate']} 至 {data['internshipEndDate']}",
        f"统计截至：{data['throughDate']}　时区：{data['timezoneName']}",
        "",
        (
            f"已签到 {summary['CHECKIN']} 天　"
            f"未签到 {summary['ABSENT']} 天　"
            f"请假 {summary['LEAVE']} 天　"
            f"补签 {summary['MAKEUP']} 天　"
            f"免签 {summary['EXEMPT']} 天"
        ),
        "",
        "考勤明细",
    ]
    labels = {
        "CHECKIN": "已签到",
        "ABSENT": "未签到",
        "PENDING": "未签到",
        "LEAVE": "请假",
        "MAKEUP": "补签",
        "EXEMPT": "免签",
    }
    for item in reversed(data["items"]):
        extra = []
        if item.get("time"):
            extra.append(str(item["time"]))
        if item.get("address"):
            extra.append(str(item["address"]))
        lines.append(
            f"{item['date']}　{labels.get(item['status'], item['status'])}"
            + (f"　{' · '.join(extra)}" if extra else "")
        )
    content = pdf_util.build_text_pdf(
        "岗位实习签到考勤记录",
        "\n".join(lines),
        watermark=(
            f"跃科岗位实习管理平台 · 学生本人导出 · "
            f"批次 {data['batchId']} · 实习记录 {data['internshipId']}"
        ),
    )
    if not content.startswith(b"%PDF"):
        raise AppException("DATA_CONFLICT", "考勤 PDF 生成失败")
    result = pdf_util.pack_pdf_result(content, "岗位实习签到考勤记录.pdf")
    result.update({
        "batchId": data["batchId"],
        "internshipId": data["internshipId"],
        "rowCount": len(data["items"]),
        "summary": summary,
    })
    return result
