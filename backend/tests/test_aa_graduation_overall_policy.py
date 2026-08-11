"""Stage C3 毕业正式预审 overall 的 fail-closed 合同。"""
from app.modules.academic_affairs.services.academic_affairs_graduation_overall_policy import strict_overall


def _item(code: str, result: str):
    return {"item": code, "result": result}


def test_all_pass_is_required_for_formal_precheck():
    rows = [
        _item("STATUS", "PASS"),
        _item("CREDIT", "PASS"),
        _item("COURSE_REQUIRED", "PASS"),
        _item("COURSE_ELECTIVE", "PASS"),
        _item("PRACTICE", "PASS"),
        _item("INTERNSHIP", "PASS"),
        _item("GRADUATION_DESIGN", "PASS"),
        _item("DISCIPLINE", "PASS"),
        _item("EMPLOYMENT", "PASS"),
        _item("ARCHIVE", "PASS"),
        _item("FEE", "PASS"),
    ]
    assert strict_overall(rows) == "SYSTEM_PASSED"


def test_any_unknown_blocks_formal_precheck():
    assert strict_overall([_item("STATUS", "PASS"), _item("CREDIT", "UNKNOWN")]) == "SYSTEM_ABNORMAL"
    assert strict_overall([_item("STATUS", "PASS"), _item("EMPLOYMENT", "UNKNOWN")]) == "SYSTEM_ABNORMAL"
    assert strict_overall([_item("STATUS", "PASS"), _item("ARCHIVE", "UNKNOWN")]) == "SYSTEM_ABNORMAL"
    assert strict_overall([_item("STATUS", "PASS"), _item("FEE", "UNKNOWN")]) == "SYSTEM_ABNORMAL"


def test_any_fail_still_blocks_formal_precheck():
    assert strict_overall([_item("STATUS", "PASS"), _item("FEE", "FAIL")]) == "SYSTEM_ABNORMAL"


def test_empty_or_missing_result_fails_closed():
    assert strict_overall([]) == "SYSTEM_ABNORMAL"
    assert strict_overall([{"item": "STATUS"}]) == "SYSTEM_ABNORMAL"
