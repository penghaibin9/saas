"""D6 选课读侧生产收口。

AaSelectionRecord / Selection Final / TeachingRoster 仍是唯一事实与写链。本模块只做：
1. 列表/名单 SQL 分页与学生可选课程批量加载；
2. COLLEGE 范围沿用教学任务的行政班/学院归属做 SQL 侧 fail-closed 收敛；
3. 统计、补选、冲突、归档聚合只消费本范围课程，禁止“批次可见后整批泄漏”。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.affairs_security import no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException

from . import academic_affairs_selection_core_service as _core


def _scope_values(db, ctx):
    """返回学院范围的 (allowed_class_ids, college_ids)；未配置必须 fail-closed。"""
    if str(getattr(ctx, "scope_type", "") or "").upper() != "COLLEGE":
        return None
    class_ids = {int(value) for value in (ctx.allowed_class_ids(db) or set())}
    college_ids = {int(value) for value in (getattr(ctx, "college_ids", set()) or set())}
    if not class_ids and not college_ids:
        raise no_data_scope("当前学院身份未配置教学班学院或班级范围")
    return class_ids, college_ids


def _scope_course_query(query, scoped):
    """把现有教学任务归属关系压到 SQL；scoped=None 表示保持既有全校/教师语义。"""
    if scoped is None:
        return query

    from app.models import AaSelectionCourse, AaTeachingTask, AaTeachingTaskBatch

    class_ids, college_ids = scoped
    predicates = []
    if class_ids:
        predicates.append(AaTeachingTask.class_id.in_(sorted(class_ids)))
    if college_ids:
        predicates.append(AaTeachingTaskBatch.college_id.in_(sorted(college_ids)))
    return (
        query.join(AaTeachingTask, AaTeachingTask.id == AaSelectionCourse.teaching_task_id)
        .join(AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id)
        .filter(
            AaTeachingTask.tenant_id == _core._tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTaskBatch.tenant_id == _core._tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
            or_(*predicates),
        )
    )


def _course_query(db, batch_id: int, scoped, *, status=None):
    from app.models import AaSelectionCourse

    query = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.batch_id == int(batch_id),
        AaSelectionCourse.tenant_id == _core._tid(),
        AaSelectionCourse.is_deleted.is_(False),
    )
    if status:
        query = query.filter(AaSelectionCourse.status == status)
    return _scope_course_query(query, scoped)


def _require_batch_visible(db, batch_id: int, scoped) -> None:
    if scoped is None:
        return
    if int(_course_query(db, batch_id, scoped).with_entities(func.count()).scalar() or 0) <= 0:
        raise no_data_scope("该选课批次不在当前学院数据范围内")


def _require_course_visible(db, course_id: int, scoped):
    from app.models import AaSelectionCourse

    query = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.id == int(course_id),
        AaSelectionCourse.tenant_id == _core._tid(),
        AaSelectionCourse.is_deleted.is_(False),
    )
    query = _scope_course_query(query, scoped)
    row = query.first()
    if not row:
        raise no_data_scope("该选课课程不在当前数据范围内")
    return row


def list_batches(user, status=None, term_id=None, page=1, page_size=20):
    from app.models import AaSelectionBatch, AaSelectionCourse

    safe_page = max(1, int(page or 1))
    safe_size = max(1, int(page_size or 20))
    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        query = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaSelectionBatch.status == status)
        if term_id:
            query = query.filter(AaSelectionBatch.term_id == int(term_id))
        if scoped is not None:
            batch_scope = db.query(AaSelectionCourse.batch_id).filter(
                AaSelectionCourse.tenant_id == _core._tid(),
                AaSelectionCourse.is_deleted.is_(False),
            )
            batch_scope = _scope_course_query(batch_scope, scoped).distinct().subquery()
            query = query.filter(AaSelectionBatch.id.in_(select(batch_scope.c.batch_id)))
        total = int(query.count() or 0)
        rows = (
            query.order_by(AaSelectionBatch.id.desc())
            .offset((safe_page - 1) * safe_size)
            .limit(safe_size)
            .all()
        )
        return [_core._batch_dto(row) for row in rows], total


def get_batch(user, batch_id):
    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        batch = _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch.id), scoped)
        return _core._batch_dto(batch)


def list_courses(user, batch_id, page=1, page_size=50):
    from app.models import AaSelectionCourse

    safe_page = max(1, int(page or 1))
    safe_size = max(1, int(page_size or 50))
    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch_id), scoped)
        query = _course_query(db, int(batch_id), scoped)
        total = int(query.count() or 0)
        rows = (
            query.order_by(AaSelectionCourse.id)
            .offset((safe_page - 1) * safe_size)
            .limit(safe_size)
            .all()
        )
        return [_core._course_dto(row) for row in rows], total


def course_roster(user, course_id, page=1, page_size=50):
    from app.models import AaSelectionRecord

    safe_page = max(1, int(page or 1))
    safe_size = max(1, int(page_size or 50))
    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        if scoped is not None:
            course = _require_course_visible(db, int(course_id), scoped)
        else:
            course = _core._get_course(db, int(course_id))
            if ctx.scope_type not in ("COLLEGE", "TENANT_ALL"):
                keys = _core._derive_keys(user)
                if not course.teacher_key or course.teacher_key not in keys:
                    raise _core.no_data_scope("非本人授课教学班，无权查看名单")
        query = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == int(course.id),
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.status.in_([_core._REC_SELECTED, _core._REC_LOCKED]),
            AaSelectionRecord.is_deleted.is_(False),
        )
        total = int(query.count() or 0)
        rows = (
            query.order_by(AaSelectionRecord.student_no, AaSelectionRecord.id)
            .offset((safe_page - 1) * safe_size)
            .limit(safe_size)
            .all()
        )
        return [_core._record_dto(row) for row in rows], total


def student_courses(user, batch_id=None):
    """保持既有 OPEN 批次/OPEN 课程响应，只消除按批次逐条查询。"""
    from app.models import AaSelectionBatch, AaSelectionCourse

    with _core.session() as db:
        query = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.status == _core._BATCH_OPEN,
            AaSelectionBatch.is_deleted.is_(False),
        )
        if batch_id:
            query = query.filter(AaSelectionBatch.id == int(batch_id))
        batches = query.all()
        if not batches:
            return []
        batch_ids = [int(batch.id) for batch in batches]
        course_rows = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id.in_(batch_ids),
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.status == _core._COURSE_OPEN,
            AaSelectionCourse.is_deleted.is_(False),
        ).order_by(AaSelectionCourse.batch_id, AaSelectionCourse.id).all()
        by_batch = defaultdict(list)
        for course in course_rows:
            by_batch[int(course.batch_id)].append(_core._course_dto(course))
        return [
            {"batch": _core._batch_dto(batch), "courses": by_batch.get(int(batch.id), [])}
            for batch in batches
        ]


def reselect_guide(user, batch_id):
    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        batch = _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch.id), scoped)
        if batch.status != _core._BATCH_CLOSED:
            raise _core._invalid("仅 CLOSED 批次有补选指引")
        courses = _course_query(db, int(batch.id), scoped).all()
        cancelled = [_core._course_dto(row) for row in courses if row.status == _core._COURSE_CANCELLED]
        available = [
            _core._course_dto(row) for row in courses
            if row.status == _core._COURSE_OPEN and int(row.selected_count or 0) < int(row.capacity or 0)
        ]
        return {"batchId": str(batch.id), "cancelledCourses": cancelled, "availableCourses": available}


def batch_stats(user, batch_id):
    from app.models import AaSelectionRecord

    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        batch = _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch.id), scoped)
        courses = _course_query(db, int(batch.id), scoped).all()
        course_ids = [int(row.id) for row in courses]
        total_cap = sum(int(row.capacity or 0) for row in courses)
        total_sel = sum(int(row.selected_count or 0) for row in courses)
        low = [
            row for row in courses
            if row.status == _core._COURSE_OPEN and int(row.selected_count or 0) < int(row.min_capacity or 0)
        ]
        full = [
            row for row in courses
            if int(row.capacity or 0) > 0 and int(row.selected_count or 0) >= int(row.capacity or 0)
        ]
        record_count = 0
        if course_ids:
            record_count = int(db.query(func.count(AaSelectionRecord.id)).filter(
                AaSelectionRecord.tenant_id == _core._tid(),
                AaSelectionRecord.selection_course_id.in_(course_ids),
                AaSelectionRecord.status.in_([_core._REC_SELECTED, _core._REC_LOCKED]),
                AaSelectionRecord.is_deleted.is_(False),
            ).scalar() or 0)
        return {
            "batchId": str(batch.id), "status": batch.status,
            "courseCount": len(courses), "totalCapacity": total_cap, "totalSelected": total_sel,
            "fillRate": round(total_sel / total_cap, 4) if total_cap else 0,
            "lowEnrollCount": len(low), "fullCount": len(full), "recordCount": record_count,
            "lowEnrollCourses": [_core._course_dto(row) for row in low],
        }


def get_conflict_report(user, batch_id, student_no=None):
    """冲突聚合只统计可见课程；按学号钻取同时写查询审计。"""
    from app.models import AaSelectionCourse, AffairsAuditTrail

    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        batch = _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch.id), scoped)
        course_rows = _course_query(db, int(batch.id), scoped).with_entities(
            AaSelectionCourse.id,
            AaSelectionCourse.course_name,
        ).all()
        course_ids = [int(cid) for cid, _name in course_rows]
        course_names = {int(cid): (name or "") for cid, name in course_rows}
        if not course_ids:
            return {"batchId": str(batch.id), "summary": [], "items": []}
        query = db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == _core._tid(),
            AffairsAuditTrail.biz_type == "AA_SELECTION_CONFLICT",
            AffairsAuditTrail.action == "SELECTION_CONFLICT_REJECT",
            AffairsAuditTrail.biz_id.in_(course_ids),
        )
        if student_no:
            query = query.filter(AffairsAuditTrail.detail.like(f"%studentNo={student_no} %"))
        rows = query.order_by(AffairsAuditTrail.occurred_at.desc()).all()
        counts = defaultdict(int)
        items = []
        for row in rows:
            cid = int(row.biz_id)
            counts[cid] += 1
            items.append({
                "occurredAt": _core._iso(row.occurred_at),
                "courseName": course_names.get(cid, ""),
                "detail": row.detail,
            })
        summary_counts = defaultdict(int)
        for cid, count in counts.items():
            summary_counts[course_names.get(cid) or str(cid)] += count
        summary = [
            {"courseName": name, "conflictRejectCount": count}
            for name, count in sorted(summary_counts.items(), key=lambda item: -item[1])
        ]
        if student_no:
            _core._audit(
                db, int(batch.id), "SELECTION_CONFLICT_QUERY",
                f"按学号查询冲突详情 studentNo={str(student_no)[:50]}",
            )
            db.commit()
        return {"batchId": str(batch.id), "summary": summary, "items": items}


def export_conflict_report_xlsx(user, batch_id, purpose="") -> bytes:
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx

    report = get_conflict_report(user, batch_id, None)
    current = get_current_user_ctx() or {}
    watermark = (
        f"导出人：{current.get('realName') or current.get('loginName') or '-'}  "
        f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}"
    )
    content = build_ledger_xlsx(
        "选课冲突预警报表",
        ["课程", "冲突拒选次数"],
        [[row["courseName"], row["conflictRejectCount"]] for row in report["summary"]],
        watermark=watermark,
    )
    with _core.session() as db:
        _core._audit(db, int(batch_id), "SELECTION_CONFLICT_EXPORT", f"冲突报表导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content


def list_archived_batches(user, term_id=None, page=1, page_size=20):
    return list_batches(user, _core._BATCH_ARCHIVED, term_id, page, page_size)


def archive_detail(user, batch_id):
    batch = get_batch(user, batch_id)
    if batch["status"] != _core._BATCH_ARCHIVED:
        raise _core._invalid("仅已归档批次可查看归档详情")
    return {**batch, "stats": batch_stats(user, batch_id)}


def export_archive_xlsx(user, batch_id, purpose="") -> bytes:
    from app.models import AaSelectionCourse

    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx

    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        batch = _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch.id), scoped)
        if batch.status != _core._BATCH_ARCHIVED:
            raise _core._invalid("仅已归档批次可导出归档台账")
        courses = _course_query(db, int(batch.id), scoped).order_by(AaSelectionCourse.id).all()
        batch_name = batch.batch_name
    current = get_current_user_ctx() or {}
    watermark = (
        f"导出人：{current.get('realName') or current.get('loginName') or '-'}  "
        f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}"
    )
    rows = [[
        row.course_name, row.teacher_name or "", row.capacity, row.min_capacity,
        row.selected_count, row.status,
    ] for row in courses]
    content = build_ledger_xlsx(
        f"选课归档台账 · {batch_name}",
        ["课程", "教师", "容量", "开课下限", "已选", "状态"],
        rows,
        watermark=watermark,
    )
    with _core.session() as db:
        _core._audit(db, int(batch_id), "SELECTION_ARCHIVE_EXPORT", f"归档台账导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content


def list_rounds(user, batch_id):
    """轮次只读也必须先通过所属批次对象范围。写侧仍由 SelectionRound Final 自己管。"""
    from . import academic_affairs_selection_round_service as legacy_round

    with _core.session() as db:
        ctx = _core._ctx(user, db)
        scoped = _scope_values(db, ctx)
        _core._get_batch(db, int(batch_id))
        _require_batch_visible(db, int(batch_id), scoped)
    return legacy_round.list_rounds(user, int(batch_id))
