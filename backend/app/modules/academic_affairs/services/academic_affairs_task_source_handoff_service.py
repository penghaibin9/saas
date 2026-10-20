"""学校责任人员的原任务承接命令；所有校验、记录及必需审计原子提交。"""
from __future__ import annotations

import re
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.core.timeutil import utc_now_naive
from app.services.db_service import _tid, session

from .academic_affairs_program_formation_proof_service import _actor, _hash


def _conflict(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def _responsible(db, user):
    from .academic_affairs_program_governance_service import _scope
    from .academic_affairs_responsibility_service import resolve_school
    code = "academicAffairs.teachingTask.confirm"
    enforce_permission(user, code)
    if _scope(user, db).scope_type != "TENANT_ALL":
        raise AppException("PERMISSION_DENIED", "只有校教务责任人员可以确认教学任务来源承接", http_status=403)
    actor = _actor(db, user)
    if str(actor) not in resolve_school(db, permission_code=code)["assigneeUserIds"]:
        raise AppException("PERMISSION_DENIED", "当前账号不是有效的校级教学任务终审责任人员", http_status=403)
    return actor


def _receipt(row):
    return {"handoffId": str(row.id), "termId": str(row.term_id),
        "executionTaskId": str(row.execution_task_id), "successorTaskId": str(row.successor_task_id),
        "executionSourceId": str(row.execution_source_id), "successorSourceId": str(row.successor_source_id),
        "reason": row.reason, "confirmedAt": row.confirmed_at.replace(tzinfo=timezone.utc).isoformat(),
        "summary": "后继方案来源已由原教学任务承接；课表、任课和历史仍在原任务办理。"}


def _write_audit(db, row, user):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_TASK_SOURCE_HANDOFF", biz_id=row.id,
        action="CONFIRM_SOURCE_HANDOFF", operator=str(row.confirmed_by),
        role_name=str(user.get("currentRoleCode") or ""), occurred_at=row.confirmed_at,
        detail=f"原任务{row.execution_task_id}承接后继来源任务{row.successor_task_id}；{row.reason}"))
    db.flush()


