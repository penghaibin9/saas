"""学院岗位名称不能在导入和实施推荐中变成全校领导身份。"""
import pytest

from app.core.exceptions import AppException
from app.services.saas_role_templates import role_catalog, role_codes_from_row, resolve_role_code
from app.services.system_implementation_service import _role_suggestions


@pytest.mark.parametrize("name", ["院领导", "校院领导"])
def test_ambiguous_leader_alias_requires_explicit_college_identity(name):
    with pytest.raises(AppException, match="学院范围"):
        resolve_role_code(name)


@pytest.mark.parametrize("field", ["position", "positionName", "roleName"])
@pytest.mark.parametrize("position", ["院领导", "信息学院领导", "副院长"])
def test_explicit_school_code_cannot_override_college_position(field, position):
    with pytest.raises(AppException, match="学院身份"):
        role_codes_from_row({"roleCodes": ["LEADER"], field: position, "scopeType": "COLLEGE", "scopeRef": "信息学院"})


def test_school_leader_and_explicit_college_management_keep_existing_contracts():
    assert role_codes_from_row({"roleCodes": "校领导"}) == ["LEADER"]
    assert role_codes_from_row({"roleCodes": "LEADER", "positionName": "校领导"}) == ["LEADER"]
    assert role_codes_from_row({"roleCodes": "COLLEGE_ADMIN", "positionName": "院领导"}) == ["COLLEGE_ADMIN"]
    leader = next(row for row in role_catalog()["items"] if row["roleCode"] == "LEADER")
    assert leader["roleName"] == "校领导"
    assert leader["defaultScope"] == "SCHOOL"
    assert _role_suggestions("院领导", "信息学院") == []
    assert _role_suggestions("院领导", "校领导办公室") == []
    assert _role_suggestions("院长", "校领导办公室") == []
    assert _role_suggestions("院领导", "教务处") == []
    assert _role_suggestions("院领导", "学工处") == []
    assert _role_suggestions("学院教务员", "信息学院") == ["COLLEGE_ADMIN"]
    assert _role_suggestions("校领导", "学校") == ["LEADER"]


@pytest.mark.parametrize("scope", ["COLLEGE", "MAJOR", "CLASS", "STUDENT", "ADVISOR"])
def test_school_leader_cannot_claim_an_imported_narrower_scope(scope):
    with pytest.raises(AppException, match="对应范围的身份"):
        role_codes_from_row({"roleCodes": ["LEADER"], "scopeType": scope, "scopeRef": "1"})
    assert role_codes_from_row({"roleCodes": ["COLLEGE_ADMIN", "LEADER"], "scopeType": scope, "scopeRef": "1"}) == ["COLLEGE_ADMIN", "LEADER"]
