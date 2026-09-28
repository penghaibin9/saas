from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.core.exceptions import AppException
from app.modules.internship.services import internship_regulatory_reporting_service as svc


def test_c07_status_contract_is_exact():
    assert svc.TASK_STATUSES == (
        "GENERATED",
        "VALIDATED",
        "EXPORTED",
        "SUBMITTED_EXTERNAL",
        "RECEIPT_PENDING",
        "ACCEPTED",
        "REJECTED",
    )


def test_rp01_required_enum_and_cross_field_validation():
    row = {field["key"]: "X" for field in svc.baseline_definition("RP01")["fields"]}
    row.update({
        "gender": "男",
        "insured": "否",
        "agreementSigned": "否",
        "majorMatch": "是",
        "highRisk": "是",
        "nightOrOvertime": "否",
        "holidayInternship": "否",
        "filingStatus": "待备案",
        "missingDocumentExplanation": "",
        "highRiskType": "",
        "internshipStartDate": "2026-09-01",
        "internshipEndDate": "2026-08-31",
    })
    errors = svc.validate_row("RP01", row)
    codes = {(e["field"], e["code"]) for e in errors}
    assert ("missingDocumentExplanation", "CROSS_FIELD") in codes
    assert ("highRiskType", "CROSS_FIELD") in codes
    assert ("internshipEndDate", "CROSS_FIELD") in codes


def test_rp02_overseas_requires_country():
    row = {field["key"]: "X" for field in svc.baseline_definition("RP02")["fields"]}
    row.update({
        "majorMatch": "是",
        "agreementSigned": "是",
        "overseas": "是",
        "crossProvince": "未知",
        "workCountry": "",
        "internshipStartDate": "2026-09-01",
        "internshipEndDate": "2026-12-01",
    })
    errors = svc.validate_row("RP02", row)
    assert any(
        e["field"] == "workCountry" and e["code"] == "CROSS_FIELD"
        for e in errors
    )


def test_formal_xlsx_keeps_credit_code_and_student_no_as_text():
    definition = svc.baseline_definition("RP01")
    row = {field["key"]: "" for field in definition["fields"]}
    row["studentNo"] = "001234"
    row["companyCreditCode"] = "012345678901234567"
    payload = svc.build_workbook("RP01", [row], definition)
    wb = load_workbook(BytesIO(payload))
    ws = wb["RP01"]
    labels = [c.value for c in ws[1]]
    credit_col = labels.index("统一社会信用代码") + 1
    student_col = labels.index("学号") + 1
    assert ws.cell(2, credit_col).value == "012345678901234567"
    assert ws.cell(2, credit_col).number_format == "@"
    assert ws.cell(2, student_col).value == "001234"
    assert ws.cell(2, student_col).number_format == "@"


def test_procurement_baseline_never_claims_official_template():
    for code in svc.REPORT_CODES:
        definition = svc.baseline_definition(code)
        assert definition["officialVerified"] is False
        assert "采购" in definition["templateName"]


def test_receipt_is_blocked_without_real_adapter(monkeypatch):
    monkeypatch.setattr(
        svc.settings,
        "REGULATORY_RECEIPT_ADAPTER_ENABLED",
        False,
        raising=False,
    )
    with pytest.raises(AppException) as exc:
        svc.record_external_receipt(
            1,
            {"status": "ACCEPTED", "receiptCode": "fake"},
        )
    assert "回执" in str(exc.value)
