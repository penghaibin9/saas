from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.services import affairs_funding_service as service
from app.services.message_action_registry import resolve_route, validate_action


def project(*, amount=None, condition_json="{}"):
    return SimpleNamespace(amount=amount, condition_json=condition_json)


def test_fixed_project_amount_is_suggested_and_enforced():
    item = project(amount=Decimal("3200.00"))
    policy = service._amount_policy(item)
    assert policy == {
        "mode": "FIXED", "fixedAmount": "3200.00", "suggestedAmount": "3200.00",
        "source": "PROJECT_STANDARD",
    }
    assert service._validated_amount(item, None) == Decimal("3200.00")
    with pytest.raises(AppException):
        service._validated_amount(item, "3199")


def test_range_project_amount_defaults_and_rejects_out_of_range():
    item = project(condition_json='{"amountPolicy":{"mode":"RANGE","minAmount":1000,"maxAmount":3000,"suggestedAmount":2000}}')
    policy = service._amount_policy(item)
    assert policy["mode"] == "RANGE"
    assert service._validated_amount(item, None) == Decimal("2000.00")
    assert service._validated_amount(item, "2500") == Decimal("2500.00")
    with pytest.raises(AppException):
        service._validated_amount(item, "3500")


def test_material_notice_action_is_registered_for_all_four_clients():
    key, params = validate_action(
        "student.affairs.material", {"materialRequirementId": "88", "ignored": "drop"}
    )
    assert key == "student.affairs.material"
    assert params == {"materialRequirementId": "88"}
    for client in ("pc", "studentPc", "studentMini", "teacherMini"):
        assert resolve_route(key, client=client)["ok"] is True
