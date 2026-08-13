"""生产审计 Issue 2：critical audit 必须能与业务事实共享同一事务。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.context import set_tenant
from app.services import audit_log
from app.services.audit_log import AuditPersistenceError

TENANT_ID = 1000000000000000001
ACTION = "USER_ROLE_ASSIGN"


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _ensure_tenant() -> None:
    from app.models import Tenant
    with _session() as db:
        if db.get(Tenant, TENANT_ID) is None:
            db.add(Tenant(id=TENANT_ID, tenant_code="audit-atomicity",
                          school_name="审计原子性测试学校", status="ACTIVE"))
            db.commit()
    set_tenant({"tenantId": TENANT_ID})


def _count(resource: str) -> int:
    from app.models import SecurityAuditLog
    with _session() as db:
        return int(db.scalar(select(func.count(SecurityAuditLog.id)).where(
            SecurityAuditLog.tenant_id == TENANT_ID,
            SecurityAuditLog.action == ACTION,
            SecurityAuditLog.resource == resource,
        )) or 0)


def test_record_critical_in_session_rollback_removes_audit_fact(db_mode):
    _ensure_tenant()
    resource = f"atomic-rollback-{uuid.uuid4().hex}"
    with _session() as db:
        audit_log.record_critical_in_session(
            db, ACTION, resource, detail={"reason": "故障注入回滚验证"}, tenant_id=TENANT_ID
        )
        db.flush()
        db.rollback()
    assert _count(resource) == 0


def test_record_critical_in_session_commit_persists_audit_fact(db_mode):
    _ensure_tenant()
    resource = f"atomic-commit-{uuid.uuid4().hex}"
    with _session() as db:
        audit_log.record_critical_in_session(
            db, ACTION, resource, detail={"reason": "同事务提交验证"}, tenant_id=TENANT_ID
        )
        db.commit()
    assert _count(resource) == 1


def test_record_critical_in_session_propagates_insert_failure(db_mode, monkeypatch):
    from app.services import db_service
    _ensure_tenant()

    def _boom(*args, **kwargs):
        raise RuntimeError("forced audit insert failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", _boom)
    with _session() as db, pytest.raises(AuditPersistenceError):
        audit_log.record_critical_in_session(
            db, ACTION, f"atomic-fail-{uuid.uuid4().hex}",
            detail={"reason": "故障注入"}, tenant_id=TENANT_ID
        )


def test_record_critical_in_session_rejects_noncritical_action(db_mode):
    _ensure_tenant()
    with _session() as db, pytest.raises(ValueError):
        audit_log.record_critical_in_session(
            db, "LOGIN_SUCCESS", "not-critical", detail={}, tenant_id=TENANT_ID
        )
