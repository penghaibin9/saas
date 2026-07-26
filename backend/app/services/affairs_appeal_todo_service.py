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
from types import SimpleNamespace
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


def _preflight(todo_type: str, student_id: int) -> None:
    if int(student_id or 0) <= 0:
        raise AppException("VALIDATION_ERROR", "无法识别异议/申诉学生")
    with session() as db:
        _assignee(db, _SPECS[todo_type], int(student_id))


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


def install() -> None:
    from app.services import affairs_activity_service as activity
    from app.services import affairs_aid_service as aid
    from app.services import affairs_discipline_service as discipline
    from app.services import affairs_funding_service as funding

    originals = {
        "aid_submit": aid.submit_objection,
        "aid_review": aid.review_objection,
        "funding_submit": funding.submit_appeal,
        "funding_review": funding.review_appeal,
        "discipline_submit": discipline.submit_appeal,
        "discipline_review": discipline.review_appeal,
        "credit_submit": activity.submit_credit_appeal,
        "credit_review": activity.review_credit_appeal,
    }

    def aid_submit(apply_id, body, user, **kwargs):
        from app.models import AidApply
        with session() as db:
            parent = db.get(AidApply, int(apply_id))
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                raise AppException("DATA_NOT_FOUND", "认定申请不存在")
            _preflight("AID_OBJECTION_REVIEW", int(parent.student_id))
        result = originals["aid_submit"](apply_id, body, user, **kwargs)
        row_id = _row_id(result, "objectionId", "id")
        return _with_status(result, "todoSyncStatus", bool(row_id) and _sync_todo_after_commit(
            "AID_OBJECTION_REVIEW", row_id,
        ))

    def aid_review(objection_id, body, user):
        result = originals["aid_review"](objection_id, body, user)
        return _with_status(
            result, "notificationSyncStatus",
            _result_notice("AID_OBJECTION_REVIEW", int(objection_id)),
        )

    def funding_submit(app_id, body, user, **kwargs):
        from app.models import FundingApplication
        with session() as db:
            parent = db.get(FundingApplication, int(app_id))
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                raise AppException("DATA_NOT_FOUND", "资助申请不存在")
            _preflight("FUNDING_APPEAL_REVIEW", int(parent.student_id))
        result = originals["funding_submit"](app_id, body, user, **kwargs)
        row_id = _row_id(result, "appealId", "id")
        return _with_status(result, "todoSyncStatus", bool(row_id) and _sync_todo_after_commit(
            "FUNDING_APPEAL_REVIEW", row_id,
        ))

    def funding_review(appeal_id, body, user):
        result = originals["funding_review"](appeal_id, body, user)
        return _with_status(
            result, "notificationSyncStatus",
            _result_notice("FUNDING_APPEAL_REVIEW", int(appeal_id)),
        )

    def discipline_submit(case_id, body, user, **kwargs):
        from app.models import DisciplineCase
        with session() as db:
            parent = db.get(DisciplineCase, int(case_id))
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                raise AppException("DATA_NOT_FOUND", "处分记录不存在")
            _preflight("DISCIPLINE_APPEAL_REVIEW", int(parent.student_id))
        result = originals["discipline_submit"](case_id, body, user, **kwargs)
        row_id = _row_id(result, "appealId", "id")
        return _with_status(result, "todoSyncStatus", bool(row_id) and _sync_todo_after_commit(
            "DISCIPLINE_APPEAL_REVIEW", row_id,
        ))

    def discipline_review(appeal_id, body, user):
        result = originals["discipline_review"](appeal_id, body, user)
        return _with_status(
            result, "notificationSyncStatus",
            _result_notice("DISCIPLINE_APPEAL_REVIEW", int(appeal_id)),
        )

    def credit_submit(body, user):
        student_id = int(getattr(body, "studentId", 0) or 0)
        _preflight("SECOND_CLASS_APPEAL_REVIEW", student_id)
        result = originals["credit_submit"](body, user)
        row_id = _row_id(result, "appealId", "id")
        return _with_status(result, "todoSyncStatus", bool(row_id) and _sync_todo_after_commit(
            "SECOND_CLASS_APPEAL_REVIEW", row_id,
        ))

    def credit_review(appeal_id, body, user):
        result = originals["credit_review"](appeal_id, body, user)
        return _with_status(
            result, "notificationSyncStatus",
            _result_notice("SECOND_CLASS_APPEAL_REVIEW", int(appeal_id)),
        )

    aid.submit_objection = aid_submit
    aid.review_objection = aid_review
    funding.submit_appeal = funding_submit
    funding.review_appeal = funding_review
    discipline.submit_appeal = discipline_submit
    discipline.review_appeal = discipline_review
    activity.submit_credit_appeal = credit_submit
    activity.review_credit_appeal = credit_review
