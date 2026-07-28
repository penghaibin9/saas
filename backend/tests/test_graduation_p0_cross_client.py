"""Regression guards for graduation cross-client P0 fixes."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.exceptions import AppException
from app.core.mobile_graduation_permissions import MOBILE_GRADUATION_ENDPOINT_PERMISSIONS
from app.modules.graduation.services.graduation_record_resolver import _one_or_conflict

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_has_single_head_after_graduation_merge():
    cfg = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0142_gd_excellent_delay"]


def test_teacher_mobile_graduation_endpoints_have_explicit_action_permissions():
    expected = {
        "teacher_proposal_review": "graduationDesign.proposal.review",
        "teacher_final_review": "graduationDesign.final.review",
        "teacher_midterm_check": "graduationDesign.midterm.review",
        "teacher_review_submit": "graduationDesign.review.submit",
        "teacher_grade_review": "graduationDesign.grade.review",
        "teacher_graduation_choice_review": "graduationDesign.topic.review",
        "teacher_graduation_guidance_create": "graduationDesign.guidance.create",
        "teacher_graduation_taskbook_issue": "graduationDesign.taskbook.issue",
        "teacher_graduation_taskbook_change": "graduationDesign.taskbook.update",
        "teacher_graduation_defense_score_entry": "graduationDesign.defense.score",
    }
    for endpoint, code in expected.items():
        assert MOBILE_GRADUATION_ENDPOINT_PERMISSIONS.get(endpoint) == code


def test_record_resolver_never_silently_picks_between_two_current_rows():
    with pytest.raises(AppException) as exc:
        _one_or_conflict([object(), object()], "存在多个当前档案")
    assert exc.value.code == "DATA_CONFLICT"


def test_high_risk_routes_are_registered_before_legacy_routers():
    source = (ROOT / "app/api/v1/route_registration.py").read_text(encoding="utf-8")
    assert source.index("api_router.include_router(graduation_p0_guard.router") < source.index(
        "graduation, graduation_batch, graduation_student"
    )
    assert source.index("api_router.include_router(mobile_graduation_guard.router)") < source.index(
        "mobile.router,"
    )
    assert source.index("api_router.include_router(student_portal_graduation_guard.router)") < source.index(
        "api_router.include_router(student_portal_router)"
    )


def test_direct_graduation_qualification_write_is_shadowed():
    source = (ROOT / "app/modules/graduation/routers/graduation_p0_guard.py").read_text(encoding="utf-8")
    assert "毕业设计中心不再直接裁决最终毕业资格" in source
    assert '@router.post("/gd-students/{record_id}/grad-qual"' in source


def test_taskbook_confirmation_uses_versioned_evidence_key():
    source = (ROOT / "app/modules/graduation/services/graduation_taskbook_confirmation_service.py").read_text(
        encoding="utf-8"
    )
    assert 'sign_biz_id = f"{gd_student.id}:v{version}"' in source
    assert "PortalSignRecord.content_hash == content_hash" in source
    assert 'taskbook.status not in ("PENDING_CONFIRM", "CHANGE_PENDING", "CONFIRMED")' in source


def test_student_portal_legacy_service_delegates_to_authoritative_confirmation():
    source = (ROOT / "app/student_portal/services/graduation_service.py").read_text(encoding="utf-8")
    start = source.index("def taskbook_sign(")
    end = source.index("\ndef taskbook_print(", start)
    body = source[start:end]
    assert "confirm_with_evidence(" in body
    assert "confirm_taskbook_in_session" not in body
    assert "create_sign_record_in_session" not in body


def test_guidance_void_locks_row_and_checks_student_scope():
    source = (ROOT / "app/modules/graduation/services/graduation_p0_service.py").read_text(encoding="utf-8")
    assert ".with_for_update()" in source
    assert 'assert_student_access(db, student, "guidance.update")' in source
