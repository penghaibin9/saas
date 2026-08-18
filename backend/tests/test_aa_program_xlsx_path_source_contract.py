"""Source contracts for Program XLSX path-backed shared runtime."""
from __future__ import annotations

import inspect
import zipfile

import pytest

from app.core.exceptions import AppException
from app.services import xlsx_util


def test_program_shared_runtime_stays_path_backed_and_reuses_package_guard():
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.modules.academic_affairs.services import (
        academic_affairs_school_setup_program_workbook_adapter as workbook,
    )

    exchange_source = inspect.getsource(exchange)
    parse_source = inspect.getsource(exchange._parse_and_validate)
    path_reader_source = inspect.getsource(workbook.read_program_workbook_path)
    path_validator_source = inspect.getsource(xlsx_util.validate_xlsx_path)
    bytes_validator_source = inspect.getsource(xlsx_util.validate_xlsx_package)

    assert ".read_bytes(" not in exchange_source
    assert "parse_and_normalize_program_workbook_path(" in parse_source
    assert "xlsx_util.validate_xlsx_path(" in path_reader_source
    assert "_validate_xlsx_archive(archive)" in path_validator_source
    assert "_validate_xlsx_archive(archive)" in bytes_validator_source
    assert "max_bytes" in inspect.signature(workbook.read_program_workbook_path).parameters
    assert "max_bytes" in inspect.signature(workbook.parse_and_normalize_program_workbook_path).parameters


def test_validate_xlsx_path_keeps_archive_security_policy(tmp_path):
    source_path = tmp_path / "external-link.xlsx"
    with zipfile.ZipFile(source_path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/externalLinks/externalLink1.xml", "<externalLink />")

    with pytest.raises(AppException, match="XLSX 不允许宏、嵌入对象或外部链接"):
        xlsx_util.validate_xlsx_path(source_path)
