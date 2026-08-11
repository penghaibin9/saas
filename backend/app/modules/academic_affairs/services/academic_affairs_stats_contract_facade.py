"""教务统计 08/09/14 号卡唯一运行时合同。

历史 stats_service 同文件曾存在两套同名实现：后定义的简化补建版覆盖了更完整的生产实现，
导致页面聚合字段、下钻和 export_stats_xlsx 彼此不一致。这里集中保留完整合同并显式安装到
legacy 模块，让公开 Service 与 legacy 内部导出使用同一组函数。
"""
from __future__ import annotations

from sqlalchemy import func, select

from . import academic_affairs_stats_service as _legacy


def course_selection_stats(user, term_id=None, college_id=None) -> dict:
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        bq = select(AaSelectionBatch.id, AaSelectionBatch.status).where(
            AaSelectionBatch.tenant_id == _legacy._tid(), AaSelectionBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaSelectionBatch.term_id == int(term_id))
        batches = db.execute(bq).all()
        bids = [bid for bid, _status in batches] or [-1]
        cq = select(AaSelectionCourse).where(
            AaSelectionCourse.tenant_id == _legacy._tid(),
            AaSelectionCourse.batch_id.in_(bids),
            AaSelectionCourse.is_deleted.is_(False),
        )
        if colleges is not None:
            if not colleges:
                return {
                    "totalCapacity": 0, "totalSelected": 0, "lowEnrollCount": 0,
                    "fullCount": 0, "recordCount": 0, "byBatchStatus": [],
                    "scope": {"blocked": scope.blocked},
                }
            course_ids = set(db.scalars(select(AaCourse.id).where(
                AaCourse.tenant_id == _legacy._tid(),
                AaCourse.owner_college_id.in_(colleges),
                AaCourse.is_deleted.is_(False),
            )).all())
            cq = cq.where(AaSelectionCourse.course_id.in_(course_ids or [-1]))
        rows = list(db.scalars(cq).all())
        total_capacity = sum(int(row.capacity or 0) for row in rows)
        total_selected = sum(int(row.selected_count or 0) for row in rows)
        low_enroll = sum(1 for row in rows if int(row.selected_count or 0) < int(row.min_capacity or 0))
        full = sum(1 for row in rows if int(row.capacity or 0) > 0 and int(row.selected_count or 0) >= int(row.capacity or 0))
        selection_course_ids = [int(row.id) for row in rows] or [-1]
        record_count = int(db.scalar(select(func.count()).where(
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.selection_course_id.in_(selection_course_ids),
            AaSelectionRecord.is_deleted.is_(False),
        )) or 0)
        by_status: dict[str, int] = {}
        for _batch_id, status in batches:
            by_status[str(status or "UNKNOWN")] = by_status.get(str(status or "UNKNOWN"), 0) + 1
        return {
            "totalCapacity": total_capacity,
            "totalSelected": total_selected,
            "lowEnrollCount": low_enroll,
            "fullCount": full,
            "recordCount": record_count,
            "byBatchStatus": [{"key": key, "count": value} for key, value in sorted(by_status.items())],
            "scope": {"blocked": scope.blocked},
        }


def course_selection_detail(user, term_id=None, college_id=None, page=1, page_size=20):
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse

    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        bq = select(AaSelectionBatch.id).where(
            AaSelectionBatch.tenant_id == _legacy._tid(), AaSelectionBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaSelectionBatch.term_id == int(term_id))
        batch_ids = list(db.scalars(bq).all()) or [-1]
        q = select(AaSelectionCourse).where(
            AaSelectionCourse.tenant_id == _legacy._tid(),
            AaSelectionCourse.batch_id.in_(batch_ids),
            AaSelectionCourse.is_deleted.is_(False),
            AaSelectionCourse.selected_count < AaSelectionCourse.min_capacity,
        )
        if colleges is not None:
            if not colleges:
                return [], 0
            course_ids = set(db.scalars(select(AaCourse.id).where(
                AaCourse.tenant_id == _legacy._tid(),
                AaCourse.owner_college_id.in_(colleges),
                AaCourse.is_deleted.is_(False),
            )).all())
            q = q.where(AaSelectionCourse.course_id.in_(course_ids or [-1]))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(db.scalars(q.order_by(AaSelectionCourse.id.desc())
                               .offset((page - 1) * page_size).limit(page_size)).all())
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


