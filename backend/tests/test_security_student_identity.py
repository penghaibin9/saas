"""稳定学生身份由登录声明与账号绑定共同证明，不修改主线认证热路径。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECURITY = (ROOT / "app/core/security.py").read_text(encoding="utf-8")
AUTH_SERVICE = (ROOT / "app/services/auth_service_db.py").read_text(encoding="utf-8")
RESOLVER = (ROOT / "app/services/mobile_student_identity_facade.py").read_text(encoding="utf-8")


def test_login_claims_keep_stable_student_identity_for_future_consumers():
    assert 'claims["studentId"] = str(student_id)' in AUTH_SERVICE


def test_academic_student_resolution_uses_account_binding_fail_closed():
    assert 'student_id = u.get("studentId")' in RESOLVER
    assert "get_student_id_by_user" in RESOLVER
    assert "allow_legacy_fallback=True" in RESOLVER
    assert "有真实账号ID却无法建立绑定证据时必须停止" in RESOLVER
    assert "return None" in RESOLVER


def test_auth_core_remains_byte_compatible_in_behavior_with_current_main():
    assert "validate_token_subject(user)" in SECURITY
    assert "user = validate_token_subject(user)" not in SECURITY
    assert '"studentId": claims.get("studentId")' not in SECURITY


def test_auth_hot_path_does_not_query_student_profile_again():
    assert "_refresh_current_student_identity" not in SECURITY
    assert "get_sessionmaker" not in SECURITY
    assert "StudentProfile" not in SECURITY
