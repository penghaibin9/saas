from app.services import platform_defaults as platform_defaults
from app.services import effective_security_policy_service as effective_policy


def test_platform_security_surface_covers_all_effective_login_policy_controls():
    """平台主管可编辑项必须覆盖真正进入登录 runtime 的六个安全参数。"""
    keys = {
        "loginFailMaxTimes",
        "loginFailLockMinutes",
        "passwordMinLength",
        "captchaAfterFailures",
        "accessTokenExpireMinutes",
        "refreshTokenExpireDays",
    }
    assert keys <= set(platform_defaults.DEFAULT_SECURITY)
    assert keys <= set(platform_defaults.SECURITY_BOUNDS)

    for key in keys:
        assert platform_defaults.DEFAULT_SECURITY[key] == effective_policy._BASELINE[key]
        assert platform_defaults.SECURITY_BOUNDS[key] == effective_policy._BOUNDS[key]
