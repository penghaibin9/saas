"""教务统计 08/09/14 号卡唯一运行时合同。

历史 stats_service 同文件曾存在两套同名实现：后定义的简化补建版覆盖了更完整的生产实现，
导致页面聚合字段、下钻和 export_stats_xlsx 彼此不一致。这里集中保留完整合同并显式安装到
legacy 模块，让公开 Service 与 legacy 内部导出使用同一组函数。

PR #101 生产复审：聚合必须在 SQL 完成；下钻必须使用有界分页和子查询范围，禁止先把整批
batch/course/id 列表 materialize 到 Python 再做 count/filter。
"""
from __future__ import annotations

from sqlalchemy import and_, case, func, select

from app.core.exceptions import AppException

from . import academic_affairs_stats_service as _legacy


_MAX_PAGE_SIZE = 200


def _page_values(page, page_size) -> tuple[int, int]:
    try:
        page_no = int(1 if page is None else page)
        size = int(20 if page_size is None else page_size)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page/pageSize 必须为整数") from None
    if page_no < 1:
        raise AppException("VALIDATION_ERROR", "page 必须大于等于 1")
    if size < 1 or size > _MAX_PAGE_SIZE:
        raise AppException("VALIDATION_ERROR", f"pageSize 必须在 1-{_MAX_PAGE_SIZE} 之间")
    return page_no, size


def _mask_student_no(value) -> str:
    """统计下钻只返回不可逆展示掩码，不依赖历史模块的私有 helper/import 顺序。"""
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"


def _selection_scope_queries(term_id, colleges):
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse

    batch_conditions = [
        AaSelectionBatch.tenant_id == _legacy._tid(),
        AaSelectionBatch.is_deleted.is_(False),
    ]
    if term_id:
        batch_conditions.append(AaSelectionBatch.term_id == int(term_id))
    batch_ids = select(AaSelectionBatch.id).where(*batch_conditions)

    course_conditions = [
        AaSelectionCourse.tenant_id == _legacy._tid(),
        AaSelectionCourse.batch_id.in_(batch_ids),
        AaSelectionCourse.is_deleted.is_(False),
    ]
    if colleges is not None:
        course_ids = select(AaCourse.id).where(
            AaCourse.tenant_id == _legacy._tid(),
            AaCourse.owner_college_id.in_(colleges),
            AaCourse.is_deleted.is_(False),
        )
        course_conditions.append(AaSelectionCourse.course_id.in_(course_ids))
    return batch_conditions, course_conditions


def course_selection_stats(user, term_id=None, college_id=None) -> dict:
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        if colleges is not None and not colleges:
            return {
                "totalCapacity": 0, "totalSelected": 0, "lowEnrollCount": 0,
                "fullCount": 0, "recordCount": 0, "byBatchStatus": [],
                "scope": {"blocked": scope.blocked},
            }

        batch_conditions, course_conditions = _selection_scope_queries(term_id, colleges)
        total_capacity, total_selected, low_enroll, full = db.execute(
            select(
                func.coalesce(func.sum(AaSelectionCourse.capacity), 0),
                func.coalesce(func.sum(AaSelectionCourse.selected_count), 0),
                func.coalesce(func.sum(case((
                    func.coalesce(AaSelectionCourse.selected_count, 0)
                    < func.coalesce(AaSelectionCourse.min_capacity, 0), 1
                ), else_=0)), 0),
                func.coalesce(func.sum(case((and_(
                    func.coalesce(AaSelectionCourse.capacity, 0) > 0,
                    func.coalesce(AaSelectionCourse.selected_count, 0)
                    >= func.coalesce(AaSelectionCourse.capacity, 0),
                ), 1), else_=0)), 0),
            ).where(*course_conditions)
        ).one()

        selection_course_ids = select(AaSelectionCourse.id).where(*course_conditions)
        record_count = int(db.scalar(select(func.count(AaSelectionRecord.id)).where(
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.selection_course_id.in_(selection_course_ids),
            AaSelectionRecord.is_deleted.is_(False),
        )) or 0)
        grouped = db.execute(
            select(AaSelectionBatch.status, func.count(AaSelectionBatch.id))
            .where(*batch_conditions)
            .group_by(AaSelectionBatch.status)
        ).all()
        return {
            "totalCapacity": int(total_capacity or 0),
            "totalSelected": int(total_selected or 0),
            "lowEnrollCount": int(low_enroll or 0),
            "fullCount": int(full or 0),
            "recordCount": record_count,
            "byBatchStatus": [
                {"key": str(status or "UNKNOWN"), "count": int(count or 0)}
                for status, count in sorted(grouped, key=lambda row: str(row[0] or "UNKNOWN"))
            ],
            "scope": {"blocked": scope.blocked},
        }


