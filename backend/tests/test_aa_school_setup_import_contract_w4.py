"""A-W4/A-C5 Course/Program school-setup import contracts."""
from __future__ import annotations

import inspect

import pytest


def _contract():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_import_contract as contract
    return contract


def test_import_types_and_reconciliation_actions_are_frozen_without_second_framework():
    contract = _contract()
    assert contract.ACADEMIC_COURSE_CATALOG_IMPORT == "ACADEMIC_COURSE_CATALOG"
    assert contract.ACADEMIC_PROGRAM_IMPORT == "ACADEMIC_PROGRAM"
    assert contract.RECONCILIATION_ACTIONS == {
        "CREATE", "REUSE", "CONFLICT", "REJECT",
    }
    source = inspect.getsource(contract)
    assert "ImportJob(" not in source
    assert "FileObject(" not in source
    assert "get_sessionmaker" not in source
    assert "db.commit" not in source


def test_course_template_requires_stable_identity_and_domain_fields():
    contract = _contract()
    assert contract.COURSE_TEMPLATE_VERSION == "course-catalog-v1"
    assert contract.COURSE_HEADER_MAP["课程代码"] == "courseCode"
    assert contract.COURSE_HEADER_MAP["版本"] == "version"
    assert {"courseCode", "version", "courseName", "category", "nature", "credit", "examMode"} <= (
        contract.COURSE_REQUIRED_FIELDS
    )
    missing = contract.missing_required_fields(
        {"courseCode": "CS101", "version": 1, "courseName": "Python"},
        contract.COURSE_REQUIRED_FIELDS,
    )
    assert "category" in missing
    assert "nature" in missing
    assert "credit" in missing
    assert "examMode" in missing


def test_course_business_key_is_code_plus_version_never_name():
    contract = _contract()
    first = contract.course_business_key({"courseCode": " cs101 ", "version": "2", "courseName": "旧名称"})
    renamed = contract.course_business_key({"courseCode": "CS101", "version": 2, "courseName": "新名称"})
    another_code = contract.course_business_key({"courseCode": "CS102", "version": 2, "courseName": "旧名称"})

    assert first == renamed
    assert first.text() == "CS101@v2"
    assert another_code != first


@pytest.mark.parametrize("version", [None, "", 0, -1, "abc"])
def test_course_business_key_rejects_missing_or_invalid_version(version):
    with pytest.raises(ValueError, match="version"):
        _contract().course_business_key({"courseCode": "CS101", "version": version, "courseName": "Python"})


def test_program_contract_separates_version_identity_from_binding_relationship():
    contract = _contract()
    assert contract.PROGRAM_TEMPLATE_VERSION == "program-v1"
    assert {"programName", "programVersion", "majorId", "gradeYear", "totalCredits"} <= (
        contract.PROGRAM_MAIN_REQUIRED_FIELDS
    )
    assert {"courseCode", "courseVersion", "openTermNo", "formationMode"} <= (
        contract.PROGRAM_COURSE_REQUIRED_FIELDS
    )
    assert {"programVersion", "majorId", "gradeYear", "bindingScope"} <= (
        contract.PROGRAM_BINDING_REQUIRED_FIELDS
    )

    version_key = contract.program_version_key({
        "majorId": 10, "gradeYear": "2026", "programVersion": 3,
    })
    major_binding = contract.program_binding_key({
        "majorId": 10, "gradeYear": "2026", "programVersion": 3,
        "bindingScope": "MAJOR_GRADE", "classId": "",
    })
    class_binding = contract.program_binding_key({
        "majorId": 10, "gradeYear": "2026", "programVersion": 3,
        "bindingScope": "CLASS", "classId": 77,
    })

    assert version_key.text() == "MAJOR:10:GRADE:2026:v3"
    assert major_binding.text() == "MAJOR:10:GRADE:2026:MAJOR_GRADE"
    assert class_binding.text() == "MAJOR:10:GRADE:2026:CLASS:77"
    assert major_binding != class_binding


def test_program_binding_scope_is_fail_closed():
    contract = _contract()
    with pytest.raises(ValueError, match="classId"):
        contract.program_binding_key({
            "majorId": 10, "gradeYear": "2026", "programVersion": 1,
            "bindingScope": "CLASS", "classId": "",
        })
    with pytest.raises(ValueError, match="classId must be empty"):
        contract.program_binding_key({
            "majorId": 10, "gradeYear": "2026", "programVersion": 1,
            "bindingScope": "MAJOR_GRADE", "classId": 77,
        })
    with pytest.raises(ValueError, match="unsupported bindingScope"):
        contract.program_binding_key({
            "majorId": 10, "gradeYear": "2026", "programVersion": 1,
            "bindingScope": "NAME_MATCH", "classId": "",
        })


def test_program_course_reference_uses_versioned_course_and_explicit_formation():
    contract = _contract()
    result = contract.program_course_reference({
        "majorId": 10,
        "gradeYear": "2026",
        "programVersion": 2,
        "courseCode": " cs101 ",
        "courseVersion": "3",
        "openTermNo": 4,
        "formationMode": "selectable",
        "creditSnapshot": "3.5",
        "courseName": "名称不得参与 identity",
        "nature": "PUBLIC_ELECTIVE",
    })
    assert result["programKey"] == "MAJOR:10:GRADE:2026:v2"
    assert result["courseKey"] == "CS101@v3"
    assert result["formationMode"] == "SELECTABLE"
    assert result["openTermNo"] == 4
    assert str(result["creditSnapshot"]) == "3.5"


def test_program_course_reference_never_infers_formation_from_nature_or_name():
    contract = _contract()
    with pytest.raises(ValueError, match="formationMode"):
        contract.program_course_reference({
            "majorId": 10,
            "gradeYear": "2026",
            "programVersion": 1,
            "courseCode": "PE101",
            "courseVersion": 1,
            "openTermNo": 1,
            "courseName": "公共选修",
            "nature": "PUBLIC_ELECTIVE",
        })


def test_reconciliation_action_is_exact_and_fail_closed():
    contract = _contract()
    for action in ("CREATE", "reuse", "CONFLICT", "reject"):
        assert contract.reconciliation_action(action) == action.upper()
    with pytest.raises(ValueError, match="unsupported reconciliation action"):
        contract.reconciliation_action("OVERWRITE_BY_NAME")