def confirm_source_handoff(execution_task_id, body, user):
    """先锁共同父对象，再锁两任务；确认后不再产生后继业务执行。

    复用当前校级教学任务确认责任，原业务与历史保持在原任务。
    """
    from app.models import (AaProgram, AaProgramCourse, AaTeachingTask, AaTeachingTaskBatch,
        AaTeachingTaskSourceHandoff, AaTerm)
    from .academic_affairs_archive_service import guard_term_writable
    from .academic_affairs_task_service import _ensure_task_visible
    from .academic_affairs_task_source_review_service import get_source_review
    from .academic_affairs_task_execution_authority import require_independent_task

    original_id, successor_id = int(execution_task_id), int(body.successorTaskId)
    reason, idem = str(body.reason).strip(), str(body.idempotencyKey).strip()
    expected = str(body.expectedSourceFingerprint).lower()
    if original_id == successor_id or len(reason) < 4 or len(reason) > 500 or not 1 <= len(idem) <= 120:
        raise AppException("VALIDATION_ERROR", "请选择不同任务并填写完整承接说明和请求标识")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise AppException("VALIDATION_ERROR", "请先重新核对任务来源，再提交承接")
    payload_hash = _hash({"execution": str(original_id), "successor": str(successor_id),
        "reason": reason, "fingerprint": expected})
    try:
        with session() as db:
            # 首个读取前设置，等待任务锁后所有非锁定子对象查询读到已提交事实。
            db.connection(execution_options={"isolation_level": "READ COMMITTED"})
            actor = _responsible(db, user)
            original, _ = _ensure_task_visible(db, original_id, user)
            successor, _ = _ensure_task_visible(db, successor_id, user)
            batch_ids = sorted({original.batch_id, successor.batch_id})
            batches = db.scalars(select(AaTeachingTaskBatch).where(AaTeachingTaskBatch.tenant_id == _tid(),
                AaTeachingTaskBatch.id.in_(batch_ids), AaTeachingTaskBatch.is_deleted.is_(False))).all()
            if len(batches) != len(batch_ids):
                raise not_found("教学任务来源批次不存在")
            term_ids = {batch.term_id for batch in batches}
            if len(term_ids) != 1:
                raise _conflict("两条任务不属于同一学期，不能承接")
            term_id = next(iter(term_ids))
            term = db.scalar(select(AaTerm).where(AaTerm.tenant_id == _tid(), AaTerm.id == term_id,
                AaTerm.is_deleted.is_(False)).with_for_update().execution_options(populate_existing=True))
            if term is None:
                raise not_found("学期不存在")
            source_ids = sorted({pk for pk in (original.source_program_course_id, successor.source_program_course_id) if pk})
            sources = db.scalars(select(AaProgramCourse).where(AaProgramCourse.tenant_id == _tid(),
                AaProgramCourse.id.in_(source_ids), AaProgramCourse.is_deleted.is_(False))).all()
            program_ids = sorted({row.program_id for row in sources})
            db.scalars(select(AaProgram).where(AaProgram.tenant_id == _tid(), AaProgram.id.in_(program_ids),
                AaProgram.is_deleted.is_(False)).order_by(AaProgram.id).with_for_update()
                .execution_options(populate_existing=True)).all()
            sources = db.scalars(select(AaProgramCourse).where(AaProgramCourse.tenant_id == _tid(),
                AaProgramCourse.id.in_(source_ids), AaProgramCourse.is_deleted.is_(False))
                .order_by(AaProgramCourse.id).with_for_update().execution_options(populate_existing=True)).all()
            batches = db.scalars(select(AaTeachingTaskBatch).where(AaTeachingTaskBatch.tenant_id == _tid(),
                AaTeachingTaskBatch.id.in_(batch_ids), AaTeachingTaskBatch.is_deleted.is_(False))
                .order_by(AaTeachingTaskBatch.id).with_for_update().execution_options(populate_existing=True)).all()
            tasks = db.scalars(select(AaTeachingTask).where(AaTeachingTask.tenant_id == _tid(),
                AaTeachingTask.id.in_([original_id, successor_id]), AaTeachingTask.is_deleted.is_(False))
                .order_by(AaTeachingTask.id).with_for_update().execution_options(populate_existing=True)).all()
            if len(tasks) != 2 or len(batches) != len(batch_ids):
                raise _conflict("教学任务或批次已变化，请重新核对")
            current = {row.id: row for row in tasks}
            if (sorted({row.program_id for row in sources}) != program_ids
                or any(row.batch_id not in batch_ids for row in tasks)
                or any(batch.term_id != term_id for batch in batches)
                or sorted({pk for row in tasks if (pk := row.source_program_course_id)}) != source_ids):
                raise _conflict("教学任务来源或办理范围已变化，请重新核对")
            for pk in (original_id, successor_id):
                _ensure_task_visible(db, pk, user)
            previous = db.scalar(select(AaTeachingTaskSourceHandoff).where(
                AaTeachingTaskSourceHandoff.tenant_id == _tid(),
                AaTeachingTaskSourceHandoff.idempotency_key == idem))
            if previous:
                if previous.payload_hash != payload_hash:
                    raise _conflict("同一请求标识已用于其他承接内容，请回读原结果")
                return _receipt(previous)
            guard_term_writable(db, term_id)
            require_independent_task(db, current[original_id])
            require_independent_task(db, current[successor_id])
            if db.scalar(select(AaTeachingTaskSourceHandoff.id).where(
                AaTeachingTaskSourceHandoff.tenant_id == _tid(),
                AaTeachingTaskSourceHandoff.execution_task_id == successor_id).limit(1)) is not None:
                raise _conflict("后继任务已承担其他来源的教学执行，不能把已有执行链改为后继")
            review = get_source_review(original_id, successor_id, user, db=db)
            if review["status"] != "CHECKED":
                blockers = [row for row in review["checks"] if row["status"] != "PASS"]
                raise AppException("DATA_CONFLICT", "来源承接前置尚未满足：" + "；".join(row["message"] for row in blockers),
                    http_status=409, details={"confirmationBlockers": blockers})
            if review["executionTaskId"] != str(original_id) or review["successorTaskId"] != str(successor_id):
                raise _conflict("承接方向与明确方案版本关系不一致，请保留原任务执行")
            if review["sourceFingerprint"] != expected:
                raise _conflict("来源、任课、名单或任务版本已变化，请重新核对后确认")
            row = AaTeachingTaskSourceHandoff(tenant_id=_tid(), term_id=term_id,
                execution_task_id=original_id, successor_task_id=successor_id,
                execution_source_id=current[original_id].source_program_course_id,
                successor_source_id=current[successor_id].source_program_course_id,
                source_fingerprint=expected, reason=reason, confirmed_by=actor, confirmed_at=utc_now_naive(),
                idempotency_key=idem, payload_hash=payload_hash, created_by=actor)
            db.add(row); db.flush()
            _write_audit(db, row, user)
            # 回读实际落库时间精度；首个回执必须与幂等重放一致。
            db.refresh(row)
            db.commit()
            return _receipt(row)
    except IntegrityError as exc:
        raise _conflict("承接关系已由其他请求确认，请回读原任务结果") from exc
    except OperationalError as exc:
        if getattr(exc.orig, "args", (None,))[0] in (1205, 1213):
            raise _conflict("教学任务正在由其他责任人办理，请回读后再核对") from exc
        raise
