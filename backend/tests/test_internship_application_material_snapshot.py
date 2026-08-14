"""E-A01 / A01-8 immutable application material snapshot contracts."""
from __future__ import annotations

from datetime import datetime
import inspect

from sqlalchemy import UniqueConstraint

from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_match import InternshipApplication
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.modules.internship.services import internship_application_material_snapshot_service as service


def test_snapshot_is_append_only_and_contains_required_v3_evidence_fields():
    columns = set(InternshipApplicationMaterialSnapshot.__table__.columns.keys())
    assert InternshipApplicationMaterialSnapshot.__tablename__ == "t_internship_application_material_snapshot"
    assert {
        "tenant_id", "volunteer_group_id", "student_id", "campaign_id", "batch_id",
        "submission_version", "profile_version", "profile_snapshot_json", "school_fact_snapshot_json",
        "attachment_file_ids_json", "material_policy_snapshot_json", "consent_version", "consent_at",
        "contact_sharing_policy", "snapshot_hash", "created_at",
    } <= columns
    assert not {"updated_at", "updated_by", "is_deleted", "version"} & columns
    uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in InternshipApplicationMaterialSnapshot.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("tenant_id", "volunteer_group_id", "submission_version") in uniques


def test_campaign_material_policy_is_stored_but_readiness_is_derived():
    assert "application_material_policy_json" in InternshipRecruitmentCampaign.__table__.columns
    assert "material_ready" not in InternshipRecruitmentCampaign.__table__.columns
    projection = {
        "profile": {"selfIntro": "", "skillTags": ["CAD"]},
        "items": [{"itemType": "PROJECT"}],
    }
    result = service.evaluate_material_readiness(
        projection,
        {"requiredProfileFields": ["selfIntro", "skillTags"], "requiredItemTypes": ["PROJECT", "CERTIFICATE"]},
    )
    assert result["ready"] is False
    assert "profile.selfIntro" in result["missing"]
    assert "itemType.CERTIFICATE" in result["missing"]


def test_snapshot_hash_is_stable_canonical_sha256():
    payload_a = {"b": 2, "a": {"y": 1, "x": [3, 2, 1]}}
    payload_b = {"a": {"x": [3, 2, 1], "y": 1}, "b": 2}
    assert service._snapshot_hash(payload_a) == service._snapshot_hash(payload_b)
    assert len(service._snapshot_hash(payload_a)) == 64


def test_common_snapshot_explicitly_excludes_volunteers_company_position_and_statement():
    source = inspect.getsource(service.create_material_snapshot_in_tx)
    assert '"profileSnapshot": profile_snapshot' in source
    assert '"schoolFactSnapshot": school_facts' in source
    assert '"consentVersion": consent_version' in source
    assert '"contactSharingPolicy": policy' in source
    for forbidden in ("volunteers", "positionId", "companyId", "applicationStatement"):
        assert f'"{forbidden}"' not in source


def test_application_keeps_position_statement_and_snapshot_reference_on_canonical_row():
    columns = set(InternshipApplication.__table__.columns.keys())
    assert "application_statement" in columns
    assert "material_snapshot_id" in columns
    assert InternshipApplication.__tablename__ == "t_internship_application"


def test_contact_policy_defaults_to_no_contact_and_requires_explicit_mode():
    assert service.normalize_contact_sharing_policy(None) == {
        "mode": "NONE", "sharePhone": False, "shareEmail": False,
    }
    explicit = service.normalize_contact_sharing_policy({"mode": "AFTER_ACCEPT_INTENT", "sharePhone": True})
    assert explicit["sharePhone"] is True
    assert explicit["mode"] == "AFTER_ACCEPT_INTENT"
