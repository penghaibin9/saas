"""Only reversible offboarding in the isolated pytest MySQL fixture; no purge calls."""
import pytest

from app.core.exceptions import AppException
from app.services import tenant_offboarding_service as service
from app.services.tenant_effective_state_service import get_effective_state

TID = 1000000000000000001
ACTOR = {"userId": "1"}


def test_freeze_export_and_cancel_restore_the_original_state(db_mode):
    before = get_effective_state(TID, strict=True)
    created = service.request_offboarding(ACTOR, TID, reason="测试学校确认进行可逆的退出服务核验", expected_version=before["version"], retention_days=30)
    assert created["state"] == "FROZEN_READONLY"
    assert created["tenantId"] == str(TID)
    assert get_effective_state(TID, strict=True)["effectiveStatus"] == "readonly"
    kept = service.confirm_final_export(ACTOR, int(created["jobId"]), sha256="a" * 64)
    assert kept["state"] == "RETENTION"
    assert kept["finalExportSha256"] == "a" * 64
    assert get_effective_state(TID, strict=True)["effectiveStatus"] == "disabled"
    cancelled = service.cancel_offboarding(ACTOR, int(created["jobId"]), reason="核验结束恢复原状态")
    assert cancelled["state"] == "CANCELLED"
    assert get_effective_state(TID, strict=True)["effectiveStatus"] == before["effectiveStatus"]
    assert cancelled["purgeEvidenceSha256"] is None


def test_duplicate_request_is_rejected_while_original_task_remains(db_mode):
    version = service.preview_offboarding(TID)["effectiveState"]["version"]
    created = service.request_offboarding(ACTOR, TID, reason="隔离测试验证不能重复创建退出任务", expected_version=version, retention_days=30)
    with pytest.raises(AppException):
        service.request_offboarding(ACTOR, TID, reason="同一个学校重复申请退出应被阻止", expected_version=version, retention_days=30)
    assert service.get_active_job_for_tenant(TID)["jobId"] == created["jobId"]


def test_invalid_export_digest_does_not_advance_frozen_job(db_mode):
    version = service.preview_offboarding(TID)["effectiveState"]["version"]
    created = service.request_offboarding(ACTOR, TID, reason="隔离测试验证数据交付摘要必须完整", expected_version=version, retention_days=30)
    with pytest.raises(AppException):
        service.confirm_final_export(ACTOR, int(created["jobId"]), sha256="not-a-sha")
    assert service.get_job(int(created["jobId"]))["state"] == "FROZEN_READONLY"
