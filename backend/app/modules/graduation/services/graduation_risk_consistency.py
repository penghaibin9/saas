"""毕业设计风险台账并发与输入一致性。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import GraduationRiskCase, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session

_INSTALLED = False


def _locked(db, risk_id, action):
    risk = db.scalars(select(GraduationRiskCase).where(
        GraduationRiskCase.id == int(risk_id),
        GraduationRiskCase.tenant_id == _tid(),
        GraduationRiskCase.is_deleted.is_(False),
    ).with_for_update()).first()
    if not risk:
        raise not_found("风险记录不存在")
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == risk.gd_student_id,
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
    ).with_for_update()).first()
    assert_student_access(db, student, action)
    return risk, student


def accept_risk(risk_id, assignee: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_risk_service as service
    with session() as db:
        risk, student = _locked(db, risk_id, "risk.accept")
        operator, _ = service._op()
        target = str(assignee or operator or "").strip()
        if not target:
            raise AppException("VALIDATION_ERROR", "风险受理人不能为空")
        if len(target) > 100:
            raise AppException("VALIDATION_ERROR", "风险受理人不得超过 100 字")
        if risk.status == "PROCESSING" and (risk.assignee or "").strip() == target:
            return service._row(risk, student)
        if risk.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅待受理风险可受理")
        risk.status = "PROCESSING"
        risk.assignee = target
        service._audit(db, risk.id, "受理风险", f"assignee={target}")
        db.commit()
        return service._row(risk, student)


def process_risk(risk_id, note: str) -> dict:
    from app.modules.graduation.services import graduation_risk_service as service
    content = str(note or "").strip()
    if len(content) < 2:
        raise AppException("VALIDATION_ERROR", "处理说明至少 2 字")
    if len(content) > 1000:
        raise AppException("VALIDATION_ERROR", "处理说明不得超过 1000 字")
    with session() as db:
        risk, student = _locked(db, risk_id, "risk.process")
        if risk.status != "PROCESSING":
            raise AppException("DATA_CONFLICT", "仅处理中风险可记录处理")
        if (risk.handle_note or "").strip() == content:
            return service._row(risk, student)
        risk.handle_note = content
        service._audit(db, risk.id, "处理风险", content)
        db.commit()
        return service._row(risk, student)


def close_risk(risk_id, reason: str) -> dict:
    from app.modules.graduation.services import graduation_risk_service as service
    content = str(reason or "").strip()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "关闭原因必填且不少于 5 字")
    if len(content) > 500:
        raise AppException("VALIDATION_ERROR", "关闭原因不得超过 500 字")
    with session() as db:
        risk, student = _locked(db, risk_id, "risk.close")
        if risk.status == "CLOSED":
            if (risk.close_reason or "").strip() == content:
                return service._row(risk, student)
            raise AppException("DATA_CONFLICT", "风险已关闭，不能覆盖原关闭原因")
        allow_open_inactive = risk.status == "OPEN" and getattr(risk, "condition_active", True) is False
        if risk.status != "PROCESSING" and not allow_open_inactive:
            raise AppException("DATA_CONFLICT", "仅处理中风险可关闭（条件已消失的待受理除外）")
        risk.status = "CLOSED"
        risk.close_reason = content
        risk.closed_at = service._now()
        service._audit(db, risk.id, "关闭风险", content)
        db.commit()
        return service._row(risk, student)


def install_risk_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.modules.graduation.services import graduation_risk_service as service
    service.accept_risk = accept_risk
    service.process_risk = process_risk
    service.close_risk = close_risk
    _INSTALLED = True
