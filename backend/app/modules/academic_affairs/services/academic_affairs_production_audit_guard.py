"""PR #101 production-audit hardening without creating new business truth.

This guard only tightens read-side scope/pagination contracts that were introduced by
D2/D6-D8 convenience/read refactors. Canonical write services, state machines, DTOs and
persistent facts remain owned by their existing modules.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from functools import wraps

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException

_MAX_PAGE_SIZE = 200


def _bounded_page_size(value, *, default: int) -> int:
    try:
        size = int(value if value is not None else default)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "pageSize 必须为整数") from None
    if size < 1 or size > _MAX_PAGE_SIZE:
        raise AppException(
            "VALIDATION_ERROR",
            f"pageSize 必须在 1-{_MAX_PAGE_SIZE} 之间",
        )
    return size


def _selection_scope_values(db, ctx):
    """Only TENANT_ALL is unscoped; every other staff identity is explicitly narrowed."""
    from . import academic_affairs_selection_read_service as read

    scope_type = str(getattr(ctx, "scope_type", "") or "").upper()
    if scope_type == "TENANT_ALL":
        return None

    roles = {str(value or "").upper() for value in (getattr(ctx, "role_codes", set()) or set())}
    if "ACADEMIC_TEACHER" in roles:
        identity = {
            "userId": str(getattr(ctx, "user_id", "") or ""),
            "loginName": str(getattr(ctx, "login_name", "") or ""),
        }
        teacher_keys = {str(value) for value in read._core._derive_keys(identity) if str(value)}
        if not teacher_keys:
            raise no_data_scope("当前教师身份无法解析本人授课范围")
        # Teacher visibility is always COURSE/teacher-key based. A coincidental class scope
        # must never widen a teacher from "own course" to "all courses in the class".
        return set(), set(), teacher_keys

    if scope_type in {"COLLEGE", "CLASS"}:
        class_ids = {int(value) for value in (ctx.allowed_class_ids(db) or set())}
        college_ids = {
            int(value) for value in (getattr(ctx, "college_ids", set()) or set())
            if value is not None
        }
        if not class_ids and not college_ids:
            raise no_data_scope("当前身份未配置选课班级或学院数据范围")
        return class_ids, college_ids, set()

    # STUDENT/SELF/NONE/DORM_BUILDING and any future unknown scope must not silently
    # become tenant-wide merely because the caller has selection.view permission.
    raise no_data_scope("当前身份未配置可用的选课数据范围")


def _selection_scope_course_query(query, scoped):
    if scoped is None:
        return query

    from app.models import AaSelectionCourse, AaTeachingTask, AaTeachingTaskBatch
    from . import academic_affairs_selection_read_service as read

    class_ids, college_ids, teacher_keys = scoped
    predicates = []
    if teacher_keys:
        predicates.append(AaTeachingTask.teacher_key.in_(sorted(teacher_keys)))
    else:
        if class_ids:
            predicates.append(AaTeachingTask.class_id.in_(sorted(class_ids)))
        if college_ids:
            predicates.append(AaTeachingTaskBatch.college_id.in_(sorted(college_ids)))
    if not predicates:
        raise no_data_scope("当前身份未配置可用的选课课程范围")

    return (
        query.join(AaTeachingTask, AaTeachingTask.id == AaSelectionCourse.teaching_task_id)
        .join(AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id)
        .filter(
            AaTeachingTask.tenant_id == read._core._tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTaskBatch.tenant_id == read._core._tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
            or_(*predicates),
        )
    )


def _roster_sql(user, keyword=None, status=None, page=1, page_size=20):
    """Keep the roster contract while pushing scope, search, count and paging into SQL."""
    from app.core.field_crypto import mask_id_card_encrypted
    from app.models import StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    from . import academic_affairs_service as roster_read

    try:
        page_no = max(1, int(page or 1))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    size = _bounded_page_size(page_size, default=20)
    with roster_read.session() as db:
        ctx = build_affairs_context(user, db)
        conditions = [
            StudentProfile.tenant_id == roster_read._tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        if status:
            conditions.append(StudentProfile.student_status == status)
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None:
            conditions.append(
                StudentProfile.class_id.in_(sorted(allowed)) if allowed else StudentProfile.id == -1
            )
        term = str(keyword or "").strip()
        if term:
            conditions.append(or_(
                StudentProfile.real_name.contains(term, autoescape=True),
                StudentProfile.student_no.contains(term, autoescape=True),
            ))

        total = int(db.scalar(select(func.count(StudentProfile.id)).where(*conditions)) or 0)
        rows = db.scalars(
            select(StudentProfile)
            .where(*conditions)
            .order_by(StudentProfile.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [
            {
                "studentId": str(student.id),
                "studentNo": student.student_no,
                "realName": student.real_name,
                "className": str(student.class_id or ""),
                "studentStatus": student.student_status,
                "enrolled": is_enrolled(student.student_status),
                "idCardMasked": mask_id_card_encrypted(student.id_card_encrypted),
            }
            for student in rows
        ], total


def _roster_status_summary_sql(user) -> dict:
    """Aggregate the 20k+ student roster in SQL instead of materializing every profile."""
    from app.models import AaStatusChange, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    from . import academic_affairs_service as roster_read

    with roster_read.session() as db:
        ctx = build_affairs_context(user, db)
        conditions = [
            StudentProfile.tenant_id == roster_read._tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None:
            conditions.append(
                StudentProfile.class_id.in_(sorted(allowed)) if allowed else StudentProfile.id == -1
            )

        grouped = db.execute(
            select(StudentProfile.student_status, func.count(StudentProfile.id))
            .where(*conditions)
            .group_by(StudentProfile.student_status)
        ).all()
        counts = {str(status or ""): int(count or 0) for status, count in grouped}
        total = sum(counts.values())
        enrolled_count = sum(
            count for status, count in counts.items() if is_enrolled(status)
        )

        since = datetime.utcnow() - timedelta(days=30)
        change_conditions = [
            AaStatusChange.tenant_id == roster_read._tid(),
            AaStatusChange.is_deleted.is_(False),
            AaStatusChange.status == "EFFECTIVE",
            AaStatusChange.effective_date >= since,
        ]
        if allowed is not None:
            if allowed:
                allowed_values = sorted(allowed)
                change_conditions.append(or_(
                    AaStatusChange.from_class_id.in_(allowed_values),
                    AaStatusChange.to_class_id.in_(allowed_values),
                ))
            else:
                change_conditions.append(AaStatusChange.id == -1)
        recent = int(
            db.scalar(select(func.count()).select_from(AaStatusChange).where(*change_conditions)) or 0
        )
        return {
            "total": total,
            "byStatus": [
                {
                    "status": status,
                    "label": roster_read._STATUS_LABEL.get(status, status),
                    "count": count,
                }
                for status, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "enrolledCount": enrolled_count,
            "notEnrolledCount": total - enrolled_count,
            "recentChanges30d": recent,
        }


def _registration_archive_list_sql(user, page=1, page_size=20):
    """Archived registration batches are school-wide records: TENANT_ALL + true SQL paging."""
    from app.models import AaRegistrationBatch
    from . import academic_affairs_service as roster_read

    try:
        page_no = max(1, int(page or 1))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    size = _bounded_page_size(page_size, default=20)
    with roster_read.session() as db:
        ctx = build_affairs_context(user, db)
        roster_read._require_school_scope(ctx)
        conditions = [
            AaRegistrationBatch.tenant_id == roster_read._tid(),
            AaRegistrationBatch.is_deleted.is_(False),
            AaRegistrationBatch.status == "ARCHIVED",
        ]
        total = int(db.scalar(select(func.count(AaRegistrationBatch.id)).where(*conditions)) or 0)
        rows = db.scalars(
            select(AaRegistrationBatch)
            .where(*conditions)
            .order_by(AaRegistrationBatch.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [
            {
                "batchId": str(batch.id),
                "batchName": batch.batch_name,
                "registerType": batch.register_type,
                "status": batch.status,
            }
            for batch in rows
        ], total


def _registration_archive_detail_sql(batch_id, user) -> dict:
    """Never derive archive totals from an arbitrary 10k page; count the immutable ledger in SQL."""
    from app.models import AaRegistration, AaRegistrationBatch
    from . import academic_affairs_service as roster_read

    with roster_read.session() as db:
        ctx = build_affairs_context(user, db)
        roster_read._require_school_scope(ctx)
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != roster_read._tid():
            raise roster_read.not_found("注册批次不存在")
        if batch.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "仅已归档批次可查看归档详情", http_status=409)
        conditions = [
            AaRegistration.tenant_id == roster_read._tid(),
            AaRegistration.batch_id == batch.id,
            AaRegistration.is_deleted.is_(False),
        ]
        total = int(db.scalar(select(func.count(AaRegistration.id)).where(*conditions)) or 0)
        registered = int(db.scalar(
            select(func.count(AaRegistration.id)).where(
                *conditions,
                AaRegistration.status == "REGISTERED",
            )
        ) or 0)
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "registerType": batch.register_type,
            "status": batch.status,
            "termId": str(batch.term_id) if batch.term_id else None,
            "windowStart": roster_read._iso(batch.window_start),
            "windowEnd": roster_read._iso(batch.window_end),
            "archivedAt": roster_read._iso(batch.updated_at),
            "stats": {"total": total, "registered": registered},
        }


def _registration_archive_export_full(batch_id, user, purpose="") -> bytes:
    """Export every archived registration row; never silently truncate at 10k."""
    from app.models import AaRegistration, AaRegistrationBatch, StudentProfile
    from app.services.xlsx_util import build_ledger_xlsx
    from . import academic_affairs_service as roster_read

    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    with roster_read.session() as db:
        ctx = build_affairs_context(user, db)
        roster_read._require_school_scope(ctx)
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != roster_read._tid():
            raise roster_read.not_found("注册批次不存在")
        if batch.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "仅已归档批次可导出归档台账", http_status=409)
        batch_name = batch.batch_name
        register_type = batch.register_type
        join = and_(
            StudentProfile.id == AaRegistration.student_id,
            StudentProfile.tenant_id == AaRegistration.tenant_id,
        )
        records = db.execute(
            select(AaRegistration, StudentProfile)
            .outerjoin(StudentProfile, join)
            .where(
                AaRegistration.tenant_id == roster_read._tid(),
                AaRegistration.batch_id == batch.id,
                AaRegistration.is_deleted.is_(False),
            )
            .order_by(AaRegistration.id.desc())
        ).all()

    operator_name, _role, _uid = roster_read._op()
    watermark = (
        f"导出人：{operator_name or '-'}  时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  "
        f"用途：{purpose}"
    )
    headers = ["学号", "姓名", "状态", "注册时间"]
    rows = [
        [
            student.student_no if student else "",
            student.real_name if student else "",
            "已注册" if record.status == "REGISTERED" else record.status,
            roster_read._iso(record.register_at) or "",
        ]
        for record, student in records
    ]
    title = (
        f"注册归档台账 · {batch_name}"
        f"（{roster_read._REG_TYPE_LABEL.get(register_type, register_type)}）"
    )
    content = build_ledger_xlsx(title, headers, rows, watermark=watermark)
    with roster_read.session() as db:
        roster_read._audit(db, "AA_REG_BATCH", batch_id, "ARCHIVE_EXPORT", f"用途={purpose[:100]}")
        db.commit()
    return content


def _escape_like(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _redact_conflict_detail(value) -> str:
    """Keep the existing human-readable detail contract without returning student PII."""
    text = str(value or "")
    text = re.sub(r"studentNo=[^ ]*", "studentNo=***", text, count=1)
    text = re.sub(r"studentName=.*? courseName=", "studentName=*** courseName=", text, count=1)
    return text


def _selection_conflict_report(user, batch_id, student_no=None, page=1, page_size=50):
    """SQL aggregate + paged drilldown; exact studentNo matching treats LIKE wildcards literally."""
    from app.models import AaSelectionCourse, AffairsAuditTrail
    from . import academic_affairs_selection_read_service as read

    try:
        page_no = max(1, int(page or 1))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    size = _bounded_page_size(page_size, default=50)
    with read._core.session() as db:
        ctx = read._core._ctx(user, db)
        scoped = read._scope_values(db, ctx)
        batch = read._core._get_batch(db, int(batch_id))
        read._require_batch_visible(db, int(batch.id), scoped)
        course_rows = read._course_query(db, int(batch.id), scoped).with_entities(
            AaSelectionCourse.id,
            AaSelectionCourse.course_name,
        ).all()
        course_ids = [int(cid) for cid, _name in course_rows]
        course_names = {int(cid): (name or "") for cid, name in course_rows}
        if not course_ids:
            return {
                "batchId": str(batch.id), "summary": [], "items": [],
                "total": 0, "page": page_no, "pageSize": size,
            }

        conditions = [
            AffairsAuditTrail.tenant_id == read._core._tid(),
            AffairsAuditTrail.biz_type == "AA_SELECTION_CONFLICT",
            AffairsAuditTrail.action == "SELECTION_CONFLICT_REJECT",
            AffairsAuditTrail.biz_id.in_(course_ids),
        ]
        normalized_student_no = str(student_no or "").strip()
        if normalized_student_no:
            escaped = _escape_like(normalized_student_no[:50])
            conditions.append(
                AffairsAuditTrail.detail.like(f"%studentNo={escaped} %", escape="\\")
            )

        summary_rows = db.query(
            AffairsAuditTrail.biz_id,
            func.count(AffairsAuditTrail.id),
        ).filter(*conditions).group_by(AffairsAuditTrail.biz_id).all()
        summary = [
            {
                "courseName": course_names.get(int(cid), ""),
                "conflictRejectCount": int(count or 0),
            }
            for cid, count in sorted(
                summary_rows,
                key=lambda item: (-int(item[1] or 0), course_names.get(int(item[0]), "")),
            )
        ]
        total = sum(item["conflictRejectCount"] for item in summary)
        rows = db.query(AffairsAuditTrail).filter(*conditions).order_by(
            AffairsAuditTrail.occurred_at.desc(), AffairsAuditTrail.id.desc()
        ).offset((page_no - 1) * size).limit(size).all()
        items = [
            {
                "occurredAt": read._core._iso(row.occurred_at),
                "courseName": course_names.get(int(row.biz_id), ""),
                "detail": _redact_conflict_detail(row.detail),
            }
            for row in rows
        ]
        if normalized_student_no:
            read._core._audit(
                db,
                int(batch.id),
                "SELECTION_CONFLICT_QUERY",
                f"按学号查询冲突详情 studentNo={normalized_student_no[:50]}",
            )
            db.commit()
        return {
            "batchId": str(batch.id),
            "summary": summary,
            "items": items,
            "total": total,
            "page": page_no,
            "pageSize": size,
        }


def _wrap_page_size(func, *, position: int, default: int):
    """Reject oversized internal calls too; Router validation is not the only safety boundary."""
    @wraps(func)
    def wrapped(*args, **kwargs):
        args_list = list(args)
        if "page_size" in kwargs:
            kwargs["page_size"] = _bounded_page_size(kwargs["page_size"], default=default)
        elif len(args_list) > position:
            args_list[position] = _bounded_page_size(args_list[position], default=default)
        else:
            kwargs["page_size"] = _bounded_page_size(None, default=default)
        return func(*args_list, **kwargs)

    return wrapped


def install() -> None:
    """Idempotently tighten only the audited read-side functions."""
    from . import academic_affairs_service as roster_read
    from . import academic_affairs_selection_read_service as selection_read
    from . import academic_affairs_selection_final_service as selection_public
    from . import exam_convenience_service as exam_read
    from . import academic_affairs_grade_task_read_service as grade_task_read
    from . import academic_affairs_grade_recheck_read_service as grade_recheck_read
    from . import academic_affairs_recognition_read_service as recognition_read

    if getattr(selection_read, "_production_audit_guard_installed", False):
        return

    roster_read.roster = _roster_sql
    roster_read.roster_status_summary = _roster_status_summary_sql
    roster_read.list_archived_registration_batches = _registration_archive_list_sql
    roster_read.registration_archive_detail = _registration_archive_detail_sql
    roster_read.export_registration_archive_xlsx = _registration_archive_export_full

    selection_read._scope_values = _selection_scope_values
    selection_read._scope_course_query = _selection_scope_course_query

    selection_read.list_batches = _wrap_page_size(selection_read.list_batches, position=4, default=20)
    selection_read.list_courses = _wrap_page_size(selection_read.list_courses, position=3, default=50)
    selection_read.course_roster = _wrap_page_size(selection_read.course_roster, position=3, default=50)
    selection_read.get_conflict_report = _selection_conflict_report

    # Selection Final is the public module object; refresh only the read-side attributes that
    # services/__init__.py already delegates to selection_read_service.
    for name in ("list_batches", "list_courses", "course_roster", "get_conflict_report"):
        setattr(selection_public, name, getattr(selection_read, name))

    exam_read.list_course_candidates = _wrap_page_size(exam_read.list_course_candidates, position=5, default=20)
    exam_read.list_courses = _wrap_page_size(exam_read.list_courses, position=3, default=100)
    grade_task_read.list_tasks = _wrap_page_size(grade_task_read.list_tasks, position=3, default=20)
    grade_recheck_read.list_all = _wrap_page_size(grade_recheck_read.list_all, position=3, default=50)
    recognition_read.list_all = _wrap_page_size(recognition_read.list_all, position=3, default=50)

    selection_read._production_audit_guard_installed = True
