"""学生考试自视图与缓考申请安全适配层。

目的：在不重写现有考务编排/审批服务的前提下，统一修复三类生产风险：
1. 以学校本地时区判断是否开考，禁止 UTC 与本地文本直接比较；
2. 学生端历史考试包含正式 FINISHED 状态；
3. 缓考提交必须再次证明 examCourseId 属于本人考试名单，防止猜 ID 代他人/跨课程申请。

缓考审批状态机、审计格式继续复用 academic_affairs_exam_service，避免形成第二套规则。
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session
from app.services.mobile_student_service import _require_student, resolve_student

_DEFAULT_TIMEZONE = "Asia/Shanghai"
_VISIBLE_BATCH_STATUSES = {"PUBLISHED", "FINISHED", "ARCHIVED", "CLOSED"}  # CLOSED 兼容历史数据


def _tenant_timezone(db) -> tuple[ZoneInfo, str]:
    """读取租户扩展配置中的 timezone；缺失/非法时使用中国学校默认时区。"""
    from app.models import TenantBrandConfig

    cfg = db.scalars(select(TenantBrandConfig).where(
        TenantBrandConfig.tenant_id == _tid(),
        TenantBrandConfig.is_deleted.is_(False),
    )).first()
    raw = (getattr(cfg, "config_json", None) or {}) if cfg else {}
    name = str(raw.get("timezone") or raw.get("timeZone") or _DEFAULT_TIMEZONE).strip()
    try:
        return ZoneInfo(name), name
    except ZoneInfoNotFoundError:
        return ZoneInfo(_DEFAULT_TIMEZONE), _DEFAULT_TIMEZONE


def _local_exam_datetime(course, zone: ZoneInfo) -> datetime | None:
    if not getattr(course, "exam_date", None):
        return None
    start = str(getattr(course, "start_time", None) or "00:00").strip()
    try:
        naive = datetime.fromisoformat(f"{course.exam_date}T{start}")
    except (TypeError, ValueError):
        return None
    return naive.replace(tzinfo=zone)


def exam_started(course, *, zone: ZoneInfo, now: datetime | None = None) -> bool:
    """按学校本地时区判断是否已开考；无法解析时不擅自判已开考。"""
    exam_at = _local_exam_datetime(course, zone)
    if exam_at is None:
        return False
    current = now or datetime.now(zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=zone)
    return current.astimezone(zone) >= exam_at


def _student(db, user):
    student = resolve_student(db, _require_student(user))
    if not student:
        raise not_found("学生档案不存在")
    return student


def _seat_rows(db, student_id: int):
    from app.models import AaExamRoomStudent
    return db.scalars(select(AaExamRoomStudent).where(
        AaExamRoomStudent.tenant_id == _tid(),
        AaExamRoomStudent.student_id == int(student_id),
        AaExamRoomStudent.is_deleted.is_(False),
    ).order_by(AaExamRoomStudent.id.desc())).all()


def exam_my(user) -> dict:
    """本人已发布/已结束/已归档考试安排，包含座位与本地开考状态。"""
    from app.models import AaExamBatch, AaExamCourse, AaExamRoom

    with session() as db:
        student = _student(db, user)
        zone, zone_name = _tenant_timezone(db)
        items = []
        for seat in _seat_rows(db, student.id):
            course = db.get(AaExamCourse, int(seat.exam_course_id))
            if not course or course.is_deleted or course.tenant_id != _tid():
                continue
            batch = db.get(AaExamBatch, int(course.batch_id)) if course.batch_id else None
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                continue
            if str(batch.status or "").upper() not in _VISIBLE_BATCH_STATUSES:
                continue
            room = db.get(AaExamRoom, int(seat.exam_room_id)) if seat.exam_room_id else None
            items.append({
                "examCourseId": str(course.id),
                "courseName": course.course_name or "",
                "className": course.class_name or "",
                "examDate": course.exam_date or "",
                "startTime": course.start_time or "",
                "endTime": course.end_time or "",
                "classroom": (room.classroom_text if room else "") or "",
                "seatNo": seat.seat_no,
                "admissionNo": seat.admission_no or "",
                "batchName": batch.batch_name or "",
                "batchStatus": batch.status or "",
                "status": course.status or "",
                "started": exam_started(course, zone=zone),
                "timezone": zone_name,
            })
        items.sort(key=lambda x: (x.get("examDate") or "9999-99-99", x.get("startTime") or "99:99",
                                  x.get("courseName") or ""))
        return {
            "hasData": bool(items), "items": items, "total": len(items), "timezone": zone_name,
            "note": "" if items else "暂无已发布的个人考试安排",
        }


def deferrable_courses(user) -> dict:
    """本人名单内、尚未开考且没有进行中缓考申请的课程。"""
    from app.models import AaDeferredExam, AaExamBatch, AaExamCourse
    from app.modules.academic_affairs.services import academic_affairs_exam_service as legacy

    with session() as db:
        student = _student(db, user)
        zone, zone_name = _tenant_timezone(db)
        active = {int(row.exam_course_id) for row in db.scalars(select(AaDeferredExam).where(
            AaDeferredExam.tenant_id == _tid(), AaDeferredExam.student_id == student.id,
            AaDeferredExam.status.notin_([legacy._D_REJECTED, legacy._D_APPROVED]),
            AaDeferredExam.is_deleted.is_(False),
        )).all()}
        seen = set()
        items = []
        for seat in _seat_rows(db, student.id):
            cid = int(seat.exam_course_id)
            if cid in seen:
                continue
            seen.add(cid)
            course = db.get(AaExamCourse, cid)
            if not course or course.is_deleted or course.tenant_id != _tid() or course.status == "REMOVED":
                continue
            batch = db.get(AaExamBatch, int(course.batch_id)) if course.batch_id else None
            if not batch or batch.is_deleted or batch.tenant_id != _tid() or batch.status != "PUBLISHED":
                continue
            started = exam_started(course, zone=zone)
            items.append({
                "examCourseId": str(course.id), "courseName": course.course_name or "",
                "examDate": course.exam_date or "", "startTime": course.start_time or "",
                "endTime": course.end_time or "", "hasActiveDefer": cid in active,
                "started": started, "canApply": not started and cid not in active,
            })
        items.sort(key=lambda x: (x.get("examDate") or "9999-99-99", x.get("startTime") or "99:99"))
        return {"items": items, "total": len(items), "timezone": zone_name}


def defer_apply(user, body: dict) -> dict:
    """本人申请缓考：名单归属、未开考、无进行中申请、理由完整。"""
    from app.models import AaDeferredExam, AaExamBatch, AaExamCourse, AaExamRoomStudent
    from app.modules.academic_affairs.services import academic_affairs_exam_service as legacy

    data = body or {}
    raw_cid = data.get("examCourseId")
    if not raw_cid:
        raise AppException("VALIDATION_ERROR", "请选择本人考试课程")
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "缓考原因必填且不少于5个字")
    reason_type = str(data.get("reasonType") or "").strip()
    if not reason_type:
        raise AppException("VALIDATION_ERROR", "请选择缓考原因类型")

    with session() as db:
        student = _student(db, user)
        course = db.get(AaExamCourse, int(raw_cid))
        if not course or course.is_deleted or course.tenant_id != _tid() or course.status == "REMOVED":
            raise not_found("考试课程不存在")
        seat = db.scalars(select(AaExamRoomStudent).where(
            AaExamRoomStudent.tenant_id == _tid(),
            AaExamRoomStudent.student_id == student.id,
            AaExamRoomStudent.exam_course_id == course.id,
            AaExamRoomStudent.is_deleted.is_(False),
        )).first()
        if not seat:
            raise AppException("NO_DATA_SCOPE", "该考试课程不在您的考试名单内", http_status=403)
        batch = db.get(AaExamBatch, int(course.batch_id)) if course.batch_id else None
        if not batch or batch.is_deleted or batch.tenant_id != _tid() or batch.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布且尚未开考的考试可以申请缓考", http_status=409)
        zone, _ = _tenant_timezone(db)
        if exam_started(course, zone=zone):
            raise AppException("DATA_CONFLICT", "考试已开始，不可申请缓考", http_status=409)
        active = db.scalars(select(AaDeferredExam).where(
            AaDeferredExam.tenant_id == _tid(), AaDeferredExam.student_id == student.id,
            AaDeferredExam.exam_course_id == course.id,
            AaDeferredExam.status.notin_([legacy._D_REJECTED, legacy._D_APPROVED]),
            AaDeferredExam.is_deleted.is_(False),
        )).first()
        if active:
            raise AppException("DATA_CONFLICT", "已有进行中的缓考申请", http_status=409)
        row = AaDeferredExam(
            tenant_id=_tid(), student_id=student.id, student_no=student.student_no,
            student_name=student.real_name, exam_course_id=course.id, course_name=course.course_name,
            reason_type=reason_type, reason=reason, apply_at=datetime.utcnow(),
            current_node="COUNSELOR", status=legacy._D_COUNSELOR,
        )
        db.add(row)
        db.flush()
        legacy._audit(db, "DEFERRED_EXAM", row.id, "DEFER_APPLY_SUBMIT", f"缓考申请 {course.course_name}")
        db.commit()
        db.refresh(row)
        return legacy._defer_dto(row)
