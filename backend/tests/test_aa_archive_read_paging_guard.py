"""PR #101 production audit: archive batch reads use bounded SQL pagination."""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_archive_read_guard as guard
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service


def test_archive_read_guard_is_installed_at_package_import():
    assert archive_service.list_batches is guard.list_batches
    assert getattr(archive_service.list_batches, "_archive_sql_paging_guard", False) is True


def test_archive_batch_list_uses_sql_count_offset_limit_not_python_slice():
    source = inspect.getsource(guard.list_batches)
    assert "select(func.count(AaArchiveBatch.id))" in source
    assert ".offset((page_no - 1) * size)" in source
    assert ".limit(size)" in source
    assert "rows[(page" not in source
    assert "len(rows)" not in source


@pytest.mark.parametrize(
    "kwargs",
    [
        {"page": 0},
        {"page": -1},
        {"page": "bad"},
        {"page_size": 0},
        {"page_size": 201},
        {"page_size": "bad"},
    ],
)
def test_archive_batch_list_rejects_invalid_paging_before_database_access(kwargs):
    with pytest.raises(AppException) as exc:
        guard.list_batches(object(), **kwargs)
    assert exc.value.code == "VALIDATION_ERROR"
