"""上线阻断项的轻量契约回归；数据库并发集成测试另由 MySQL 套件覆盖。"""
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.permissions import has_permission
from app.modules.internship.schemas.internship_student import (
    AssignPositionRequest, StudentStatusRequest,
)


ROOT = Path(__file__).parents[1] / "app"


def test_assignment_requires_record_expected_version():
    with pytest.raises(ValidationError):
        AssignPositionRequest(positionId="1")
    assert AssignPositionRequest(positionId="1", expectedVersion=0).expectedVersion == 0


def test_regular_status_contract_has_no_archive_action():
    with pytest.raises(ValidationError):
        StudentStatusRequest(action="ARCHIVE")
    assert StudentStatusRequest(action="ASSESS").action == "ASSESS"


def test_mobile_internship_routes_use_module_guarded_subrouters():
    source = (ROOT / "api/v1/mobile.py").read_text(encoding="utf-8-sig")
    assert 'dependencies=[Depends(require_module("internship"))]' in source
    assert '@router.get("/internship' not in source
    assert '@router.post("/internship' not in source
    assert '@router.get("/teacher/internship' not in source
    assert '@router.post("/teacher/internship' not in source


def test_staff_consent_confirmation_route_removed():
    source = (ROOT / "modules/internship/routers/internship_compliance.py").read_text(
        encoding="utf-8")
    assert '"/consents/{iid}/confirm"' not in source
    mobile = (ROOT / "api/v1/mobile.py").read_text(encoding="utf-8-sig")
    assert '"/consents/{consent_id}/confirm"' in mobile


def test_archive_force_and_revoke_are_not_mentor_permissions():
    mentor = {"currentRoleCode": "INTERN_MENTOR", "userType": "TEACHER"}
    assert has_permission(mentor, "internship.archive.view")
    assert not has_permission(mentor, "internship.archive.execute")
    assert not has_permission(mentor, "internship.archive.force")
    assert not has_permission(mentor, "internship.archive.revoke")
