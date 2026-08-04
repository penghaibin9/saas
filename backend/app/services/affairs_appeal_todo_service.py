"""学工异议/申诉统一待办与结果通知。

覆盖困难异议、资助申诉、处分申诉、第二课堂积分申诉。

设计约束：
- 提交前解析具体受理人，禁止生成 assignee_id=0 的死待办；
- 业务提交/复核由既有领域服务完成，补充待办与结果消息不得反向伪装业务失败；
- 教师读取工作台时绝不扫描并写库，GET 保持只读；
- 补充同步失败必须留下审计证据，并在响应中标记 DEGRADED，便于运维补偿。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

log = logging.getLogger(__name__)

_SPECS = {
    "AID_OBJECTION_REVIEW": {
        "model": "AidObjection", "id_field": "id", "student_field": "student_id",
        "status_field": "status", "pending": {"SUBMITTED"}, "node": "SCHOOL_REVIEW",
        "biz_type": "AID_OBJECTION", "title": "困难认定异议待复核",
    },
    "FUNDING_APPEAL_REVIEW": {
        "model": "FundingAppeal", "id_field": "id", "student_field": "student_id",
        "status_field": "status", "pending": {"SUBMITTED"}, "node": "SCHOOL_REVIEW",
        "biz_type": "FUNDING_APPEAL", "title": "资助公示申诉待复核",
    },
    "DISCIPLINE_APPEAL_REVIEW": {
        "model": "DisciplineAppeal", "id_field": "id", "student_field": "student_id",
        "status_field": "status", "pending": {"SUBMITTED", "REVIEWING"}, "node": "SA_OFFICE_REVIEW",
        "biz_type": "DISCIPLINE_APPEAL", "title": "处分申诉待复核",
    },
    "SECOND_CLASS_APPEAL_REVIEW": {
        "model": "AffairsCreditAppeal", "id_field": "id", "student_field": "student_id",
        "status_field": "status", "pending": {"SUBMITTED"}, "node": "STUDENT_AFFAIRS_REVIEW",
        "biz_type": "SECOND_CLASS_APPEAL", "title": "第二课堂积分申诉待审核",
    },
}

_LABELS = {key: spec["title"] for key, spec in _SPECS.items()}


def _model(name: str):
    from app import models
    return getattr(models, name)


def _assignee(db, spec: dict, student_id: int) -> int:
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, spec["node"], student_id=student_id)


def _record_sync_failure(todo_type: str, row_id: int | None, stage: str, exc: Exception) -> None:
    """补偿链失败只记录，不把已经成功的业务事务伪装成失败。"""
    log.exception(
        "student-affairs appeal sync failed: type=%s row=%s stage=%s",
        todo_type, row_id, stage,
    )
    try:
        from app.services import audit_log
        audit_log.record(
            "AFFAIRS_APPEAL_SYNC_FAILED",
            f"{todo_type}:{row_id or 0}",
            detail={
                "todoType": todo_type,
                "rowId": str(row_id or ""),
                "stage": stage,
                "errorType": type(exc).__name__,
            },
            result="FAILED",
        )
    except Exception:  # noqa: BLE001 - 最后兜底不得覆盖原业务结果
        log.exception("failed to persist appeal sync failure audit")
    if row_id:
        try:
            from app.services.affairs_appeal_repair_service import enqueue
            enqueue(todo_type, int(row_id), stage, exc)
        except Exception:  # noqa: BLE001 - 入队失败仍不得覆盖原业务结果
            log.exception("failed to enqueue appeal repair")


def _ensure_todo(db, todo_type: str, row) -> None:
    from app.models import UnifiedTodo

    spec = _SPECS[todo_type]
    row_id = int(getattr(row, spec["id_field"]))
    student_id = int(getattr(row, spec["student_field"]))
    status = str(getattr(row, spec["status_field"]) or "")

    existing = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type == spec["biz_type"],
        UnifiedTodo.source_biz_id == row_id,
        UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.is_deleted.is_(False),
    ).with_for_update()).first()

    if status in spec["pending"]:
        assignee_id = _assignee(db, spec, student_id)
        if existing:
            changed = (
                int(existing.assignee_id or 0) != int(assignee_id)
                or int(existing.student_id or 0) != int(student_id)
                or existing.title != spec["title"]
                or existing.status != "PENDING"
            )
            existing.assignee_id = int(assignee_id)
            existing.student_id = student_id
            existing.title = spec["title"]
            existing.status = "PENDING"
            if changed:
                existing.version = int(existing.version or 0) + 1
        else:
            db.add(UnifiedTodo(
                tenant_id=_tid(), source_module="student-affairs",
                source_biz_type=spec["biz_type"], source_biz_id=row_id,
                todo_type=todo_type, assignee_id=int(assignee_id),
                student_id=student_id, title=spec["title"], status="PENDING",
            ))
    elif existing and existing.status != "DONE":
        existing.status = "DONE"
        existing.version = int(existing.version or 0) + 1


def _sync_todo_after_commit(todo_type: str, row_id: int) -> bool:
    """幂等补齐单条待办。失败时返回 False，绝不抛回已完成的业务请求。"""
    spec = _SPECS[todo_type]
    model = _model(spec["model"])
    try:
        with session() as db:
            row = db.scalars(select(model).where(
                model.tenant_id == _tid(),
                model.id == int(row_id),
                model.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row:
                raise AppException("DATA_NOT_FOUND", "异议/申诉记录不存在")
            _ensure_todo(db, todo_type, row)
            db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        _record_sync_failure(todo_type, row_id, "TODO_SYNC", exc)
        return False


def _result_notice(todo_type: str, row_id: int) -> bool:
    """关闭待办并写入学生结果消息；失败不反向覆盖复核成功结果。"""
    from app.services.message_event_outbox_service import emit_receiver_notice, try_process_pending_outbox

    spec = _SPECS[todo_type]
    model = _model(spec["model"])
    try:
        with session() as db:
            row = db.scalars(select(model).where(
                model.tenant_id == _tid(),
                model.id == int(row_id),
                model.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row:
                raise AppException("DATA_NOT_FOUND", "异议/申诉记录不存在")
            _ensure_todo(db, todo_type, row)
            status = str(getattr(row, spec["status_field"]) or "")
            result = str(getattr(row, "result", None) or status)
            opinion = str(getattr(row, "review_opinion", None) or "")
            if status not in spec["pending"]:
                emit_receiver_notice(
                    db,
                    event_code=f"{spec['biz_type']}.RESULT",
                    source_module="student-affairs",
                    source_biz_type=spec["biz_type"].lower(),
                    source_biz_id=int(row_id),
                    receiver_id=int(getattr(row, spec["student_field"])),
                    title=f"{spec['title'].replace('待复核', '').replace('待审核', '')}结果",
                    content=f"复核结论：{result}" + (f"；意见：{opinion}" if opinion else ""),
                    receiver_as="student",
                    dedup_extra=f"result:{status}:{result}",
                )
            db.commit()
        try:
            try_process_pending_outbox(worker_id="affairs-appeal-inline")
        except Exception as exc:  # noqa: BLE001
            _record_sync_failure(todo_type, row_id, "OUTBOX_DRAIN", exc)
        return True
    except Exception as exc:  # noqa: BLE001
        _record_sync_failure(todo_type, row_id, "RESULT_NOTICE", exc)
        return False


def _row_id(result: Any, *keys: str) -> int:
    if not isinstance(result, dict):
        return 0
    for key in keys:
        value = result.get(key)
        if str(value or "").isdigit():
            return int(value)
    return 0


def _with_status(result: Any, key: str, ok: bool):
    if isinstance(result, dict):
        result[key] = "OK" if ok else "DEGRADED"
    return result


def require_submission_assignee(db, todo_type: str, student_id: int) -> int:
    """提交事务内显式验证受理人，禁止依赖启动期函数替换。"""
    if todo_type not in _SPECS:
        raise AppException("VALIDATION_ERROR", "未知学工申诉待办类型")
    if int(student_id or 0) <= 0:
        raise AppException("VALIDATION_ERROR", "无法识别异议/申诉学生")
    return _assignee(db, _SPECS[todo_type], int(student_id))


def sync_after_submit(todo_type: str, result: Any, *id_keys: str):
    """业务提交成功后同步待办；失败进入租约补偿队列并返回 DEGRADED。"""
    row_id = _row_id(result, *(id_keys or ("id",)))
    return _with_status(
        result, "todoSyncStatus",
        bool(row_id) and _sync_todo_after_commit(todo_type, row_id),
    )


def sync_after_review(todo_type: str, row_id: int, result: Any):
    """业务复核成功后关闭待办并通知学生；失败可恢复且不回滚业务结论。"""
    return _with_status(
        result, "notificationSyncStatus",
        _result_notice(todo_type, int(row_id)),
    )


def install() -> None:
    """兼容空入口；各领域服务已显式调用本模块，不再替换函数对象。"""
    return None
