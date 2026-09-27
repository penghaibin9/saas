def test_standalone_module_access_only_allows_internship():
    from app.core.exceptions import AppException
    from app.services.module_access_service import assert_module_access

    assert assert_module_access(1, "internship", write=True)["writeAllowed"] is True
    try:
        assert_module_access(1, "graduation", write=False)
    except AppException as exc:
        assert exc.code == "NO_PERMISSION"
    else:
        raise AssertionError("non-internship module must fail closed")


def test_student_portal_print_log_imports():
    from app.student_portal.services.common_service import print_log
    assert callable(print_log)
