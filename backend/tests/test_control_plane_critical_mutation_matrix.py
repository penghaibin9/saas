"""Item 5: runtime Critical Mutation Matrix on canonical replacement paths."""
from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import PlatformConfig
from app.services import platform_access_governance_service as pam
from app.services.audit_log import AuditPersistenceError


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _actor() -> dict:
    return {
        "userId": "920001",
        "currentRoleCode": "PLATFORM_OWNER",
        "userType": "PLATFORM_OWNER",
        "authTime": int(time.time()),
        "amr": ["pwd", "mfa"],
        "acr": "urn:mfa",
    }


def _force_audit_failure(monkeypatch):
    from app.services import db_service

    def boom(*args, **kwargs):
        raise RuntimeError("forced canonical critical-audit failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", boom)


def _config(config_type: str, key: str, *, tenant_id: int = 0, payload: dict | None = None) -> PlatformConfig:
    return PlatformConfig(
        tenant_id=tenant_id,
        config_type=config_type,
        config_key=key,
        config_json=payload or {},
        enabled=True,
        status="ACTIVE",
    )


def test_canonical_pam_assignment_business_write_rolls_back_on_audit_failure(db_mode, monkeypatch):
    request_id = f"matrix-duty-{uuid.uuid4().hex}"
    key = pam._canonical._base._idempotent_key("duty", request_id)
    _force_audit_failure(monkeypatch)

    with pytest.raises(AuditPersistenceError):
        pam.save_access_assignment(
            {
                "requestId": request_id,
                "userId": "920101",
                "dutyCode": "PLATFORM_COMMERCIAL",
                "reason": "关键变更矩阵审计故障注入",
                "status": "ACTIVE",
            },
            actor=_actor(),
        )

    with _session() as db:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == pam.ASSIGNMENT,
            PlatformConfig.config_key == key,
            PlatformConfig.is_deleted.is_(False),
        )).first()
        assert row is None, "critical audit failure must roll back the business grant row"


def test_access_review_revoke_is_atomic_when_audit_insert_fails(db_mode, monkeypatch):
    target_key = f"matrix-target-{uuid.uuid4().hex}"
    review_key = f"matrix-review-{uuid.uuid4().hex}"
    with _session() as db:
        target = _config(
            pam.ASSIGNMENT,
            target_key,
            payload={
                "userId": "920201",
                "dutyCode": "PLATFORM_COMMERCIAL",
                "status": "ACTIVE",
                "reason": "待复核职责",
            },
        )
        db.add(target)
        db.flush()
        target_version = int(target.version or 0)
        review = _config(
            pam.REVIEW,
            review_key,
            payload={
                "requestId": f"review-{uuid.uuid4().hex}",
                "name": "关键访问复核",
                "status": "OPEN",
                "items": [{
                    "itemKey": f"{pam.ASSIGNMENT}:0:{target_key}",
                    "configType": pam.ASSIGNMENT,
                    "tenantId": 0,
                    "recordId": target_key,
                    "version": target_version,
                    "snapshot": {"userId": "920201", "dutyCode": "PLATFORM_COMMERCIAL"},
                    "decision": "PENDING",
                }],
            },
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        review_version = int(review.version or 0)

    _force_audit_failure(monkeypatch)
    with pytest.raises(AuditPersistenceError):
        pam.close_access_review(
            review_key,
            {
                "expectedVersion": review_version,
                "reason": "关键变更矩阵验证整事务回滚",
                "decisions": [{
                    "itemKey": f"{pam.ASSIGNMENT}:0:{target_key}",
                    "decision": "REVOKE",
                }],
            },
            actor=_actor(),
        )

    with _session() as db:
        target = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == pam.ASSIGNMENT,
            PlatformConfig.config_key == target_key,
        )).one()
        review = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == pam.REVIEW,
            PlatformConfig.config_key == review_key,
        )).one()
        assert target.enabled is True
        assert target.config_json["status"] == "ACTIVE"
        assert int(target.version or 0) == target_version
        assert review.config_json["status"] == "OPEN"
        assert int(review.version or 0) == review_version


def test_two_real_mysql_sessions_produce_stale_version_conflict_on_canonical_pam(db_mode):
    key = f"matrix-concurrency-{uuid.uuid4().hex}"
    with _session() as db:
        row = _config(
            pam.ASSIGNMENT,
            key,
            payload={
                "userId": "920301",
                "dutyCode": "PLATFORM_COMMERCIAL",
                "status": "ACTIVE",
                "reason": "并发前值",
            },
        )
        db.add(row)
        db.commit()

    # Two independent real DB sessions observe the same version before either writer commits.
    session_a = _session()
    session_b = _session()
    try:
        row_a = session_a.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == pam.ASSIGNMENT,
            PlatformConfig.config_key == key,
        )).one()
        row_b = session_b.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == pam.ASSIGNMENT,
            PlatformConfig.config_key == key,
        )).one()
        version_a = int(row_a.version or 0)
        version_b = int(row_b.version or 0)
        assert version_a == version_b
    finally:
        session_a.close()
        session_b.close()

    first = pam.save_access_assignment(
        {
            "id": key,
            "expectedVersion": version_a,
            "userId": "920301",
            "dutyCode": "PLATFORM_COMMERCIAL",
            "reason": "会话 A 成功提交",
            "status": "ACTIVE",
        },
        actor=_actor(),
    )
    assert int(first["version"]) == version_a + 1

    with pytest.raises(AppException) as exc:
        pam.save_access_assignment(
            {
                "id": key,
                "expectedVersion": version_b,
                "userId": "920301",
                "dutyCode": "PLATFORM_COMMERCIAL",
                "reason": "会话 B 使用旧版本提交",
                "status": "ACTIVE",
            },
            actor=_actor(),
        )
    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409

    with _session() as db:
        final = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == pam.ASSIGNMENT,
            PlatformConfig.config_key == key,
        )).one()
        assert int(final.version or 0) == version_a + 1
        assert final.config_json["reason"] == "会话 A 成功提交"
