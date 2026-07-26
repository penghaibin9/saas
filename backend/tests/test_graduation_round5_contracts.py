"""毕业设计四端收口合同测试（不依赖 mock 业务数据）。"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.graduation.schemas.graduation_defense_score import (
    DefenseAbsenceRequest,
    DefenseScoreEntryRequest,
)
from app.modules.graduation.services.graduation_audit_consistency import _db_id
from app.modules.graduation.services.graduation_contract_bridge import _normalize_members

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_defense_score_dto_contains_real_score_contract():
    row = DefenseScoreEntryRequest(
        gdStudentId="10", judgeName="张老师", judgeMentorId="7", score=88,
        comment="答辩过程完整", absent=False,
    )
    assert row.score == 88
    assert row.judgeMentorId == "7"
    absent = DefenseAbsenceRequest(
        gdStudentId="10", judgeName="李老师", expertId="9", absentReason="临时公务缺席",
    )
    assert absent.expertId == "9"
    with pytest.raises(ValidationError):
        DefenseScoreEntryRequest(
            gdStudentId="10", judgeName="张老师", score=90, absent=True,
            absentReason="缺席却又有分数",
        )


def test_audit_db_user_id_normalizes_prefixed_ids():
    assert _db_id("db-123") == 123
    assert _db_id("456") == 456
    assert _db_id("unknown") is None


def test_defense_member_contract_keeps_details_and_names():
    payload = _normalize_members({
        "members": [
            {"mentorId": 1, "teacherNo": "T001", "name": "张老师"},
            "李老师",
        ]
    })
    assert payload["members"] == ["张老师", "李老师"]
    assert payload["memberNames"] == ["张老师", "李老师"]
    assert payload["memberDetails"][0]["mentorId"] == 1


def test_sensitive_routes_require_batch_and_precede_legacy_routes():
    routes = text("backend/app/api/v1/route_registration.py")
    assert "graduation_sensitive_router.router" in routes
    assert "graduation_archive_sensitive_router.router" in routes
    assert routes.index("graduation_sensitive_router.router") < routes.index("graduation, graduation_batch")
    sensitive = text("backend/app/modules/graduation/routers/graduation_sensitive_router.py")
    for endpoint in (
        '"/gd-grades/{gd_student_id}"',
        '"/gd-defense-scores/{gd_student_id}/confirm"',
        '"/gd-defense-scores/{gd_student_id}/second-defense"',
        '"/gd-reviews/assign"',
    ):
        assert endpoint in sensitive
    assert sensitive.count("batchId: int = Query(..., ge=1)") >= 15


def test_pc_grade_api_never_sends_unbound_final_and_always_sends_batch():
    api = text("frontend/src/modules/graduation/api/graduation-defense-grade.api.js")
    assert "function batchParams" in api
    assert "params: batchParams()" in api
    assert "gdFinalId: null" not in api
    assert "reviewerMentorId" in api


def test_archive_manifest_uses_file_sha_and_signed_preview():
    archive = text("backend/app/modules/graduation/services/graduation_archive_consistency.py")
    assert "FileObject" in archive
    assert '"sha256": row.sha256' in archive
    assert '"confirmationHash": sign.content_hash' in archive
    assert "previewToken" in archive
    assert "hmac.compare_digest" in archive
    assert "with_for_update()" in archive
    api = text("frontend/src/modules/graduation/api/graduation-risk-archive.api.js")
    assert "previewToken" in api
    assert "batch-generate/preview" in api
    assert "batch-file/preview" in api


def test_teacher_mobile_uses_stable_ids_not_same_name_blockade():
    permissions = text("backend/app/core/mobile_graduation_permissions.py")
    bridge = text("backend/app/modules/graduation/services/graduation_mobile_stable_bridge.py")
    assert "same_name_count" not in permissions
    assert "GraduationStudent.mentor_id == mentor.id" in bridge
    assert "GraduationReview.reviewer_mentor_id == mentor.id" in bridge
    assert "judge_identity" in bridge
    assert "advisor_name ==" not in bridge


def test_topic_change_and_material_submissions_are_serialized():
    topic = text("backend/app/modules/graduation/services/graduation_topic_change_consistency.py")
    consistency = text("backend/app/modules/graduation/services/graduation_consistency_install.py")
    assert topic.count("with_for_update()") >= 4
    assert "install_topic_change_consistency()" in consistency
    assert "GraduationProposal" in consistency and "with_for_update()" in consistency
    assert "GraduationFinal" in consistency and "active_key=f\"pending:{student.id}\"" in consistency


def test_get_grade_remains_read_only():
    service = text("backend/app/modules/graduation/services/graduation_grade_service.py")
    start = service.index("def get_grade(")
    end = service.index("\ndef calculate_grade(", start)
    body = service[start:end]
    assert "db.commit()" not in body
    assert "db.add(" not in body
    assert '"exists": False' in body


def test_teacher_topic_page_does_not_turn_errors_into_empty_lists():
    page = text("miniapp/src/pages/teacher/graduation-topics/index.vue")
    assert "Promise.allSettled" in page
    assert "catch(() => [])" not in page
    assert "choiceError" in page and "changeError" in page
