from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("scope,allowed_code", [
    ("PSY_STUDENT", "studentAffairs.risk.psyDetail.view"),
    ("PSY_STUDENT", "studentAffairs.archive.psySensitive"),
    ("AID_RESTRICTED", "studentAffairs.aid.sensitiveView"),
])
def test_sensitive_material_content_needs_separate_permission_and_student_scope(monkeypatch, scope, allowed_code):
    from app.modules.student_affairs.services import affairs_material_center_service as center
    from app.core import permissions
    row = SimpleNamespace(material_scope=scope, student_id=1)
    monkeypatch.setattr(center, "_staff_can_enumerate", lambda db, requirement, user: requirement.student_id == 1)
    monkeypatch.setattr(permissions, "get_base_permission_patterns", lambda user: user.get("granted", set()))
    assert not center._staff_can_read_content(None, row, {"granted": {"studentAffairs.*"}})
    assert center._staff_can_read_content(None, row, {"granted": {allowed_code}})
    row.student_id = 2
    assert not center._staff_can_read_content(None, row, {"granted": {allowed_code}})
