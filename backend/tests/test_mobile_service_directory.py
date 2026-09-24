"""服务目录合同测试；不写业务数据，不以目录可见冒充流程通过。"""
import json
from pathlib import Path

import pytest

from app.services import mobile_service_directory as directory


STUDENT = {"userId": "17", "userType": "STUDENT", "clientType": "STUDENT_MINI"}


@pytest.fixture
def school(monkeypatch):
    monkeypatch.setattr(directory, "current_tenant_id", lambda: 7)
    monkeypatch.setattr(directory, "module_access_state", lambda tenant, module: {"allowed": True})


def test_complete_directory_is_not_limited_by_freshman_stage(school):
    result = directory.service_directory({**STUDENT, "stage": "ADMITTED"})
    assert len(result["categories"]) == 4
    assert len(result["items"]) > 8
    assert {x["cat"] for x in result["items"]} == {x[0] for x in directory.DIRECTORY}
    assert any(x["name"] == "我的成绩" for x in result["items"])


def test_only_real_student_routes_are_offered(school):
    manifest = json.loads((Path(__file__).resolve().parents[2] / "miniapp/src/pages.json").read_text(encoding="utf-8"))
    paths = {"/" + p["path"] for p in manifest["pages"]}
    for package in manifest["subPackages"]:
        paths.update(f"/{package['root']}/{p['path']}" for p in package["pages"])
    result = directory.service_directory(STUDENT)
    for item in result["items"] + result["categories"]:
        target = item["action"]["target"]
        assert target["path"] in paths
        assert target["path"].startswith(("/pages/student/", "/pages/student-internship/"))
    ids = [x["id"] for x in result["items"]]
    assert len(ids) == len(set(ids))


def test_school_module_denial_keeps_explanation_not_action_or_child_menu(school, monkeypatch):
    monkeypatch.setattr(directory, "module_access_state", lambda tenant, module: {"allowed": module != "internship", "reasonCode": "NOT_ENTITLED"})
    result = directory.service_directory(STUDENT)
    category = next(c for c in result["categories"] if c["key"] == "internship")
    assert category["reason"] == "学校尚未开通此模块"
    assert category["action"]["target"] is None
    assert category["action"]["allowedActions"] == []
    assert not any(x["cat"] == "internship" for x in result["items"])


def test_authority_failure_does_not_turn_into_available_or_empty_directory(school, monkeypatch):
    def fail(*args):
        raise RuntimeError("authority unavailable")
    monkeypatch.setattr(directory, "module_access_state", fail)
    with pytest.raises(RuntimeError):
        directory.service_directory(STUDENT)


def test_trusted_school_context_not_user_parameter_selects_authorization(school, monkeypatch):
    tenants = []
    monkeypatch.setattr(directory, "module_access_state", lambda tenant, module: tenants.append(tenant) or {"allowed": True})
    directory.service_directory({**STUDENT, "tenantId": "999"})
    assert tenants == [7] * 4


@pytest.mark.parametrize("user", [
    {}, {**STUDENT, "userType": "TEACHER"}, {**STUDENT, "clientType": "TEACHER_MINI"},
])
def test_other_identities_cannot_read_student_directory(school, user):
    with pytest.raises(Exception) as error:
        directory.service_directory(user)
    assert "学生移动端" in str(error.value)


def test_missing_school_fails_closed(school, monkeypatch):
    monkeypatch.setattr(directory, "current_tenant_id", lambda: None)
    with pytest.raises(Exception) as error:
        directory.service_directory(STUDENT)
    assert "学校上下文" in str(error.value)
