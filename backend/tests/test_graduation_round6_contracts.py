"""毕业设计自主审计 Loop 第六轮合同测试。"""
from __future__ import annotations

import importlib
from pathlib import Path

from app.services.xlsx_util import safe_excel_value

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_new_consistency_modules_import_without_cycles():
    for module in (
        "app.modules.graduation.services.graduation_archive_batch_consistency",
        "app.modules.graduation.services.graduation_defense_round_consistency",
        "app.modules.graduation.services.graduation_export_security",
        "app.modules.graduation.services.graduation_grade_appeal_consistency",
        "app.modules.graduation.services.graduation_material_access_consistency",
        "app.modules.graduation.services.graduation_peer_consistency",
        "app.modules.graduation.services.graduation_topic_import_consistency",
    ):
        assert importlib.import_module(module)


def test_runtime_installs_permissions_archive_and_all_state_guards():
    runtime = text("backend/app/modules/graduation/services/graduation_runtime_settings.py")
    for call in (
        "install_graduation_permission_extensions()",
        "install_archive_consistency()",
        "install_archive_batch_consistency()",
        "install_material_access_consistency()",
        "install_topic_import_consistency()",
        "install_graduation_export_security()",
        "install_defense_round_consistency()",
        "install_grade_appeal_consistency()",
        "install_peer_consistency()",
    ):
        assert call in runtime


def test_batch_archive_routes_consume_preview_token_before_dynamic_student_path():
    router = text("backend/app/modules/graduation/routers/graduation_archive_sensitive_router.py")
    assert router.index('"/gd-archives/batch-generate"') < router.index('"/gd-archives/{gd_student_id}"')
    assert router.index('"/gd-archives/batch-file"') < router.index('"/gd-archives/{gd_student_id}"')
    assert "preview_token=_preview_token(body)" in router
    assert "archiveBatchNo" in router
    permissions = text("backend/app/modules/graduation/services/graduation_permission_extensions.py")
    assert '"batch_generate_preview", "batch_file_preview"' in permissions
    assert '"batch_generate", "batch_file"' in permissions


def test_archive_preview_binds_the_final_archive_batch_number():
    service = text("backend/app/modules/graduation/services/graduation_archive_batch_consistency.py")
    api = text("frontend/src/modules/graduation/api/graduation-risk-archive.api.js")
    assert 'snapshot["archiveBatchNo"] = archive_no' in service
    assert "archive.archive_batch_no = archive_no" in service
    assert "preview.archiveBatchNo" in api
    assert "body: { ...body, archiveBatchNo, previewToken }" in api


def test_xlsx_formula_injection_is_neutralized_in_public_and_legacy_exports():
    assert safe_excel_value("=HYPERLINK(\"https://evil.invalid\")").startswith("'")
    assert safe_excel_value(" +SUM(1,2)").startswith("'")
    assert safe_excel_value("normal text") == "normal text"
    assert safe_excel_value(88) == 88
    legacy = text("backend/app/modules/graduation/services/graduation_export_security.py")
    assert "cell.data_type == \"f\"" in legacy
    assert "install_graduation_export_security" in legacy


def test_second_defense_is_exactly_round_two_and_rejects_stale_grade_states():
    service = text("backend/app/modules/graduation/services/graduation_defense_round_consistency.py")
    assert 'grade.status in ("CALCULATED", "REVIEWED", "PUBLISHED")' in service
    assert "any(round_no >= 2 for round_no in rounds)" in service
    assert "round_no=2" in service
    assert '"newRound": 2' in service


def test_grade_appeal_acceptance_performs_full_withdrawal_and_notification():
    service = text("backend/app/modules/graduation/services/graduation_grade_appeal_consistency.py")
    assert 'grade.status = "WITHDRAWN"' in service
    assert "grade.reviewed_at = None" in service
    assert 'student.stage = "DEFENSE"' in service
    assert "emit_message_event" in service
    assert "GRADUATION_DESIGN.GRADE_APPEAL_REVIEWED" in service


def test_peer_review_is_bound_to_approved_final_and_both_student_clients_show_evidence():
    service = text("backend/app/modules/graduation/services/graduation_peer_consistency.py")
    assert 'GraduationFinal.final_type == "定稿"' in service
    assert 'GraduationFinal.status == "APPROVED"' in service
    assert 'assert_student_access(db, target, "peer.assign.target")' in service
    assert 'assert_student_access(db, reviewer, "peer.assign.reviewer")' in service
    assert '"attachmentsList": _final_attachments' in service
    assert "历史互查任务未绑定正式定稿" in service

    mini = text("miniapp/src/pages/student/graduation/index.vue")
    portal = text("student-portal/src/views/graduation/GraduationWorkbenchView.vue")
    for page in (mini, portal):
        assert "finalVersion" in page
        assert "attachmentsList" in page
        assert "taskValid" in page


def test_material_download_is_bound_to_tenant_file_and_explicit_peer_task():
    service = text("backend/app/modules/graduation/services/graduation_material_access_consistency.py")
    assert 'FileObject.tenant_id == _tid()' in service
    assert 'FileObject.biz_type == "GRADUATION_MATERIAL"' in service
    assert "is_downloadable_status" in service
    assert "GraduationPeerReview.gd_final_id == material_id" in service
    assert "GraduationPeerReview.reviewer_gd_student_id == int(current.id)" in service
    assert "该材料不属于本人，也未分配给本人互查" in service
