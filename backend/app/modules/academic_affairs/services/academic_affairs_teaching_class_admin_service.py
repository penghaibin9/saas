"""教学班存量回填管理 Service。

正式回填单事务全有或全无：先完成当前范围内全部教学任务名单对账，任何未就绪项都零写入；
已有正式版本成员一致则幂等跳过，成员不一致则阻断，绝不覆盖人工或选课版本。
"""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_task_service as task_service
from . import academic_affairs_teaching_class_service as teaching_class_service


def _scoped_tasks(db, user, term_id: int):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    scope = task_service._scope(user, db)
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

    allowed = []
    for row in tasks:
        batch = batch_by_id.get(int(row.batch_id))
        in_college = bool(
            scope.college_ids and batch and batch.college_id
            and int(batch.college_id) in scope.college_ids
        )
        in_class = bool(
            scope.class_ids and row.class_id and int(row.class_id) in scope.class_ids
        )
        if in_college or in_class:
            allowed.append(row)
    return allowed


def _preview_rows(db, tasks):
    from app.models import AaTeachingClass

    report = []
    for task in tasks:
        legacy = teaching_class_service._legacy_resolve_roster(db, int(task.id))
        legacy_ids = sorted({int(value) for value in (legacy.get("studentIds") or [])})
        teaching_class = db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.teaching_task_id == int(task.id),
            AaTeachingClass.is_deleted.is_(False),
        ).first()
        current = (
            teaching_class_service._new_roster_dto(db, teaching_class)
            if teaching_class and teaching_class.current_roster_version_id else None
        )
        authoritative = (
            teaching_class_service.resolve_teaching_task_roster(db, int(task.id))
            if teaching_class and teaching_class.current_roster_version_id else None
        )

        existing_projected = bool(current and current.get("ready"))
        projection_match = None
        blocked_reason = ""
        if teaching_class and teaching_class.current_roster_version_id:
            if not current or not current.get("ready"):
                blocked_reason = "已有教学班当前名单版本无效，禁止回填覆盖"
            elif not authoritative or not authoritative.get("ready") or not authoritative.get("rosterVersionId"):
                blocked_reason = authoritative.get("note") if authoritative else "已有名单版本不是当前权威事实"
            elif legacy.get("ready") and set(legacy_ids) != set(current.get("studentIds") or []):
                projection_match = False
                blocked_reason = "已有正式名单与兼容事实源成员不一致，必须人工核对，禁止自动覆盖"
            else:
                projection_match = True if legacy.get("ready") else None
        elif not legacy.get("ready") or not legacy_ids:
            blocked_reason = legacy.get("note") or "兼容名单尚未就绪"

        ready_for_backfill = bool(
            not blocked_reason
            and (existing_projected or (legacy.get("ready") and legacy_ids))
        )
        report.append({
            "teachingTaskId": str(task.id),
            "courseName": task.course_name or "",
            "className": task.teaching_class_name or str(getattr(task, "class_name", None) or ""),
            "legacyReady": bool(legacy.get("ready")),
            "legacySource": legacy.get("source") or "",
            "legacyMemberCount": len(legacy_ids),
            "note": blocked_reason or legacy.get("note") or "",
            "readyForBackfill": ready_for_backfill,
            "existingProjected": existing_projected,
            "existingVersionNo": int(teaching_class.current_roster_version_no or 0) if teaching_class else 0,
            "projectionMatch": projection_match,
            "studentIds": legacy_ids,
            "batchIds": [str(value) for value in (legacy.get("batchIds") or [])],
        })
    return report


def _public_report(term_id: int, dry_run: bool, rows):
    private_keys = {"studentIds", "batchIds"}
    items = [{key: value for key, value in row.items() if key not in private_keys} for row in rows]
    ready_count = sum(1 for row in items if row["readyForBackfill"])
    existing_count = sum(1 for row in items if row["existingProjected"] and row["readyForBackfill"])
    return {
        "termId": str(term_id), "dryRun": bool(dry_run),
        "taskCount": len(items), "readyCount": ready_count,
        "blockedCount": len(items) - ready_count,
        "alreadyProjectedCount": existing_count,
        "toCreateCount": ready_count - existing_count,
        "items": items,
    }


def backfill_teaching_classes(user, term_id: int, dry_run=True, reason=""):
    reason_text = str(reason or "").strip()
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
        if not tasks:
            db.rollback()
            raise AppException("DATA_CONFLICT", "当前学期和数据范围没有可回填的教学任务", http_status=409)
        blocked = [row for row in report_rows if not row["readyForBackfill"]]
        if blocked:
            db.rollback()
            raise AppException(
                "DATA_CONFLICT",
                f"仍有 {len(blocked)} 条教学任务名单未就绪或与现有版本冲突，已取消本次回填，未写入任何数据",
                details=_public_report(int(term_id), True, report_rows),
                http_status=409,
            )

        created_count = 0
        skipped_count = 0
        for task, row in zip(tasks, report_rows):
            if row["existingProjected"]:
                skipped_count += 1
                continue
            teaching_class = teaching_class_service.ensure_teaching_class_for_task(
                db, int(task.id), initialize_admin_roster=False,
            )
            source_type = "SELECTION_LOCK" if row["legacySource"] == "SELECTION_LOCKED" else "ADMIN_CLASS"
            source_id = int(row["batchIds"][0]) if row["batchIds"] else task.class_id
            teaching_class_service.create_roster_version(
                db, teaching_class, row["studentIds"],
                source_type=source_type, source_id=source_id,
                reason=f"V2-02存量回填：{reason_text}",
            )
            created_count += 1

        context = get_current_user_ctx() or {}
        db.add(AffairsAuditTrail(
            tenant_id=_tid(), biz_type="AA_TEACHING_CLASS",
            biz_id=int(term_id), action="TEACHING_CLASS_BACKFILL",
            operator=str(context.get("userId") or context.get("loginName") or ""),
            role_name=str(context.get("currentRoleCode") or ""),
            detail=(
                f"termId={term_id};taskCount={result['taskCount']};created={created_count};"
                f"skipped={skipped_count};reason={reason_text}"
            )[:990],
        ))
        db.commit()
        result.update({
            "dryRun": False, "createdCount": created_count,
            "skippedCount": skipped_count, "reason": reason_text, "audited": True,
        })
        return result