def exam_stats(user, term_id=None, college_id=None) -> dict:
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident

    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        cq = select(AaExamCourse).where(
            AaExamCourse.tenant_id == _legacy._tid(), AaExamCourse.is_deleted.is_(False))
        if term_id:
            batch_ids = list(db.scalars(select(AaExamBatch.id).where(
                AaExamBatch.tenant_id == _legacy._tid(),
                AaExamBatch.term_id == int(term_id),
                AaExamBatch.is_deleted.is_(False),
            )).all())
            cq = cq.where(AaExamCourse.batch_id.in_(batch_ids or [-1]))
        if colleges is not None:
            if not colleges:
                return {
                    "courseTotal": 0, "confirmedCount": 0, "confirmRate": None,
                    "absentCount": 0, "violationCount": 0, "scope": {"blocked": scope.blocked},
                }
            cq = cq.where(AaExamCourse.college_id.in_(colleges))
        courses = list(db.scalars(cq).all())
        course_ids = [int(row.id) for row in courses] or [-1]
        course_total = len(courses)
        confirmed = sum(1 for row in courses if str(row.status or "").upper() == "CONFIRMED")
        incidents = list(db.scalars(select(AaExamIncident).where(
            AaExamIncident.tenant_id == _legacy._tid(),
            AaExamIncident.status == "ACTIVE",
            AaExamIncident.exam_course_id.in_(course_ids),
            AaExamIncident.is_deleted.is_(False),
        )).all())
        return {
            "courseTotal": course_total,
            "confirmedCount": confirmed,
            "confirmRate": round(confirmed / course_total * 100, 2) if course_total else None,
            "absentCount": sum(1 for row in incidents if row.incident_type == "ABSENT"),
            "violationCount": sum(1 for row in incidents if row.incident_type == "DISCIPLINE_VIOLATION"),
            "scope": {"blocked": scope.blocked},
        }


def exam_detail(user, term_id=None, college_id=None, incident_type=None, page=1, page_size=20):
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident

    with _legacy.session() as db:
        scope = _legacy._resolve_scope(user, db)
        _legacy._validate_college_param(scope, college_id)
        colleges = _legacy._college_ids_scope(db, scope, college_id)
        cq = select(AaExamCourse.id).where(
            AaExamCourse.tenant_id == _legacy._tid(), AaExamCourse.is_deleted.is_(False))
        if term_id:
            batch_ids = list(db.scalars(select(AaExamBatch.id).where(
                AaExamBatch.tenant_id == _legacy._tid(),
                AaExamBatch.term_id == int(term_id),
                AaExamBatch.is_deleted.is_(False),
            )).all())
            cq = cq.where(AaExamCourse.batch_id.in_(batch_ids or [-1]))
        if colleges is not None:
            if not colleges:
                return [], 0
            cq = cq.where(AaExamCourse.college_id.in_(colleges))
        course_ids = list(db.scalars(cq).all()) or [-1]
        q = select(AaExamIncident).where(
            AaExamIncident.tenant_id == _legacy._tid(),
            AaExamIncident.status == "ACTIVE",
            AaExamIncident.exam_course_id.in_(course_ids),
            AaExamIncident.is_deleted.is_(False),
        )
        if incident_type:
            q = q.where(AaExamIncident.incident_type == incident_type)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(db.scalars(q.order_by(AaExamIncident.id.desc())
                               .offset((page - 1) * page_size).limit(page_size)).all())
        items = []
        for row in rows:
            recorded_at = getattr(row, "recorded_at", None) or getattr(row, "created_at", None)
            items.append({
                "incidentId": str(row.id),
                "studentName": row.student_name or "",
                "studentNo": _legacy._mask_student_no(row.student_no),
                "incidentType": row.incident_type,
                "recordedAt": recorded_at.isoformat() if recorded_at else None,
            })
        _legacy._audit(db, "STATS_DRILL_EXAM", f"考务异常明细 total={total} type={incident_type or '-'}")
        db.commit()
        return items, total


def resource_stats(user) -> dict:
    from app.models import AaClassroom, AaClassroomBooking

    with _legacy.session() as db:
        rooms = list(db.scalars(select(AaClassroom).where(
            AaClassroom.tenant_id == _legacy._tid(), AaClassroom.is_deleted.is_(False))).all())
        by_status: dict[str, int] = {}
        for room in rooms:
            key = str(room.status or "UNKNOWN")
            by_status[key] = by_status.get(key, 0) + 1
        booking_total = int(db.scalar(select(func.count()).where(
            AaClassroomBooking.tenant_id == _legacy._tid(),
            AaClassroomBooking.status == "PENDING",
            AaClassroomBooking.is_deleted.is_(False),
        )) or 0)
        return {
            "classroomTotal": len(rooms),
            "bookingTotal": booking_total,
            "byStatus": [{"key": key, "count": value} for key, value in sorted(by_status.items())],
        }


def resource_detail(user, page=1, page_size=20):
    from app.models import AaClassroomBooking

    with _legacy.session() as db:
        q = select(AaClassroomBooking).where(
            AaClassroomBooking.tenant_id == _legacy._tid(),
            AaClassroomBooking.status == "PENDING",
            AaClassroomBooking.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(db.scalars(q.order_by(AaClassroomBooking.id.desc())
                               .offset((page - 1) * page_size).limit(page_size)).all())
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
