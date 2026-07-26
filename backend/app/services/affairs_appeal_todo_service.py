"""学工异议/申诉统一待办与结果通知。

覆盖困难异议、资助申诉、处分申诉、第二课堂积分申诉。提交前要求具体受理人，
提交后幂等创建 UnifiedTodo；教师移动学工卡每次读取时执行轻量对账，修复历史漏单。
复核后关闭待办，并向学生发送所有结论（成立/不成立/维持/变更/撤销/驳回）。
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

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


def _assignee(db, spec, student_id: int) -> int:
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, spec["node"], student_id=student_id)


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
    )).first()
    if status in spec["pending"]:
        assignee_id = _assignee(db, spec, student_id)
        if existing:
            existing.assignee_id = assignee_id
            existing.student_id = student_id
            existing.title = spec["title"]
            if existing.status != "PENDING":
                existing.status = "PENDING"
                existing.version += 1
        else:
            db.add(UnifiedTodo(
                tenant_id=_tid(), source_module="student-affairs",
                source_biz_type=spec["biz_type"], source_biz_id=row_id,
                todo_type=todo_type, assignee_id=assignee_id,
                student_id=student_id, title=spec["title"], status="PENDING",
            ))
    elif existing and existing.status != "DONE":
        existing.status = "DONE"
        existing.version += 1


def reconcile() -> None:
    with session() as db:
        for todo_type, spec in _SPECS.items():
            model = _model(spec["model"])
            rows = db.scalars(select(model).where(
                model.tenant_id == _tid(),
                model.is_deleted.is_(False),
            ).order_by(model.id.desc()).limit(500)).all()
            for row in rows:
                _ensure_todo(db, todo_type, row)
        db.commit()


def _preflight(todo_type: str, student_id: int) -> None:
    with session() as db:
        _assignee(db, _SPECS[todo_type], student_id)


def _result_notice(todo_type: str, row_id: int) -> None:
    from app.services.message_event_outbox_service import emit_receiver_notice, try_process_pending_outbox
    spec = _SPECS[todo_type]
    model = _model(spec["model"])
    with session() as db:
        row = db.get(model, int(row_id))
        if not row or row.is_deleted or row.tenant_id != _tid():
            return
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
    try_process_pending_outbox(worker_id="affairs-appeal-inline")


def install() -> None:
    from app.services import affairs_activity_service as activity
    from app.services import affairs_aid_service as aid
    from app.services import affairs_discipline_service as discipline
    from app.services import affairs_funding_service as funding
    from app.services import mobile_affairs_service as mobile_affairs

    originals = {
        "aid_submit": aid.submit_objection,
        "aid_review": aid.review_objection,
        "funding_submit": funding.submit_appeal,
        "funding_review": funding.review_appeal,
        "discipline_submit": discipline.submit_appeal,
        "discipline_review": discipline.review_appeal,
        "credit_submit": activity.submit_credit_appeal,
        "credit_review": activity.review_credit_appeal,
        "teacher_affairs": mobile_affairs.teacher_affairs,
    }

    def aid_submit(apply_id, body, user, **kwargs):
        from app.models import AidApply
        with session() as db:
            parent = db.get(AidApply, int(apply_id))
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                raise AppException("DATA_NOT_FOUND", "认定申请不存在")
            _preflight("AID_OBJECTION_REVIEW", int(parent.student_id))
        result = originals["aid_submit"](apply_id, body, user, **kwargs)
        reconcile()
        return result

    def aid_review(objection_id, body, user):
        result = originals["aid_review"](objection_id, body, user)
        _result_notice("AID_OBJECTION_REVIEW", int(objection_id))
        return result

    def funding_submit(app_id, body, user, **kwargs):
        from app.models import FundingApplication
        with session() as db:
            parent = db.get(FundingApplication, int(app_id))
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                raise AppException("DATA_NOT_FOUND", "资助申请不存在")
            _preflight("FUNDING_APPEAL_REVIEW", int(parent.student_id))
        result = originals["funding_submit"](app_id, body, user, **kwargs)
        reconcile()
        return result

    def funding_review(appeal_id, body, user):
        result = originals["funding_review"](appeal_id, body, user)
        _result_notice("FUNDING_APPEAL_REVIEW", int(appeal_id))
        return result

    def discipline_submit(case_id, body, user, **kwargs):
        from app.models import DisciplineCase
        with session() as db:
            parent = db.get(DisciplineCase, int(case_id))
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                raise AppException("DATA_NOT_FOUND", "处分记录不存在")
            _preflight("DISCIPLINE_APPEAL_REVIEW", int(parent.student_id))
        result = originals["discipline_submit"](case_id, body, user, **kwargs)
        reconcile()
        return result

    def discipline_review(appeal_id, body, user):
        result = originals["discipline_review"](appeal_id, body, user)
        _result_notice("DISCIPLINE_APPEAL_REVIEW", int(appeal_id))
        return result

    def credit_submit(body, user):
        student_id = int(getattr(body, "studentId", 0) or 0)
        _preflight("SECOND_CLASS_APPEAL_REVIEW", student_id)
        result = originals["credit_submit"](body, user)
        reconcile()
        return result

    def credit_review(appeal_id, body, user):
        result = originals["credit_review"](appeal_id, body, user)
        _result_notice("SECOND_CLASS_APPEAL_REVIEW", int(appeal_id))
        return result

    def teacher_affairs(user):
        reconcile()
        data = originals["teacher_affairs"](user)
        for card in data.get("cards", []):
            card["label"] = _LABELS.get(card.get("todoType"), card.get("label"))
        return data

    aid.submit_objection = aid_submit
    aid.review_objection = aid_review
    funding.submit_appeal = funding_submit
    funding.review_appeal = funding_review
    discipline.submit_appeal = discipline_submit
    discipline.review_appeal = discipline_review
    activity.submit_credit_appeal = credit_submit
    activity.review_credit_appeal = credit_review
    mobile_affairs.teacher_affairs = teacher_affairs
