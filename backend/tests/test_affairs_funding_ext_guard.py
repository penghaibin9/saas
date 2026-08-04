"""勤工助学、贷款、减免静态回归合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_extension_dtos_return_version_and_backend_actions():
    text = source("backend/app/services/affairs_funding_ext_service.py")
    assert text.count('"version": int(') >= 4
    assert '"APPLIED": ["APPROVE", "REJECT"]' in text
    assert '"APPROVED": ["ONBOARD", "TERMINATE"]' in text
    assert 'x.status in _LOAN_NEXT' in text
    assert '"APPROVED": ["ISSUE"]' in text


def test_work_study_capacity_and_monthly_totals_are_locked():
    text = source("backend/app/services/affairs_funding_ext_service.py")
    assert text.count(".with_for_update()") >= 3
    assert "岗位录用人数已满" in text
    assert "累计补贴超过金额上限" in text
    assert "该月已考核" in text


def test_monthly_and_money_inputs_fail_before_mysql():
    text = source("backend/app/services/affairs_funding_ext_service.py")
    assert 're.fullmatch(r"\\d{4}-(0[1-9]|1[0-2])", month)' in text
    assert "工时应为0-9999.99且最多2位小数" in text
    assert 'Decimal("999999999999.99")' in text
    assert "_scope_or_403(db, record.student_id, user)" in text
    assert "银行卡后4位必须为4位数字" in text
