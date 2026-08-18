"""A-W4/INT/A-C5 Course/Program school-setup import contracts."""
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


def test_program_v2_freezes_all_six_logical_groups_and_required_fields():
    contract = _contract()
    assert contract.PROGRAM_TEMPLATE_VERSION == "program-v2"
    assert contract.PROGRAM_LOGICAL_GROUPS == {
        "MAIN", "COURSE", "CREDIT_REQUIREMENT", "PRACTICE", "GRADUATION", "BINDING",
    }
    assert set(contract.PROGRAM_REQUIRED_FIELDS_BY_GROUP) == contract.PROGRAM_LOGICAL_GROUPS
    assert {"programSeriesKey", "programName", "programVersion", "majorId", "gradeYear", "totalCredits"} <= (
        contract.PROGRAM_MAIN_REQUIRED_FIELDS
    )
    assert {"programSeriesKey", "programVersion", "courseCode", "courseVersion", "openTermNo", "module", "formationMode"} <= (
        contract.PROGRAM_COURSE_REQUIRED_FIELDS
    )
    assert contract.PROGRAM_CREDIT_REQUIREMENT_REQUIRED_FIELDS == {
        "programSeriesKey", "programVersion", "module", "creditTarget",
    }
    assert {"segmentName", "segmentType", "weeks", "credit", "orgMode", "assessmentMode"} <= (
        contract.PROGRAM_PRACTICE_REQUIRED_FIELDS
    )
    assert {"category", "content"} <= contract.PROGRAM_GRADUATION_REQUIRED_FIELDS
    assert {"programSeriesKey", "programVersion", "majorId", "gradeYear", "bindingScope"} <= (
        contract.PROGRAM_BINDING_REQUIRED_FIELDS
    )


def test_program_identity_is_series_plus_version_never_major_grade_or_name():
    contract = _contract()
    first = contract.program_version_key({
        "programSeriesKey": " cs-soft ",
        "programVersion": 3,
        "majorId": 10,
        "gradeYear": "2026",
        "programName": "软件技术A方案",
    })
    renamed_or_rescoped = contract.program_version_key({
        "programSeriesKey": "CS-SOFT",
        "programVersion": 3,
        "majorId": 999,
        "gradeYear": "2030",
        "programName": "名称变化也不能改 identity",
    })
    parallel = contract.program_version_key({
        "programSeriesKey": "CS-SOFT-ALT",
        "programVersion": 3,
        "majorId": 10,
        "gradeYear": "2026",
        "programName": "同专业同年级同版本的合法并行系列",
    })

    assert first == renamed_or_rescoped
    assert first.text() == "SERIES:CS-SOFT:v3"
    assert parallel.text() == "SERIES:CS-SOFT-ALT:v3"
    assert parallel != first


@pytest.mark.parametrize("series_key", [None, "", "   ", "bad key", "中文方案", "*bad", "A" * 65])
def test_program_series_key_is_explicit_bounded_and_fail_closed(series_key):
    with pytest.raises(ValueError, match="programSeriesKey"):
        _contract().program_version_key({
            "programSeriesKey": series_key,
            "programVersion": 1,
            "majorId": 10,
            "gradeYear": "2026",
        })


def test_program_binding_targets_exact_program_version_and_keeps_scope_separate():
    contract = _contract()
    major_binding = contract.program_binding_key({
        "programSeriesKey": "CS-SOFT",
        "programVersion": 3,
        "majorId": 10,
        "gradeYear": "2026",
        "bindingScope": "MAJOR_GRADE",
        "classId": "",
    })
    class_binding = contract.program_binding_key({
        "programSeriesKey": "CS-SOFT",
        "programVersion": 3,
        "majorId": 10,
        "gradeYear": "2026",
        "bindingScope": "CLASS",
        "classId": 77,
    })
    next_version = contract.program_binding_key({
        "programSeriesKey": "CS-SOFT",
        "programVersion": 4,
        "majorId": 10,
        "gradeYear": "2026",
        "bindingScope": "MAJOR_GRADE",
        "classId": "",
    })

    assert major_binding.program.text() == "SERIES:CS-SOFT:v3"
    assert major_binding.text() == "SERIES:CS-SOFT:v3|MAJOR:10:GRADE:2026:MAJOR_GRADE"
    assert class_binding.text() == "SERIES:CS-SOFT:v3|MAJOR:10:GRADE:2026:CLASS:77"
    assert major_binding != class_binding
    assert next_version != major_binding


