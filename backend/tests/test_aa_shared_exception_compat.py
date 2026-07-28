"""教务服务使用共享异常模块时仍必须保持 fail-closed。"""


def test_no_data_scope_helper_is_additive_and_forbidden_by_default():
    from app.core.exceptions import CODE_HTTP, no_data_scope

    exc = no_data_scope("没有可用范围", details={"scope": "NONE"})
    assert exc.code == "NO_DATA_SCOPE"
    assert exc.http_status == 403
    assert exc.message == "没有可用范围"
    assert exc.details == {"scope": "NONE"}
    assert CODE_HTTP["NO_DATA_SCOPE"] == 403
