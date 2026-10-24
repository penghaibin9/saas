from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.services import approval_business_context_service as service


def test_unsupported_details_keep_the_original_type_but_not_in_the_message():
    result = service.resolve_context(None, SimpleNamespace(source_biz_type="COMPANY_CHANGE", source_biz_id=123))
    assert result["sourceBizType"] == "COMPANY_CHANGE"
    assert result["sourceBizId"] == "123"
    assert result["completeness"] == service.UNSUPPORTED
    assert result["sections"] == result["attachments"] == []
    assert result["note"] == "此类申请暂不支持在本页查看业务详情。"


def test_read_failure_is_not_reported_as_empty_or_unsupported(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("internal details")
    monkeypatch.setitem(service._ADAPTERS, "LANGUAGE_TEST", fail)
    result = service.resolve_context(None, SimpleNamespace(source_biz_type="LANGUAGE_TEST", source_biz_id=123))
    assert result["completeness"] == service.ERROR
    assert result["note"] == "业务信息读取失败，请稍后重试"
    assert "RuntimeError" not in result["note"]


def test_read_failure_and_missing_version_still_prevent_approval():
    kind = service.supported_biz_types()[0]
    with pytest.raises(AppException) as failed:
        service.assert_action_context({"sourceBizType": kind, "completeness": service.ERROR}, 1)
    assert failed.value.code == "APPROVAL_CONTEXT_INCOMPLETE"
    assert failed.value.http_status == 409
    assert failed.value.message == "业务信息不完整或无法读取，请刷新后再审批"
    with pytest.raises(AppException) as missing:
        service.assert_action_context({"sourceBizType": kind, "completeness": service.FULL}, None)
    assert missing.value.code == "APPROVAL_CONTEXT_VERSION_REQUIRED"
    assert missing.value.http_status == 409