def test_program_binding_scope_is_fail_closed():
    contract = _contract()
    base = {
        "programSeriesKey": "CS-SOFT",
        "programVersion": 1,
        "majorId": 10,
        "gradeYear": "2026",
    }
    with pytest.raises(ValueError, match="classId"):
        contract.program_binding_key({**base, "bindingScope": "CLASS", "classId": ""})
    with pytest.raises(ValueError, match="classId must be empty"):
        contract.program_binding_key({**base, "bindingScope": "MAJOR_GRADE", "classId": 77})
    with pytest.raises(ValueError, match="unsupported bindingScope"):
        contract.program_binding_key({**base, "bindingScope": "NAME_MATCH", "classId": ""})


def test_program_course_reference_uses_exact_program_course_module_and_explicit_formation():
    contract = _contract()
    result = contract.program_course_reference({
        "programSeriesKey": "CS-SOFT",
        "programVersion": 2,
        "courseCode": " cs101 ",
        "courseVersion": "3",
        "openTermNo": 4,
        "module": "专业核心",
        "formationMode": "selectable",
        "creditSnapshot": "3.5",
        "majorId": 999,
        "gradeYear": "2030",
        "courseName": "名称不得参与 identity",
        "nature": "PUBLIC_ELECTIVE",
    })
    assert result["programKey"] == "SERIES:CS-SOFT:v2"
    assert result["courseKey"] == "CS101@v3"
    assert result["module"] == "专业核心"
    assert result["formationMode"] == "SELECTABLE"
    assert result["openTermNo"] == 4
    assert str(result["creditSnapshot"]) == "3.5"


def test_program_course_reference_requires_module_and_never_infers_formation_from_nature_or_name():
    contract = _contract()
    base = {
        "programSeriesKey": "CS-SOFT",
        "programVersion": 1,
        "courseCode": "PE101",
        "courseVersion": 1,
        "openTermNo": 1,
        "courseName": "公共选修",
        "nature": "PUBLIC_ELECTIVE",
    }
    with pytest.raises(ValueError, match="module"):
        contract.program_course_reference({**base, "formationMode": "SELECTABLE"})
    with pytest.raises(ValueError, match="formationMode"):
        contract.program_course_reference({**base, "module": "公共选修"})


def test_program_child_group_normalizers_use_exact_series_version_key():
    contract = _contract()
    requirement = contract.program_credit_requirement({
        "programSeriesKey": "CS-SOFT", "programVersion": 2,
        "module": "专业核心", "creditTarget": "30.5",
    })
    practice = contract.program_practice_segment({
        "programSeriesKey": "CS-SOFT", "programVersion": 2,
        "segmentName": "岗位实习", "segmentType": "post_internship",
        "openTermNo": 5, "weeks": "16", "credit": "8",
        "orgMode": "distributed", "assessmentMode": "check", "location": "企业",
    })
    graduation = contract.program_graduation_requirement({
        "programSeriesKey": "CS-SOFT", "programVersion": 2,
        "category": "ability", "content": "完成综合项目并形成可审计成果",
    })

    assert requirement == {
        "programKey": "SERIES:CS-SOFT:v2",
        "module": "专业核心",
        "creditTarget": requirement["creditTarget"],
    }
    assert str(requirement["creditTarget"]) == "30.5"
    assert practice["programKey"] == "SERIES:CS-SOFT:v2"
    assert practice["segmentType"] == "POST_INTERNSHIP"
    assert practice["orgMode"] == "DISTRIBUTED"
    assert practice["assessmentMode"] == "CHECK"
    assert graduation == {
        "programKey": "SERIES:CS-SOFT:v2",
        "category": "ABILITY",
        "content": "完成综合项目并形成可审计成果",
    }


def test_reconciliation_action_is_exact_and_fail_closed():
    contract = _contract()
    for action in ("CREATE", "reuse", "CONFLICT", "reject"):
        assert contract.reconciliation_action(action) == action.upper()
    with pytest.raises(ValueError, match="unsupported reconciliation action"):
        contract.reconciliation_action("OVERWRITE_BY_NAME")
