"""毕业正式预审 overall 的阻断/非阻断 UNKNOWN 合同。"""
from app.modules.academic_affairs.services.academic_affairs_graduation_overall_policy import strict_overall


def _item(code: str, result: str):
    return {"item": code, "result": result}


def test_nonblocking_unknown_does_not_block_formal_precheck():
    rows = [
        _item("STATUS", "PASS"),
        _item("CREDIT", "PASS"),
        _item("COURSE_REQUIRED", "PASS"),
        _item("COURSE_ELECTIVE", "PASS"),
        _item("PRACTICE", "PASS"),
        _item("INTERNSHIP", "PASS"),
        _item("GRADUATION_DESIGN", "PASS"),
        _item("DISCIPLINE", "PASS"),
        _item("EMPLOYMENT", "UNKNOWN"),
        _item("ARCHIVE", "UNKNOWN"),
        _item("FEE", "UNKNOWN"),
    ]
    assert strict_overall(rows) == "SYSTEM_PASSED"


def test_blocking_unknown_still_blocks_formal_precheck():
    assert strict_overall([_item("STATUS", "PASS"), _item("CREDIT", "UNKNOWN")]) == "SYSTEM_ABNORMAL"


def test_any_fail_still_blocks_formal_precheck():
    assert strict_overall([_item("STATUS", "PASS"), _item("FEE", "FAIL")]) == "SYSTEM_ABNORMAL"
