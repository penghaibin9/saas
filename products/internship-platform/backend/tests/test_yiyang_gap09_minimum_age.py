"""GAP-09: under-16 placement must remain blocked outside optional rules."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
from test_internship_round3_compliance_unit import _batch, _company, _position


@pytest.mark.parametrize("operation", ["APPLY", "ASSIGN", "ONBOARD", "CONTINUE"])
def test_under_sixteen_cannot_be_placed_even_with_optional_rules_disabled(operation):
    student = SimpleNamespace(birth_date=date(datetime.utcnow().year - 15, 1, 1))
    batch = _batch()
    batch.rules_config["compliance"]["workRights"]["required"] = False
    batch.rules_config["compliance"]["minimumAge"] = {"required": False, "severity": "WARN"}
    result = evaluate_position_publishability(_position(), _company(), batch, student, operation=operation)
    assert not result["passed"]
    assert any(x["code"] == "minimumAge" for x in result["blockers"] + result["unknowns"])


from app.core.exceptions import AppException
from app.core.field_crypto import encrypt_sensitive
from app.modules.internship.services.internship_student_age import (
    minimum_age_item, student_age_years, student_birth_date, assert_exemption_allowed,
)
from app.modules.internship.services.internship_consent_service import evaluate_applicability
from app.modules.internship.services.internship_special_filing_service import evaluate_triggers


def encrypted_student(birth):
    prefix = "430102" + birth.strftime("%Y%m%d") + "001"
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    suffix = "10X98765432"[sum(int(c) * w for c, w in zip(prefix, weights)) % 11]
    return SimpleNamespace(id_card_encrypted=encrypt_sensitive(prefix + suffix, "id_card"))


@pytest.mark.parametrize("birth,status", [
    (date(2010, 10, 3), "REJECTED"),
    (date(2010, 10, 2), "VALID"),
    (date(2009, 10, 2), "VALID"),
    (date(2000, 1, 1), "VALID"),
    (date(2027, 1, 1), "PENDING"),
    (None, "PENDING"),
])
def test_calendar_boundary_and_unknown_birth(birth, status):
    result = minimum_age_item(SimpleNamespace(birth_date=birth), today=date(2026, 10, 2))
    assert result["status"] == status
    assert result["required"] is True and result["severity"] == "BLOCK"
    assert result["exemptible"] is False


@pytest.mark.parametrize("birth,status", [(date(2011, 1, 1), "REJECTED"), (date(2000, 1, 1), "VALID")])
def test_encrypted_master_identity_is_authority_without_pii_in_result(birth, status):
    student = encrypted_student(birth)
    assert student_birth_date(student, today=date(2026, 10, 2)) == birth
    result = minimum_age_item(student, today=date(2026, 10, 2))
    assert result["status"] == status
    assert "id_card" not in str(result) and birth.isoformat() not in str(result)
    assert student.id_card_encrypted not in str(result)


@pytest.mark.parametrize("value", ["bad-ciphertext", "43010220110101001X", "", None])
def test_corrupt_identity_cannot_be_treated_as_adult(value):
    student = SimpleNamespace(id_card_encrypted=value)
    assert minimum_age_item(student)["status"] == "PENDING"
    assert student_age_years(student) is None


def test_future_schedule_does_not_admit_currently_underage_student():
    student = SimpleNamespace(birth_date=date(2010, 10, 3))
    record = SimpleNamespace(intern_start_date=datetime(2026, 11, 1))
    assert minimum_age_item(student, record=record, today=date(2026, 10, 2))["status"] == "REJECTED"


def test_later_birthday_does_not_rewrite_underage_historical_start():
    student = SimpleNamespace(birth_date=date(2010, 9, 15))
    record = SimpleNamespace(intern_start_date=datetime(2026, 9, 1))
    assert minimum_age_item(student, record=record, today=date(2026, 10, 2))["status"] == "REJECTED"


def test_late_joining_student_is_not_judged_on_cohort_start_date():
    student = SimpleNamespace(birth_date=date(2010, 9, 15))
    batch = SimpleNamespace(start_date=datetime(2026, 9, 1))
    assert minimum_age_item(student, batch=batch, today=date(2026, 10, 2))["status"] == "VALID"


@pytest.mark.parametrize("code", ["minimumAge", " MINIMUMAGE ", "MinimumAge"])
def test_age_waiver_is_rejected_before_any_database_write(code):
    from app.modules.internship.services.internship_compliance_service import grant_exemption
    with pytest.raises(AppException, match="不可豁免"):
        grant_exemption({"checkCode": code, "internshipId": "1", "reason": "测试不能放行未成年学生"})
    with pytest.raises(AppException, match="不可豁免"):
        assert_exemption_allowed(code)


def test_other_existing_exemption_policy_is_not_silently_rewritten():
    assert assert_exemption_allowed("advisor") is None


def test_job_publication_without_student_does_not_require_student_identity():
    assert evaluate_position_publishability(_position(), _company(), _batch())["passed"] is True


def test_guardian_and_special_filing_use_encrypted_student_identity():
    today = date.today()
    student = encrypted_student(date(today.year - 17, 1, 1))
    assert evaluate_applicability(student, "GUARDIAN") == (True, "REQUIRED")
    assert ("MINOR", "学生未满18周岁") in evaluate_triggers(_position(), student)
    batch = _batch()
    batch.rules_config["compliance"]["workRights"]["nightShiftAllowed"] = True
    result = evaluate_position_publishability(_position(night_shift=True), _company(), batch, student)
    assert any(x["code"] == "MINOR_NIGHT_SHIFT" for x in result["blockers"])
