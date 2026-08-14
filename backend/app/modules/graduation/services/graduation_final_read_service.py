"""成果审核 SQL 读模型：真分页、统一批次/数据范围、NOT EXISTS 未提交派生。"""
from __future__ import annotations

from sqlalchemy import and_, cast, exists, func, Numeric, or_, select

from app.models import GraduationFinal, GraduationStudent
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _iso

L_MAT = {
    "PENDING_REVIEW": "待审阅",
    "APPROVED": "已通过",
    "REJECTED": "已驳回",
    "NOT_SUBMITTED": "未提交",
}
FINAL_STAGES = ("GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE")


def _rate_over(rate, threshold=30) -> bool:
    try:
        return float(str(rate).replace("%", "")) > threshold
    except (TypeError, ValueError):
        return False


def _keyword_filter(keyword: str | None):
    kw = (keyword or "").strip()
    if not kw:
        return None
    return or_(
        GraduationStudent.name.contains(kw),
        GraduationStudent.student_no.contains(kw),
        GraduationStudent.topic_title.contains(kw),
    )


def _submitted_where(db, tenant_id: int, *, keyword=None, status=None, batch_id=None):
    scope = student_scope_select(db, tenant_id, batch_id=batch_id)
    conds = [
        GraduationFinal.tenant_id == int(tenant_id),
        GraduationFinal.is_deleted.is_(False),
        GraduationStudent.id.in_(scope),
    ]
    if status:
        conds.append(GraduationFinal.status == status)
    keyword_cond = _keyword_filter(keyword)
    if keyword_cond is not None:
        conds.append(keyword_cond)
    return conds


def _submitted_count(db, tenant_id: int, *, keyword=None, status=None, batch_id=None) -> int:
    conds = _submitted_where(db, tenant_id, keyword=keyword, status=status, batch_id=batch_id)
    return int(db.scalar(
        select(func.count()).select_from(GraduationFinal)
        .join(GraduationStudent, GraduationStudent.id == GraduationFinal.gd_student_id)
        .where(*conds)
    ) or 0)


def _final_row(final: GraduationFinal, student: GraduationStudent) -> dict:
    return {
        "id": str(final.id),
        "projectId": str(final.gd_student_id),
        "studentName": student.name,
        "className": student.class_name or "",
        "topicTitle": student.topic_title or "",
        "advisorName": student.advisor_name or "",
        "type": final.final_type,
        "version": final.version or "",
        "submitAt": _iso(final.submit_at) or "",
        "plagiarismRate": final.plagiarism_rate or "—",
        "plagiarismStatus": final.plagiarism_status or "未检测",
        "plagiarismTone": "danger" if _rate_over(final.plagiarism_rate) else "success",
        "status": final.status,
        "statusLabel": L_MAT.get(final.status, final.status),
    }


def _submitted_page(db, tenant_id: int, *, offset: int, limit: int, keyword=None, status=None, batch_id=None):
    if limit <= 0:
        return []
    conds = _submitted_where(db, tenant_id, keyword=keyword, status=status, batch_id=batch_id)
    rows = db.execute(
        select(GraduationFinal, GraduationStudent)
        .join(GraduationStudent, GraduationStudent.id == GraduationFinal.gd_student_id)
        .where(*conds)
        .order_by(GraduationFinal.id.desc())
        .offset(max(0, int(offset))).limit(int(limit))
    ).all()
    return [_final_row(final, student) for final, student in rows]


def _not_submitted_where(db, tenant_id: int, *, keyword=None, batch_id=None):
    scope = student_scope_select(db, tenant_id, batch_id=batch_id)
    final_exists = exists(select(GraduationFinal.id).where(
        GraduationFinal.tenant_id == int(tenant_id),
        GraduationFinal.gd_student_id == GraduationStudent.id,
        GraduationFinal.is_deleted.is_(False),
    ))
    conds = [
        GraduationStudent.id.in_(scope),
        GraduationStudent.stage.in_(FINAL_STAGES),
        ~final_exists,
    ]
    keyword_cond = _keyword_filter(keyword)
    if keyword_cond is not None:
        conds.append(keyword_cond)
    return conds


def count_not_submitted(db, tenant_id: int, *, keyword=None, batch_id=None) -> int:
    return int(db.scalar(
        select(func.count()).select_from(GraduationStudent).where(
            *_not_submitted_where(db, tenant_id, keyword=keyword, batch_id=batch_id)
        )
    ) or 0)


