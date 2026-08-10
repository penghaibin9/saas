from __future__ import annotations

import importlib
import inspect


def test_deferred_exam_public_contract_resolves_exact_legacy_module():
    """Package facade alias must not change the canonical deferred-exam state source."""
    services = importlib.import_module("app.modules.academic_affairs.services")
    facade = services.academic_affairs_exam_service
    legacy = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_exam_service"
    )
    contract = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_exam_public_contract"
    )

    # The package intentionally exposes the facade under this public attribute.
    assert facade.__name__.endswith("academic_affairs_exam_facade")
    # Exact module import still resolves the canonical legacy state machine.
    assert legacy.__name__.endswith("academic_affairs_exam_service")
    assert contract.DEFER_STATUS_COUNSELOR_REVIEW == legacy._D_COUNSELOR
    assert contract.DEFER_STATUS_APPROVED == legacy._D_APPROVED
    assert contract.DEFER_STATUS_REJECTED == legacy._D_REJECTED
    assert contract.DEFER_TERMINAL_STATUSES == frozenset({legacy._D_APPROVED, legacy._D_REJECTED})


def test_student_exam_reader_has_no_direct_legacy_private_dependency():
    from app.modules.academic_affairs.services import student_exam_read_service as student_exam

    source = inspect.getsource(student_exam)
    assert "academic_affairs_exam_public_contract as exam_contract" in source
    for forbidden in (
        "legacy._D_",
        "legacy._audit",
        "legacy._defer_dto",
        "import app.modules.academic_affairs.services.academic_affairs_exam_service as legacy",
    ):
        assert forbidden not in source


def test_public_contract_keeps_canonical_dto_and_audit_adapters():
    contract = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_exam_public_contract"
    )
    legacy = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_exam_service"
    )

    assert contract._legacy is legacy
    assert callable(contract.deferred_exam_dto)
    assert callable(contract.record_exam_audit)
