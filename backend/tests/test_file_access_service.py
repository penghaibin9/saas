from __future__ import annotations

from types import SimpleNamespace

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
    assert registry["FUNDING"].endswith("._student_affairs_resolver")


def test_student_binding_never_allows_other_student() -> None:
    item = binding("STUDENT", "S-100")
    assert _binding_subject_allows(item, {"userType": "STUDENT", "studentNo": "S-100"}) is True
    assert _binding_subject_allows(item, {"userType": "STUDENT", "studentNo": "S-200"}) is False


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
