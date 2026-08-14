"""教师移动端毕业设计列表的 SQL 真分页读模型。

V9.2 U8/M6：禁止先收齐整批数据再由 Router 二次分页。任务书/中期/成绩
均在 MySQL 侧完成 batch + dataScope + COUNT + ORDER/OFFSET/LIMIT；写链仍由原
领域 Service 负责。本模块只提供教师移动端读投影。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import GraduationMidterm, GraduationStudent, GraduationTaskBook
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _tid, session

_ACTIONABLE_MIDTERM_STATUSES = ("PENDING", "RECTIFY_SUBMITTED")


def _batch_id(user: dict) -> int:
    value = (user or {}).get("graduationBatchId") or (user or {}).get("batchId")
    if value in (None, ""):
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "毕业设计批次无效") from None


def _page(page, page_size) -> tuple[int, int]:
    return max(1, int(page or 1)), min(100, max(1, int(page_size or 20)))


def _result(items, total, page, page_size) -> dict:
    page, page_size = _page(page, page_size)
    return {
        "items": list(items or []),
        "total": int(total or 0),
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < int(total or 0),
    }


def taskbooks_page(user: dict, page=1, page_size=20) -> dict:
    from app.db.session import db_enabled
    if not db_enabled():
        return _result([], 0, page, page_size)
    from app.modules.graduation.services import graduation_taskbook_service as svc

    page, page_size = _page(page, page_size)
    batch_id = _batch_id(user)
    tenant_id = _tid()
    with session() as db:
        scope_select = student_scope_select(db, tenant_id, batch_id=batch_id)
        join_on = GraduationStudent.id == GraduationTaskBook.gd_student_id
        filters = [
            GraduationTaskBook.tenant_id == tenant_id,
            GraduationTaskBook.is_deleted.is_(False),
            GraduationStudent.tenant_id == tenant_id,
            GraduationStudent.batch_id == batch_id,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope_select),
        ]
        total = int(db.scalar(
            select(func.count(func.distinct(GraduationTaskBook.id)))
            .select_from(GraduationTaskBook)
            .join(GraduationStudent, join_on)
            .where(*filters)
        ) or 0)
        rows = db.execute(
            select(GraduationTaskBook, GraduationStudent)
            .join(GraduationStudent, join_on)
            .where(*filters)
            .order_by(GraduationTaskBook.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return _result([svc._row(row, student) for row, student in rows], total, page, page_size)


def midterms_page(user: dict, page=1, page_size=20) -> dict:
    from app.db.session import db_enabled
    if not db_enabled():
        return _result([], 0, page, page_size)
    from app.modules.graduation.services import graduation_midterm_service as svc

    page, page_size = _page(page, page_size)
    batch_id = _batch_id(user)
    tenant_id = _tid()
    with session() as db:
        scope_select = student_scope_select(db, tenant_id, batch_id=batch_id)
        join_on = GraduationStudent.id == GraduationMidterm.gd_student_id
        filters = [
            GraduationMidterm.tenant_id == tenant_id,
            GraduationMidterm.is_deleted.is_(False),
            GraduationMidterm.status.in_(_ACTIONABLE_MIDTERM_STATUSES),
            GraduationStudent.tenant_id == tenant_id,
            GraduationStudent.batch_id == batch_id,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope_select),
        ]
        total = int(db.scalar(
            select(func.count(func.distinct(GraduationMidterm.id)))
            .select_from(GraduationMidterm)
            .join(GraduationStudent, join_on)
            .where(*filters)
        ) or 0)
        rows = db.execute(
            select(GraduationMidterm, GraduationStudent)
            .join(GraduationStudent, join_on)
            .where(*filters)
            .order_by(GraduationMidterm.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return _result([svc._row(row, student) for row, student in rows], total, page, page_size)


def grades_page(user: dict, page=1, page_size=20) -> dict:
    from app.db.session import db_enabled
    if not db_enabled():
        return _result([], 0, page, page_size)
    from app.modules.graduation.services import graduation_grade_read_service as svc

    page, page_size = _page(page, page_size)
    rows, total = svc.list_grades(
        page,
        page_size,
        status="CALCULATED",
        batch_id=_batch_id(user),
    )
    return _result(rows, total, page, page_size)


# 历史 mobile 聚合 Router 排在 V9.2 context Router 之后；保留这些只读兼容函数，
# 但绝不再 collect-all。正式分页入口使用上面的 *_page 函数。
def taskbooks(user: dict) -> list:
    return taskbooks_page(user, 1, 100)["items"]


def midterms(user: dict) -> list:
    return midterms_page(user, 1, 100)["items"]


def grades(user: dict) -> list:
    return grades_page(user, 1, 100)["items"]
