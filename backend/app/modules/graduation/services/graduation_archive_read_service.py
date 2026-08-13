from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models import GraduationArchiveRecord, GraduationStudent
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _tid, session


def _row(archive, student):
    from app.modules.graduation.services import graduation_archive_service as service

    item = service._row(archive, student)
    reasons = []
    if not str(student.name or "").strip():
        reasons.append("学生姓名缺失")
        item["studentName"] = "历史数据异常（姓名缺失）"
    if not str(student.student_no or "").strip():
        reasons.append("学号缺失")
        item["studentNo"] = "历史数据异常（学号缺失）"
    item["dataAnomaly"] = bool(reasons)
    item["anomalyReasons"] = reasons
    if reasons:
        item["allowedActions"] = []
    return item


def list_archives(page: int, page_size: int, keyword=None, status=None, batch_id=None):
    tid = _tid()
    p = max(1, int(page))
    size = min(200, max(1, int(page_size)))
    with session() as db:
        scope = student_scope_select(db, tid, batch_id=batch_id)
        join_on = GraduationStudent.id == GraduationArchiveRecord.gd_student_id
        filters = [
            GraduationArchiveRecord.tenant_id == tid,
            GraduationArchiveRecord.is_deleted.is_(False),
            GraduationStudent.tenant_id == tid,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope),
        ]
        if batch_id:
            filters.append(GraduationStudent.batch_id == int(batch_id))
        if status:
            filters.append(GraduationArchiveRecord.status == status)
        value = str(keyword or "").strip()
        if value:
            filters.append(or_(GraduationStudent.name.contains(value), GraduationStudent.student_no.contains(value)))

        total = int(db.scalar(
            select(func.count(func.distinct(GraduationArchiveRecord.id)))
            .select_from(GraduationArchiveRecord)
            .join(GraduationStudent, join_on)
            .where(*filters)
        ) or 0)

        rows = db.execute(
            select(GraduationArchiveRecord, GraduationStudent)
            .join(GraduationStudent, join_on)
            .where(*filters)
            .order_by(GraduationArchiveRecord.id.desc())
            .offset((p - 1) * size)
            .limit(size)
        ).all()
        return [_row(archive, student) for archive, student in rows], total
