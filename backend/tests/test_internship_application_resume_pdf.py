"""Production contracts for enterprise-owned immutable internship resume PDF delivery."""
from __future__ import annotations

import inspect
from datetime import datetime

from fastapi.routing import APIRoute

from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.modules.internship.routers import internship_enterprise_portal as portal
from app.modules.internship.services import internship_application_material_snapshot_service as snapshot_svc
from app.modules.internship.services import internship_application_resume_pdf_service as pdf_svc
from app.modules.internship.services import internship_enterprise_application_decision_service as decision_svc


def _snapshot() -> InternshipApplicationMaterialSnapshot:
    return InternshipApplicationMaterialSnapshot(
        id=991,
        tenant_id=1,
        volunteer_group_id=88,
        student_id=77,
        campaign_id=66,
        batch_id=55,
        submission_version=3,
        profile_version=4,
        profile_snapshot_json={
            "profile": {
                "headline": "智能制造实习生",
                "selfIntro": "熟悉 CAD 与设备点检。",
                "strengths": "安全意识强",
                "skillTags": ["CAD", "设备点检"],
                "availableFrom": "2026-09-01",
                "expectedLocations": ["长沙"],
            },
            "items": [
                {
                    "itemType": "PROJECT",
                    "title": "自动化产线项目",
                    "description": "负责设备点检清单与装配记录。",
                    "organization": "智能制造学院",
                    "verificationStatus": "VERIFIED",
                }
            ],
        },
        school_fact_snapshot_json={
            "realName": "张三",
            "studentNo": "20250001",
            "collegeName": "智能制造学院",
            "majorName": "机械制造及自动化",
            "grade": "2025级",
            "className": "机制2501",
        },
        attachment_file_ids_json=[],
        material_policy_snapshot_json={},
        consent_version="INTERNSHIP_APPLICATION_PRIVACY_V1",
        consent_at=datetime(2026, 8, 15, 10, 0, 0),
        contact_sharing_policy={"mode": "MASKED_ONLY", "sharePhone": True, "shareEmail": True},
        snapshot_hash="a" * 64,
    )


def test_resume_pdf_renderer_emits_real_pdf_from_frozen_snapshot_only():
    data = pdf_svc.render_snapshot_profile_pdf(_snapshot())
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
    source = inspect.getsource(pdf_svc.render_snapshot_profile_pdf)
    for forbidden in ("contact_value", "phone", "email", "applicationStatement", "positionId", "companyId"):
        assert forbidden not in source


def test_enterprise_resume_pdf_authorizes_application_then_locks_exact_snapshot_before_generation():
    source = inspect.getsource(pdf_svc.resolve_enterprise_resume_pdf_in_tx)
    ownership_at = source.index("decision_svc._owned_application_in_tx")
    snapshot_at = source.index("select(InternshipApplicationMaterialSnapshot)")
    ensure_at = source.index("ensure_snapshot_profile_pdf_in_tx")
    assert ownership_at < snapshot_at < ensure_at
    assert "application.material_snapshot_id" in source
    assert "context.campaign_id" in source
    assert "application.student_id" in source
    assert ".with_for_update()" in source


def test_enterprise_applicant_list_minimizes_student_identifiers_before_detail_access():
    source = inspect.getsource(decision_svc.list_owned_applications_in_tx)
    for forbidden in ('"studentId"', '"studentNo"', '"className"'):
        assert forbidden not in source
    for required in ('"realName"', '"collegeName"', '"majorName"', '"grade"'):
        assert required in source
    assert '"applicationId"' in source
    assert '"materialSnapshotId"' in source


def test_enterprise_applicant_snapshot_and_pdf_reads_are_not_enterprise_decision_window_gated():
    read_sources = (
        inspect.getsource(decision_svc.list_owned_applications_in_tx),
        inspect.getsource(decision_svc.material_detail_in_tx),
        inspect.getsource(pdf_svc.resolve_enterprise_resume_pdf_in_tx),
    )
    for source in read_sources:
        assert "assert_campaign_operation_window" not in source
        assert '"ENTERPRISE_DECISION"' not in source
    write_source = inspect.getsource(decision_svc.set_decision_in_tx)
    assert "_assert_decision_write_window" in write_source


def test_generated_pdf_is_private_highly_sensitive_and_bound_to_exact_snapshot():
    source = inspect.getsource(pdf_svc.ensure_snapshot_profile_pdf_in_tx)
    assert 'PDF_BIZ_TYPE = "INTERNSHIP_APPLICATION_PROFILE_PDF"' in inspect.getsource(pdf_svc)
    assert 'relation_type=PDF_RELATION_TYPE' in source
    assert 'subject_type="BUSINESS_OBJECT"' in source
    assert 'biz_id=str(snapshot.id)' in source
    assert 'visibility="PRIVATE"' in source
    assert 'security_level="HIGHLY_SENSITIVE"' in source
    assert "snapshot.generated_profile_pdf_file_id = file_id" in source
    assert "db.flush()" in source


def test_resume_pdf_generic_file_resolver_is_fail_closed():
    assert pdf_svc._deny_generic_resume_pdf_access(None, None, [], {}, "download") is False
    source = inspect.getsource(pdf_svc)
    assert "@register_file_resolver(PDF_BIZ_TYPE)" in source


def test_existing_pdf_pointer_requires_matching_file_and_binding_before_reuse():
    source = inspect.getsource(pdf_svc._existing_bound_pdf_in_tx)
    assert "FileObject.id == int(snapshot.generated_profile_pdf_file_id)" in source
    assert "FileObject.biz_type == PDF_BIZ_TYPE" in source
    assert "FileObject.biz_id == str(snapshot.id)" in source
    assert "FileBinding.relation_type == PDF_RELATION_TYPE" in source
    assert 'FileBinding.status == "ACTIVE"' in source
    assert "is_downloadable_status" in source
    assert 'str(row.mime_type or "").lower() != "application/pdf"' in source


def test_snapshot_public_contract_never_exposes_internal_generated_file_id():
    public = snapshot_svc.snapshot_public_dict(_snapshot())
    assert "generatedProfilePdfFileId" not in public
    assert "generated_profile_pdf_file_id" not in public


def test_enterprise_router_exposes_only_owned_application_pdf_route_with_business_permission():
    routes = [route for route in portal.router.routes if isinstance(route, APIRoute)]
    match = [route for route in routes if route.path.endswith("/applications/{application_id}/resume-pdf")]
    assert len(match) == 1
    assert match[0].methods == {"GET"}
    source = inspect.getsource(portal.application_resume_pdf)
    assert 'require_permission("internship.application.view")' in inspect.getsource(portal)
    assert "resolve_recruitment_context" in source
    assert "resume_pdf_svc.resolve_enterprise_resume_pdf_in_tx" in source
    assert "validated_local_file_response" in source
    assert "inline=True" in source
    assert 'audit_action="INTERNSHIP_ENTERPRISE_RESUME_PDF_VIEW"' in source
    assert "file_id" not in inspect.signature(portal.application_resume_pdf).parameters