def _not_submitted_row(student: GraduationStudent) -> dict:
    return {
        "id": f"S{student.id}",
        "projectId": str(student.id),
        "gdStudentId": str(student.id),
        "studentName": student.name,
        "className": student.class_name or "",
        "topicTitle": student.topic_title or "（未确认选题）",
        "advisorName": student.advisor_name or "",
        "type": "—",
        "version": "—",
        "submitAt": "",
        "plagiarismRate": "—",
        "plagiarismStatus": "未提交",
        "plagiarismTone": "warning",
        "status": "NOT_SUBMITTED",
        "statusLabel": L_MAT["NOT_SUBMITTED"],
    }


def _not_submitted_page(db, tenant_id: int, *, offset: int, limit: int, keyword=None, batch_id=None):
    if limit <= 0:
        return []
    rows = db.scalars(
        select(GraduationStudent)
        .where(*_not_submitted_where(db, tenant_id, keyword=keyword, batch_id=batch_id))
        .order_by(GraduationStudent.id)
        .offset(max(0, int(offset))).limit(int(limit))
    ).all()
    return [_not_submitted_row(student) for student in rows]


def list_finals(db, tenant_id: int, page: int, page_size: int, *, keyword=None, status=None, batch_id=None):
    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 20))
    offset = (page - 1) * page_size
    status = (status or "").strip().upper()

    if status == "NOT_SUBMITTED":
        total = count_not_submitted(db, tenant_id, keyword=keyword, batch_id=batch_id)
        return _not_submitted_page(
            db, tenant_id, offset=offset, limit=page_size, keyword=keyword, batch_id=batch_id
        ), total

    if status:
        total = _submitted_count(db, tenant_id, keyword=keyword, status=status, batch_id=batch_id)
        return _submitted_page(
            db, tenant_id, offset=offset, limit=page_size,
            keyword=keyword, status=status, batch_id=batch_id,
        ), total

    submitted_total = _submitted_count(db, tenant_id, keyword=keyword, batch_id=batch_id)
    missing_total = count_not_submitted(db, tenant_id, keyword=keyword, batch_id=batch_id)
    total = submitted_total + missing_total
    rows: list[dict] = []
    if offset < submitted_total:
        take = min(page_size, submitted_total - offset)
        rows.extend(_submitted_page(
            db, tenant_id, offset=offset, limit=take, keyword=keyword, batch_id=batch_id
        ))
        remain = page_size - len(rows)
        if remain > 0:
            rows.extend(_not_submitted_page(
                db, tenant_id, offset=0, limit=remain, keyword=keyword, batch_id=batch_id
            ))
    elif offset < total:
        rows.extend(_not_submitted_page(
            db, tenant_id, offset=offset - submitted_total, limit=page_size,
            keyword=keyword, batch_id=batch_id,
        ))
    return rows, total


def final_stats(db, tenant_id: int, *, batch_id=None) -> dict:
    total = _submitted_count(db, tenant_id, batch_id=batch_id)
    by_status = [
        {
            "status": status,
            "label": L_MAT[status],
            "count": _submitted_count(db, tenant_id, status=status, batch_id=batch_id),
        }
        for status in ("PENDING_REVIEW", "APPROVED", "REJECTED")
    ]
    conds = _submitted_where(db, tenant_id, batch_id=batch_id)
    numeric_rate = cast(func.replace(GraduationFinal.plagiarism_rate, "%", ""), Numeric(10, 2))
    plagiarism_over = int(db.scalar(
        select(func.count()).select_from(GraduationFinal)
        .join(GraduationStudent, GraduationStudent.id == GraduationFinal.gd_student_id)
        .where(*conds, GraduationFinal.plagiarism_rate.is_not(None), numeric_rate > 30)
    ) or 0)
    return {
        "total": total,
        "byStatus": by_status,
        "plagiarismOver": plagiarism_over,
        "batchId": str(batch_id) if batch_id else None,
    }


def iter_finals(db, tenant_id: int, *, keyword=None, status=None, batch_id=None, chunk_size: int = 200):
    page = 1
    written = 0
    while True:
        rows, total = list_finals(
            db, tenant_id, page, chunk_size,
            keyword=keyword, status=status, batch_id=batch_id,
        )
        if not rows:
            break
        for row in rows:
            yield row
            written += 1
        if written >= total:
            break
        page += 1
