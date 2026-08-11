"""Stage C3 不可变毕业 evaluator 的 fail-closed overall 合同。"""
from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable
from app.modules.academic_affairs.services import academic_affairs_graduation_service as graduation_service


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


def test_compat_projection_recompute_uses_same_stage_c3_policy():
    """费用回填等旧 projection 写入口不得再把 immutable UNKNOWN 重新算成 PASS。"""
    assert graduation_service._overall is immutable._strict_overall
    rows = [_item("STATUS", "PASS"), _item("ARCHIVE", "UNKNOWN"), _item("FEE", "PASS")]
    assert graduation_service._overall(rows) == "SYSTEM_ABNORMAL"