def course_selection_detail(user, term_id=None, college_id=None, page=1, page_size=20):
    from app.models import AaSelectionCourse

    page_no, size = _page_values(page, page_size)
    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        if colleges is not None and not colleges:
            return [], 0
        _batch_conditions, course_conditions = _selection_scope_queries(term_id, colleges)
        course_conditions.append(
            func.coalesce(AaSelectionCourse.selected_count, 0)
            < func.coalesce(AaSelectionCourse.min_capacity, 0)
        )
        q = select(AaSelectionCourse).where(*course_conditions)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(db.scalars(
            q.order_by(AaSelectionCourse.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all())
        items = [{
            "selectionCourseId": str(row.id),
            "courseName": row.course_name or "",
            "capacity": row.capacity,
            "minCapacity": row.min_capacity,
            "selectedCount": row.selected_count,
            "status": row.status,
        } for row in rows]
        _legacy._audit(db, "STATS_DRILL_SELECTION", f"低人数课程明细 total={total} college={college_id or '-'}")
        db.commit()
        return items, total


def _exam_course_conditions(term_id, colleges):
    from app.models import AaExamBatch, AaExamCourse

    conditions = [
        AaExamCourse.tenant_id == _legacy._tid(),
        AaExamCourse.is_deleted.is_(False),
    ]
    if term_id:
        batch_ids = select(AaExamBatch.id).where(
            AaExamBatch.tenant_id == _legacy._tid(),
            AaExamBatch.term_id == int(term_id),
            AaExamBatch.is_deleted.is_(False),
        )
        conditions.append(AaExamCourse.batch_id.in_(batch_ids))
    if colleges is not None:
        conditions.append(AaExamCourse.college_id.in_(colleges))
    return conditions


def exam_stats(user, term_id=None, college_id=None) -> dict:
    from app.models import AaExamCourse, AaExamIncident

    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        if colleges is not None and not colleges:
            return {
                "courseTotal": 0, "confirmedCount": 0, "confirmRate": None,
                "absentCount": 0, "violationCount": 0, "scope": {"blocked": scope.blocked},
            }

        course_conditions = _exam_course_conditions(term_id, colleges)
        course_total, confirmed = db.execute(
            select(
                func.count(AaExamCourse.id),
                func.coalesce(func.sum(case((AaExamCourse.status == "CONFIRMED", 1), else_=0)), 0),
            ).where(*course_conditions)
        ).one()
        course_total, confirmed = int(course_total or 0), int(confirmed or 0)
        course_ids = select(AaExamCourse.id).where(*course_conditions)
        absent, violation = db.execute(
            select(
                func.coalesce(func.sum(case((AaExamIncident.incident_type == "ABSENT", 1), else_=0)), 0),
                func.coalesce(func.sum(case((
                    AaExamIncident.incident_type == "DISCIPLINE_VIOLATION", 1
                ), else_=0)), 0),
            ).where(
                AaExamIncident.tenant_id == _legacy._tid(),
                AaExamIncident.status == "ACTIVE",
                AaExamIncident.exam_course_id.in_(course_ids),
                AaExamIncident.is_deleted.is_(False),
            )
        ).one()
        return {
            "courseTotal": course_total,
            "confirmedCount": confirmed,
            "confirmRate": round(confirmed / course_total * 100, 2) if course_total else None,
            "absentCount": int(absent or 0),
            "violationCount": int(violation or 0),
            "scope": {"blocked": scope.blocked},
        }


def exam_detail(user, term_id=None, college_id=None, incident_type=None, page=1, page_size=20):
    from app.models import AaExamCourse, AaExamIncident

    page_no, size = _page_values(page, page_size)
    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        if colleges is not None and not colleges:
            return [], 0
        course_ids = select(AaExamCourse.id).where(*_exam_course_conditions(term_id, colleges))
        q = select(AaExamIncident).where(
            AaExamIncident.tenant_id == _legacy._tid(),
            AaExamIncident.status == "ACTIVE",
            AaExamIncident.exam_course_id.in_(course_ids),
            AaExamIncident.is_deleted.is_(False),
        )
        if incident_type:
            q = q.where(AaExamIncident.incident_type == incident_type)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(db.scalars(
            q.order_by(AaExamIncident.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all())
        items = []
        for row in rows:
            recorded_at = getattr(row, "recorded_at", None) or getattr(row, "created_at", None)
            items.append({
                "incidentId": str(row.id),
                "studentName": row.student_name or "",
                "studentNo": _mask_student_no(row.student_no),
                "incidentType": row.incident_type,
                "recordedAt": recorded_at.isoformat() if recorded_at else None,
            })
        _legacy._audit(db, "STATS_DRILL_EXAM", f"考务异常明细 total={total} type={incident_type or '-'}")
        db.commit()
        return items, total


def resource_stats(user) -> dict:
    from app.models import AaClassroom, AaClassroomBooking

    with _legacy.session() as db:
        grouped = db.execute(
            select(AaClassroom.status, func.count(AaClassroom.id))
            .where(AaClassroom.tenant_id == _legacy._tid(), AaClassroom.is_deleted.is_(False))
            .group_by(AaClassroom.status)
        ).all()
        booking_total = int(db.scalar(select(func.count(AaClassroomBooking.id)).where(
            AaClassroomBooking.tenant_id == _legacy._tid(),
            AaClassroomBooking.status == "PENDING",
            AaClassroomBooking.is_deleted.is_(False),
        )) or 0)
        return {
            "classroomTotal": sum(int(count or 0) for _status, count in grouped),
            "bookingTotal": booking_total,
            "byStatus": [
                {"key": str(status or "UNKNOWN"), "count": int(count or 0)}
                for status, count in sorted(grouped, key=lambda row: str(row[0] or "UNKNOWN"))
            ],
        }


def resource_detail(user, page=1, page_size=20):
    from app.models import AaClassroomBooking

    page_no, size = _page_values(page, page_size)
    with _legacy.session() as db:
        q = select(AaClassroomBooking).where(
            AaClassroomBooking.tenant_id == _legacy._tid(),
            AaClassroomBooking.status == "PENDING",
            AaClassroomBooking.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(db.scalars(
            q.order_by(AaClassroomBooking.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all())
        items = [{
            "bookingId": str(row.id),
            "classroomText": row.classroom_text or "",
            "bookingDate": row.booking_date,
            "slotNo": row.slot_no,
            "purpose": row.purpose or "",
            "applicantName": row.applicant_name or "",
            "status": row.status,
        } for row in rows]
        _legacy._audit(db, "STATS_DRILL_RESOURCE", f"待审预约明细 total={total}")
        db.commit()
        return items, total


def install() -> None:
    """覆盖历史同名重复定义；legacy 内部 export 的全局查找也会命中这些 canonical 函数。"""
    _legacy.course_selection_stats = course_selection_stats
    _legacy.course_selection_detail = course_selection_detail
    _legacy.exam_stats = exam_stats
    _legacy.exam_detail = exam_detail
    _legacy.resource_stats = resource_stats
    _legacy.resource_detail = resource_detail
