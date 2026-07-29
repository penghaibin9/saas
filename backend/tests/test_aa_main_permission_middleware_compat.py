"""教务长期分支不得回退主线权限与请求上下文能力。"""
from pathlib import Path

from app.core.context import (
    get_current_internship_batch_id,
    set_current_internship_batch_id,
)


ROOT = Path(__file__).resolve().parents[1]
PERMISSIONS = (ROOT / "app/core/permissions.py").read_text(encoding="utf-8")
MIDDLEWARE = (ROOT / "app/middleware/context.py").read_text(encoding="utf-8")


def test_current_main_graduation_permission_additions_are_preserved():
    for token in (
        '"graduationDesign.topic.assign", "graduationDesign.topic.review"',
        '"graduationDesign.defense.view", "graduationDesign.defense.groupManage"',
        '"graduationDesign.grade.view", "graduationDesign.grade.review"',
        '"graduationDesign.defense.view", "graduationDesign.risk.view"',
    ):
        assert token in PERMISSIONS


def test_current_main_internship_signature_permission_is_preserved():
    assert '"internship.agreement.view", "internship.agreement.manage", "internship.agreement.sign"' in PERMISSIONS


def test_academic_teacher_remains_explicit_and_fail_closed():
    assert '"ACADEMIC_TEACHER": {' in PERMISSIONS
    assert '"ACADEMIC_TEACHER": {"academicAffairs.*"' not in PERMISSIONS
    for token in (
        '"academicAffairs.grade.input"',
        '"academicAffairs.grade.submit"',
        '"academicAffairs.schedule.teacherConfirm"',
        '"academicAffairs.selection.rosterView"',
        '"academicAffairs.evaluation.view"',
    ):
        assert token in PERMISSIONS
    assert "ROLE_PERMISSION_DENY: dict[str, set[str]] = {}" in PERMISSIONS


def test_internship_batch_context_is_preserved_end_to_end():
    previous = get_current_internship_batch_id()
    try:
        set_current_internship_batch_id("batch-compat-17")
        assert get_current_internship_batch_id() == "batch-compat-17"
        set_current_internship_batch_id("")
        assert get_current_internship_batch_id() is None
    finally:
        set_current_internship_batch_id(previous)

    for token in (
        "set_current_internship_batch_id(_resolve_internship_batch_id(request))",
        'request.headers.get("x-internship-batch-id")',
        'path.startswith("/api/v1/mobile/internship")',
        'path.startswith("/api/v1/portal/internship")',
        '"internshipBatchId": _resolve_internship_batch_id(request) or ""',
    ):
        assert token in MIDDLEWARE


def test_middleware_keeps_main_fail_closed_tenant_guards():
    assert "_expired_tenant_readonly_deny(request)" in MIDDLEWARE
    assert "_demo_tenant_readonly_deny(request)" in MIDDLEWARE
    assert '"TENANT_GUARD_UNAVAILABLE"' in MIDDLEWARE
    assert '"MODULE_EXPIRED_READONLY"' in MIDDLEWARE
