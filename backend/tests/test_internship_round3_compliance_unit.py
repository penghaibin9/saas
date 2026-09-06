from datetime import date, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.internship.services.internship_position_rights import (
    evaluate_position_publishability,
)
from app.modules.internship.services.internship_compliance_service import (
    _is_adult,
    _student_birth_date,
)
from app.core.field_crypto import encrypt_sensitive
from app.modules.internship.schemas.internship_position import (
    PositionCreate,
    PositionImport,
    PositionUpdate,
)


def _batch(**overrides):
    compliance = {
        "workRights": {
            "required": True, "maxDailyHours": 8, "maxWeeklyHours": 40,
            "nightShiftAllowed": False, "overtimeAllowed": False,
        }
    }
    return SimpleNamespace(id=10, rules_version=3, rules_config={"compliance": compliance}, **overrides)


def _company(**overrides):
    values = {"id": 20, "blacklist": False, "coop_status": "ACTIVE"}
    values.update(overrides)
    return SimpleNamespace(**values)


def _position(**overrides):
    values = {
        "id": 30, "batch_id": 10, "work_content": "参与软件开发与测试",
        "work_address": "校企合作园区", "work_location": None,
        "daily_hours": 8, "weekly_hours": 40, "shift_type": "DAY",
        "night_shift": False, "overtime_allowed": False, "rest_days_per_week": 2,
        "remuneration_type": "MONTHLY", "remuneration_amount": 3000,
        "remuneration_cycle": "MONTHLY", "accommodation_provided": False,
        "meal_provided": True, "hazardous_flag": False, "special_equipment": None,
        "prohibited_reason": None, "headcount": 3, "allocated_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("field", ["night_shift", "hazardous_flag"])
def test_unknown_sensitive_boolean_blocks_publish(field):
    result = evaluate_position_publishability(
        _position(**{field: None}), _company(), _batch())
    assert not result["passed"]
    assert any(x["field"] in ("nightShift", "hazardousFlag") for x in result["unknowns"])


@pytest.mark.parametrize(("field", "value", "code"), [
    ("daily_hours", 9, "DAILY_HOURS_EXCEEDED"),
    ("weekly_hours", 41, "WEEKLY_HOURS_EXCEEDED"),
])
def test_hours_above_rule_block_publish(field, value, code):
    result = evaluate_position_publishability(
        _position(**{field: value}), _company(), _batch())
    assert any(x["code"] == code for x in result["blockers"])


def test_minor_night_shift_is_blocked():
    student = SimpleNamespace(birth_date=date(datetime.utcnow().year - 17, 1, 1))
    batch = _batch()
    batch.rules_config["compliance"]["workRights"]["nightShiftAllowed"] = True
    result = evaluate_position_publishability(
        _position(night_shift=True), _company(), batch, student=student)
    assert any(x["code"] == "MINOR_NIGHT_SHIFT" for x in result["blockers"])


def test_blacklisted_company_and_missing_content_block_publish():
    result = evaluate_position_publishability(
        _position(work_content=""), _company(blacklist=True), _batch())
    codes = {x["code"] for x in result["blockers"] + result["unknowns"]}
    assert {"COMPANY_BLACKLIST", "REQUIRED_UNKNOWN"} <= codes


def test_complete_position_is_publishable_and_reports_rule_version():
    result = evaluate_position_publishability(_position(), _company(), _batch())
    assert result["passed"]
    assert result["ruleVersion"] == "batch-10-rv3"


def test_sensitive_booleans_preserve_unknown_in_create_contract():
    body = PositionCreate(
        companyId="20", title="软件测试实习生", workContent="执行功能测试",
        nightShift=None, overtimeAllowed=None, hazardousFlag=None,
    )
    assert body.nightShift is None
    assert body.overtimeAllowed is None
    assert body.hazardousFlag is None


def test_position_update_requires_expected_version():
    with pytest.raises(ValidationError):
        PositionUpdate(title="已被并发修改")


def test_old_import_template_is_rejected_by_contract():
    with pytest.raises(ValidationError):
        PositionImport(templateVersion="POSITION_IMPORT_V1", rows=[])


def test_birth_date_is_derived_from_encrypted_resident_id():
    encrypted = encrypt_sensitive("430102200001010011", "id_card")
    assert _student_birth_date(SimpleNamespace(id_card_encrypted=encrypted)) == date(2000, 1, 1)


@pytest.mark.parametrize("stored", [None, "43010220000101001X", "430102200013010011"])
def test_unknown_or_malformed_resident_id_stays_fail_closed(stored):
    assert _student_birth_date(SimpleNamespace(id_card_encrypted=stored)) is None


def test_resident_id_decryption_failure_stays_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "app.modules.internship.services.internship_compliance_service.decrypt_sensitive",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("ciphertext corrupt")),
    )
    assert _student_birth_date(SimpleNamespace(id_card_encrypted="gAAAAinvalid")) is None


def test_adult_boundary_uses_exact_calendar_date_including_leap_day():
    assert not _is_adult(date(2008, 9, 1), today=date(2026, 8, 31))
    assert _is_adult(date(2008, 9, 1), today=date(2026, 9, 1))
    assert _is_adult(date(2008, 2, 29), today=date(2026, 2, 28))
