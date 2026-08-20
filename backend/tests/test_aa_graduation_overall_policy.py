"""Stage C3 不可变毕业 evaluator 的 fail-closed overall 合同。"""
from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable
from app.modules.academic_affairs.services import academic_affairs_graduation_service as graduation_service


def _item(code: str, result: str):
    return {"item": code, "result": result}


def _complete_rows(*, employment="UNKNOWN", fee="UNKNOWN"):
    required = set(graduation_service._BLOCKING_UNKNOWN_ITEMS) | {"ARCHIVE"}
    rows = [_item(code, "PASS") for code in sorted(required)]
    rows.extend([_item("EMPLOYMENT", employment), _item("FEE", fee)])
    return rows


def _replace(rows, code: str, result: str):
    return [
        _item(row["item"], result if row["item"] == code else row["result"])
        for row in rows
    ]


def test_required_items_pass_allows_advisory_unknowns():
    rows = _complete_rows(employment="UNKNOWN", fee="UNKNOWN")
    assert immutable._strict_overall(rows) == "SYSTEM_PASSED"


def test_required_unknown_still_blocks_formal_precheck():
    rows = _complete_rows()
    assert immutable._strict_overall(_replace(rows, "CREDIT", "UNKNOWN")) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(_replace(rows, "ARCHIVE", "UNKNOWN")) == "SYSTEM_ABNORMAL"


def test_known_fail_blocks_even_on_advisory_domain():
    rows = _complete_rows()
    assert immutable._strict_overall(_replace(rows, "FEE", "FAIL")) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(_replace(rows, "EMPLOYMENT", "FAIL")) == "SYSTEM_ABNORMAL"


def test_empty_missing_or_malformed_required_evidence_fails_closed():
    assert immutable._strict_overall([]) == "SYSTEM_ABNORMAL"
    rows = _complete_rows()
    assert immutable._strict_overall([row for row in rows if row["item"] != "ARCHIVE"]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(_replace(rows, "CREDIT", "UNSUPPORTED")) == "SYSTEM_ABNORMAL"


def test_compat_projection_recompute_uses_same_stage_c3_policy():
    """费用回填等旧 projection 写入口必须复用 immutable 的同一 overall 边界。"""
    assert graduation_service._overall is immutable._strict_overall
    rows = _complete_rows(employment="UNKNOWN", fee="UNKNOWN")
    assert graduation_service._overall(rows) == "SYSTEM_PASSED"
    assert graduation_service._overall(_replace(rows, "ARCHIVE", "UNKNOWN")) == "SYSTEM_ABNORMAL"
