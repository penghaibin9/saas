"""学生考试自视图与缓考申请安全适配层。

目的：在不重写现有考务编排/审批服务的前提下，统一修复生产风险：
1. 以学校本地时区判断是否开考，禁止 UTC 与本地文本直接比较；
2. 学生端只消费已越过发布边界的正式考试事实：有效座位 -> ACTIVE room ->
   CONFIRMED course -> PUBLISHED/FINISHED/ARCHIVED batch + published_at；
3. 本人考试读取使用单条 join 查询，禁止 seat 列表后逐条 db.get(course/batch/room)；
4. 缓考提交再次证明 examCourseId 属于本人当前正式考试座位，防止猜 ID、失效考场或
   非正式课程绕过；进行中申请和审批状态机继续复用考务公开契约。

缓考审批状态机、审计格式继续复用考务公开契约，避免形成第二套规则；本模块不得直接读取
legacy exam service 的下划线私有状态或审计/DTO 辅助函数。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services import academic_affairs_exam_public_contract as exam_contract
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


def _formal_exam_rows(db, student_id: int, *, batch_statuses=None):
    """本人正式考试事实，一条查询跨 seat/room/course/batch，不消费编排草稿。"""
    from app.models import AaExamBatch, AaExamCourse, AaExamRoom, AaExamRoomStudent

    statuses = sorted(batch_statuses or _VISIBLE_BATCH_STATUSES)
    return db.execute(
        select(AaExamRoomStudent, AaExamRoom, AaExamCourse, AaExamBatch)
        .join(
            AaExamRoom,
            (AaExamRoom.id == AaExamRoomStudent.exam_room_id)
            & (AaExamRoom.tenant_id == AaExamRoomStudent.tenant_id),
        )
        .join(
            AaExamCourse,
            (AaExamCourse.id == AaExamRoomStudent.exam_course_id)
            & (AaExamCourse.id == AaExamRoom.exam_course_id)
            & (AaExamCourse.tenant_id == AaExamRoomStudent.tenant_id),
        )
        .join(
            AaExamBatch,
            (AaExamBatch.id == AaExamCourse.batch_id)
            & (AaExamBatch.tenant_id == AaExamCourse.tenant_id),
        )
        .where(
            AaExamRoomStudent.tenant_id == _tid(),
            AaExamRoomStudent.student_id == int(student_id),
            AaExamRoomStudent.is_deleted.is_(False),
            AaExamRoom.status == "ACTIVE",
            AaExamRoom.is_deleted.is_(False),
            AaExamCourse.status == "CONFIRMED",
            AaExamCourse.is_deleted.is_(False),
            AaExamBatch.status.in_(statuses),
            AaExamBatch.published_at.is_not(None),
            AaExamBatch.is_deleted.is_(False),
        )
        .order_by(AaExamCourse.exam_date, AaExamCourse.start_time, AaExamRoom.room_seq, AaExamRoomStudent.id)
    ).all()


def exam_my(user) -> dict:
    """本人已发布/已结束/已归档正式考试安排，包含座位与本地开考状态。"""
    with session() as db:
        student = _student(db, user)
        zone, zone_name = _tenant_timezone(db)
        items = []
        for seat, room, course, batch in _formal_exam_rows(db, student.id):
            items.append({
                "examCourseId": str(course.id),
                "courseName": course.course_name or "",
                "className": course.class_name or "",
                "examDate": course.exam_date or "",
                "startTime": course.start_time or "",
                "endTime": course.end_time or "",
                "classroom": room.classroom_text or "",
                "seatNo": seat.seat_no,
                "admissionNo": seat.admission_no or "",
                "batchName": batch.batch_name or "",
                "batchStatus": batch.status or "",
                "publishedAt": batch.published_at.isoformat() if batch.published_at else None,
                "status": course.status or "",
                "started": exam_started(course, zone=zone),
                "timezone": zone_name,
                "source": "FORMAL_EXAM_SEAT",
            })
        return {
            "hasData": bool(items), "items": items, "total": len(items), "timezone": zone_name,
            "note": "" if items else "暂无已发布的个人考试安排",
        }


def deferrable_courses(user) -> dict:
    """本人正式座位内、尚未开考的课程；进行中申请保留用于展示但不暴露写动作。"""
    from app.models import AaDeferredExam

    with session() as db:
        student = _student(db, user)
        zone, zone_name = _tenant_timezone(db)
        active = {int(row.exam_course_id) for row in db.scalars(select(AaDeferredExam).where(
            AaDeferredExam.tenant_id == _tid(), AaDeferredExam.student_id == student.id,
            AaDeferredExam.status.notin_(list(exam_contract.DEFER_TERMINAL_STATUSES)),
            AaDeferredExam.is_deleted.is_(False),
        )).all()}
        seen = set()
        items = []
        for _seat, _room, course, _batch in _formal_exam_rows(
            db,
            student.id,
            batch_statuses={"PUBLISHED"},
        ):
            cid = int(course.id)
            if cid in seen:
                continue
            seen.add(cid)

            # Read-model boundary is fail-closed: an already-started exam is not an option at all.
            # Malformed/missing local datetime is also omitted because the client must never receive
            # an ambiguous row that could accidentally expose a write action.
            exam_at = _local_exam_datetime(course, zone)
            if exam_at is None or exam_started(course, zone=zone):
                continue

            has_active = cid in active
            items.append({
                "examCourseId": str(course.id), "courseName": course.course_name or "",
                "examDate": course.exam_date or "", "startTime": course.start_time or "",
                "endTime": course.end_time or "", "hasActiveDefer": has_active,
                "started": False, "canApply": not has_active,
                "source": "FORMAL_EXAM_SEAT",
            })
        return {"items": items, "total": len(items), "timezone": zone_name}


def defer_apply(user, body: dict) -> dict:
    """本人申请缓考：正式座位归属、未开考、无进行中申请、理由完整。"""
    from app.models import AaDeferredExam, AaExamBatch, AaExamCourse, AaExamRoom, AaExamRoomStudent

    data = body or {}
    raw_cid = data.get("examCourseId")
    if not raw_cid:
        raise AppException("VALIDATION_ERROR", "请选择本人考试课程")
    try:
        course_id = int(raw_cid)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "examCourseId 不合法") from exc
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "缓考原因必填且不少于5个字")
    reason_type = str(data.get("reasonType") or "").strip()
    if not reason_type:
        raise AppException("VALIDATION_ERROR", "请选择缓考原因类型")

    with session() as db:
        student = _student(db, user)
        # Lock the student's formal seat so concurrent duplicate submissions serialize
        # before the active-defer check.  The same command transaction then owns audit/write.
        formal = db.execute(
            select(AaExamRoomStudent, AaExamRoom, AaExamCourse, AaExamBatch)
            .join(AaExamRoom, AaExamRoom.id == AaExamRoomStudent.exam_room_id)
            .join(AaExamCourse, AaExamCourse.id == AaExamRoomStudent.exam_course_id)
            .join(AaExamBatch, AaExamBatch.id == AaExamCourse.batch_id)
            .where(
                AaExamRoomStudent.tenant_id == _tid(),
                AaExamRoomStudent.student_id == student.id,
                AaExamRoomStudent.exam_course_id == course_id,
                AaExamRoomStudent.is_deleted.is_(False),
                AaExamRoom.tenant_id == _tid(),
                AaExamRoom.status == "ACTIVE",
                AaExamRoom.is_deleted.is_(False),
                AaExamCourse.tenant_id == _tid(),
                AaExamCourse.status == "CONFIRMED",
                AaExamCourse.is_deleted.is_(False),
                AaExamBatch.tenant_id == _tid(),
                AaExamBatch.status == "PUBLISHED",
                AaExamBatch.published_at.is_not(None),
                AaExamBatch.is_deleted.is_(False),
            )
            .with_for_update()
        ).first()
        if not formal:
            raise AppException(
                "NO_DATA_SCOPE",
                "该考试课程不是您当前已发布的正式考试安排",
                http_status=403,
            )
        _seat, _room, course, _batch = formal
        zone, _ = _tenant_timezone(db)
        exam_at = _local_exam_datetime(course, zone)
        if exam_at is None:
            raise AppException("DATA_CONFLICT", "考试时间不完整，不可申请缓考", http_status=409)
        if exam_started(course, zone=zone):
            raise AppException("DATA_CONFLICT", "考试已开始，不可申请缓考", http_status=409)
        active = db.scalars(select(AaDeferredExam).where(
            AaDeferredExam.tenant_id == _tid(), AaDeferredExam.student_id == student.id,
            AaDeferredExam.exam_course_id == course.id,
            AaDeferredExam.status.notin_(list(exam_contract.DEFER_TERMINAL_STATUSES)),
            AaDeferredExam.is_deleted.is_(False),
        )).first()
        if active:
            raise AppException("DATA_CONFLICT", "已有进行中的缓考申请", http_status=409)
        row = AaDeferredExam(
            tenant_id=_tid(), student_id=student.id, student_no=student.student_no,
            student_name=student.real_name, exam_course_id=course.id, course_name=course.course_name,
            reason_type=reason_type, reason=reason, apply_at=datetime.utcnow(),
            current_node="COUNSELOR", status=exam_contract.DEFER_STATUS_COUNSELOR_REVIEW,
        )
        db.add(row)
        db.flush()
        exam_contract.record_exam_audit(
            db, "DEFERRED_EXAM", row.id, "DEFER_APPLY_SUBMIT", f"缓考申请 {course.course_name}"
        )
        db.commit()
        db.refresh(row)
        return exam_contract.deferred_exam_dto(row)
