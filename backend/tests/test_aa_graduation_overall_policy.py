"""Stage C3 不可变毕业 evaluator 的 fail-closed overall 合同。"""
from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable


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
    assert immutable._strict_overall(rows) == "SYSTEM_PASSED"


def test_any_unknown_blocks_formal_precheck():
    assert immutable._strict_overall([_item("STATUS", "PASS"), _item("CREDIT", "UNKNOWN")]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall([_item("STATUS", "PASS"), _item("EMPLOYMENT", "UNKNOWN")]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall([_item("STATUS", "PASS"), _item("ARCHIVE", "UNKNOWN")]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall([_item("STATUS", "PASS"), _item("FEE", "UNKNOWN")]) == "SYSTEM_ABNORMAL"


def test_any_fail_still_blocks_formal_precheck():
    assert immutable._strict_overall([_item("STATUS", "PASS"), _item("FEE", "FAIL")]) == "SYSTEM_ABNORMAL"


def test_empty_or_missing_result_fails_closed():
    assert immutable._strict_overall([]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall([{"item": "STATUS"}]) == "SYSTEM_ABNORMAL"
