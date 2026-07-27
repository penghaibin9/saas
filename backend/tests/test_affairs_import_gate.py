"""学工旧域导入关闭门禁；正式迁移中心由其自身测试覆盖。"""
import pytest


def test_legacy_student_affairs_import_is_disabled_but_export_remains():
    from app.core.exceptions import AppException
    from app.core.import_export_auth import EXPORT_DOMAINS, IMPORT_DOMAINS, resolve_domain

    assert "student-affairs" not in IMPORT_DOMAINS
    assert "student-affairs" in EXPORT_DOMAINS
    with pytest.raises(AppException) as exc:
        resolve_domain("student-affairs", for_import=True)
    assert exc.value.code == "VALIDATION_ERROR"
    assert resolve_domain("student-affairs", for_export=True).export_perm == "studentAffairs.export"
