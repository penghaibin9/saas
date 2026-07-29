"""移动教务读入口不得使用教师姓名作为授权标识。"""


def test_mobile_teacher_keys_exclude_real_name():
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as service

    keys = service.stable_teacher_keys({
        "userId": "u_T001",
        "loginName": "T001",
        "activeContextId": "ctx_T001",
        "realName": "张伟",
    })

    assert "T001" in keys
    assert "张伟" not in keys


def test_mobile_primary_key_prefers_login_name():
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as service

    assert service.stable_teacher_key({
        "userId": "u_99",
        "loginName": "T001",
        "activeContextId": "ctx_other",
        "realName": "张伟",
    }) == "T001"


def test_public_mobile_service_points_to_identity_facade():
    from app.modules.academic_affairs import services

    assert services.mobile_academic_affairs_service.stable_teacher_key.__module__.endswith(
        "mobile_academic_affairs_facade"
    )
