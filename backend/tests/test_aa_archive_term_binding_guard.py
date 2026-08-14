"""PR #101 production audit: archive batches must be bound to a real academic term."""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.routers import archive_core_router
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service
from app.modules.academic_affairs.services import academic_affairs_archive_term_guard as guard


def test_archive_term_guard_is_installed_at_package_import():
    assert archive_service.create_batch is guard.create_batch
    assert archive_service.validate_term_id is guard.validate_term_id
    assert getattr(archive_service.create_batch, "_archive_term_binding_guard", False) is True


def test_archive_batch_create_router_checks_term_after_permission_dependency():
    source = inspect.getsource(archive_core_router.archive_batch_create)
    assert "archive_svc.validate_term_id(body.termId)" in source
    # Keep the body field Optional so an unauthorized request still reaches the permission
    # dependency instead of leaking the business validation contract as an early 422.
    assert archive_core_router.ArchiveBatchBody.model_fields["termId"].is_required() is False


@pytest.mark.parametrize("raw", [None, "", "   ", "abc", "0", "-1"])
def test_archive_term_guard_rejects_missing_or_invalid_term_id(raw):
    with pytest.raises(AppException) as exc:
        guard.validate_term_id(raw)
    assert exc.value.code == "VALIDATION_ERROR"


def test_archive_term_guard_accepts_positive_integer_ids():
    assert guard.validate_term_id("12") == 12
    assert guard.validate_term_id(12) == 12
