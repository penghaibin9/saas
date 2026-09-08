from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.file_access_service import (
    STATUS_TEXT,
    _binding_subject_allows,
    resolver_registry_snapshot,
)


def binding(subject_type: str, subject_id: str | None = None, batch_id: str | None = None):
    return SimpleNamespace(subject_type=subject_type, subject_id=subject_id, batch_id=batch_id)


def test_registry_contains_student_affairs_resolvers() -> None:
    registry = resolver_registry_snapshot()
    assert registry["DISCIPLINE"].endswith("._student_affairs_resolver")
    assert registry["FUNDING"] == "app.services.file_access_resolvers.funding_evidence_resolver"


def test_student_binding_never_allows_other_student() -> None:
    item = binding("STUDENT", "S-100")
    assert _binding_subject_allows(item, {"userType": "STUDENT", "studentNo": "S-100"}) is True
    assert _binding_subject_allows(item, {"userType": "STUDENT", "studentNo": "S-200"}) is False


@pytest.mark.parametrize("change", [
    {}, {"is_deleted": True}, {"status": "INACTIVE"}, {"is_current": False},
    {"biz_type": "AID"}, {"biz_id": "999"}, {"relation_type": "INTERNAL"},
    {"subject_type": "USER"}, {"subject_id": "22"},
])
def test_funding_student_requires_current_own_business_evidence(monkeypatch, change) -> None:
    from app.services import file_access_resolvers, mobile_student_service

    student = SimpleNamespace(id=21)
    application = SimpleNamespace(id=7, tenant_id=1, student_id=21, is_deleted=False)
    db = SimpleNamespace(get=lambda model, key: application)
    file_obj = SimpleNamespace(biz_id="7", tenant_id=1, owner_user_id="101", created_by="101")
    user = {"userType": "STUDENT", "userId": "101"}
    evidence = dict(is_deleted=False, status="ACTIVE", is_current=True, biz_type="FUNDING",
                    biz_id="7", relation_type="BUSINESS_EVIDENCE", subject_type="STUDENT", subject_id="21")
    evidence.update(change)
    monkeypatch.setattr(mobile_student_service, "resolve_student", lambda db, user: student)
    monkeypatch.setattr(file_access_resolvers, "resolve_message_user_id", lambda user: 101)
    resolve = file_access_resolvers.funding_evidence_resolver
    assert resolve(db, file_obj, [SimpleNamespace(**evidence)], user, "read") is (not change)
    # A teacher's internal upload must stay private even on this student's application.
    file_obj.owner_user_id = "202"
    assert resolve(db, file_obj, [SimpleNamespace(**evidence)], user, "read") is False
    file_obj.owner_user_id = "101"
    application.student_id = 22
    assert resolve(db, file_obj, [SimpleNamespace(**evidence)], user, "read") is False


def test_batch_binding_never_allows_other_batch() -> None:
    item = binding("BUSINESS_OBJECT", batch_id="B-2026-01")
    assert _binding_subject_allows(item, {"allowedBatchIds": ["B-2026-01"]}) is True
    assert _binding_subject_allows(item, {"allowedBatchIds": ["B-2026-02"]}) is False
    assert _binding_subject_allows(item, {}) is False


def test_status_text_contract_is_frozen() -> None:
    assert STATUS_TEXT == {
        "NOT_REQUIRED": "无需扫描",
        "PENDING": "等待安全扫描",
        "RUNNING": "正在安全扫描",
        "CLEAN": "安全可用",
        "INFECTED": "检测到风险，已拒绝",
        "ERROR": "安全扫描失败",
    }
