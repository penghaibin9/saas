"""V2-02 教学班管理写动作最终层。

正式回填采用单事务全有或全无：先完成当前数据范围内全部教学任务名单对账，存在任何未就绪项时
零写入；全部通过后才投影教学班、创建名单版本并写审计。dry-run 始终只读。
"""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_teaching_class_query_service as _base
from . import academic_affairs_teaching_class_lock_service as _teaching_class
from .academic_affairs_task_security_facade import _scope


def __getattr__(name):
    return getattr(_base, name)


def _scoped_tasks(db, user, term_id: int):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    scope = _scope(user, db)
    batches = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term_id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).all()
    batch_ids = [int(row.id) for row in batches]
    batch_by_id = {int(row.id): row for row in batches}
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(batch_ids or [0]),
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id).all()
    if scope.all:
        return tasks
    if scope.class_ids:
        return [row for row in tasks if row.class_id and int(row.class_id) in scope.class_ids]
    if scope.college_ids:
        return [
            row for row in tasks
            if batch_by_id.get(int(row.batch_id))
            and batch_by_id[int(row.batch_id)].college_id
            and int(batch_by_id[int(row.batch_id)].college_id) in scope.college_ids
        ]
    return []


def _preview_rows(db, tasks):
    report = []
    for task in tasks:
        legacy = _teaching_class._legacy_resolve_roster(db, int(task.id))
        report.append({
            "teachingTaskId": str(task.id),
            "courseName": task.course_name or "",
            "className": task.teaching_class_name or task.class_name or "",
            "legacyReady": bool(legacy.get("ready")),
            "legacySource": legacy.get("source") or "",
            "legacyMemberCount": len(legacy.get("studentIds") or []),
            "note": legacy.get("note") or "",
            "studentIds": [int(value) for value in (legacy.get("studentIds") or [])],
            "batchIds": [str(value) for value in (legacy.get("batchIds") or [])],
        })
    return report


def _public_report(term_id: int, dry_run: bool, rows):
    items = [{key: value for key, value in row.items() if key not in {"studentIds", "batchIds"}} for row in rows]
    return {
        "termId": str(term_id),
        "dryRun": bool(dry_run),
        "taskCount": len(items),
        "readyCount": sum(1 for row in items if row["legacyReady"]),
        "blockedCount": sum(1 for row in items if not row["legacyReady"]),
        "items": items,
    }


def backfill_teaching_classes(user, term_id: int, dry_run=True, reason=""):
    reason_text = (reason or "").strip()
    if not dry_run and len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "执行教学班回填必须填写不少于5字的原因")

    from app.models import AffairsAuditTrail

    with session() as db:
        tasks = _scoped_tasks(db, user, int(term_id))
        report_rows = _preview_rows(db, tasks)
        result = _public_report(int(term_id), bool(dry_run), report_rows)
        if dry_run:
            db.rollback()
            return result

        blocked = [row for row in report_rows if not row["legacyReady"] or not row["studentIds"]]
        if blocked:
            db.rollback()
            raise AppException(
                "DATA_CONFLICT",
                f"仍有 {len(blocked)} 条教学任务名单未就绪，已取消本次回填，未写入任何教学班版本",
                details=_public_report(int(term_id), True, report_rows),
                http_status=409,
            )

        for task, row in zip(tasks, report_rows):
            teaching_class = _teaching_class.ensure_teaching_class_for_task(
                db, int(task.id), initialize_admin_roster=False,
            )
            source_type = "SELECTION_LOCK" if row["legacySource"] == "SELECTION_LOCKED" else "ADMIN_CLASS"
            source_id = int(row["batchIds"][0]) if row["batchIds"] else task.class_id
            _teaching_class.create_roster_version(
                db,
                teaching_class,
                row["studentIds"],
                source_type=source_type,
                source_id=source_id,
                reason=f"V2-02存量回填：{reason_text}",
            )

        ctx = get_current_user_ctx() or {}
        db.add(AffairsAuditTrail(
            tenant_id=_tid(),
            biz_type="AA_TEACHING_CLASS",
            biz_id=int(term_id),
            action="TEACHING_CLASS_BACKFILL",
            operator=str(ctx.get("userId") or ctx.get("loginName") or ""),
            role_name=str(ctx.get("currentRoleCode") or ""),
            detail=(
                f"termId={term_id};taskCount={result['taskCount']};"
                f"readyCount={result['readyCount']};reason={reason_text}"
            )[:990],
        ))
        db.commit()
        result["dryRun"] = False
        result["reason"] = reason_text
        result["audited"] = True
        return result
