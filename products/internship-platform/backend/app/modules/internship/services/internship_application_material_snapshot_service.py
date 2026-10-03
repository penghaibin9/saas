"""Immutable application material snapshot service.

The snapshot freezes the common student material once per volunteer-group submission. It never
contains volunteer/company choices, current phone/email values or per-position application
statements, so sharing one snapshot across slots 1/2/3 cannot leak preference order or mutable
contact data to enterprises.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.services.db_service import _as_id

_CONTACT_MODES = frozenset({
    "MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT", "IMMEDIATE",
})
_DEFAULT_ALLOWED_CONTACT_MODES = (
    "MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT",
)
_LEGACY_CONTACT_MODE_ALIASES = {
    "NONE": "MASKED_ONLY",
    "EXPLICIT": "IMMEDIATE",
    "AFTER_SCHOOL_APPROVAL": "AFTER_ACCEPT_INTENT",
}
_DEFAULT_CONTACT_POLICY = {
    "mode": "MASKED_ONLY",
    "sharePhone": True,
    "shareEmail": True,
}
_SECTION_FIELDS = {
    "SELF_INTRO": "selfIntro",
    "SKILLS": "skillTags",
    "AVAILABILITY": "availableFrom",
    "LOCATION_PREFERENCES": "expectedLocations",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _snapshot_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def normalize_contact_sharing_policy(value: dict | None) -> dict:
    policy = dict(_DEFAULT_CONTACT_POLICY)
    if value:
        policy.update({key: value[key] for key in ("mode", "sharePhone", "shareEmail") if key in value})
    raw_mode = str(policy.get("mode") or "MASKED_ONLY").upper()
    mode = _LEGACY_CONTACT_MODE_ALIASES.get(raw_mode, raw_mode)
    if mode not in _CONTACT_MODES:
        raise AppException("VALIDATION_ERROR", "contactSharingPolicy.mode 非法")
    policy["mode"] = mode
    policy["sharePhone"] = bool(policy.get("sharePhone"))
    policy["shareEmail"] = bool(policy.get("shareEmail"))
    return policy


def _assert_contact_mode_allowed(policy: dict, campaign_policy: dict | None) -> None:
    config = dict(campaign_policy or {})
    # V3 privacy is fail-closed: an unconfigured campaign never means "all contact modes allowed".
    # Default permits masked access and delayed reveal only; IMMEDIATE requires explicit school policy.
    if "allowedContactSharingModes" in config:
        configured = config.get("allowedContactSharingModes")
        if not isinstance(configured, list):
            raise AppException(
                "CONTACT_MODE_NOT_ALLOWED",
                "招聘季联系方式共享策略配置无效",
                details={"mode": policy["mode"], "allowedModes": []},
                http_status=409,
            )
    else:
        configured = list(_DEFAULT_ALLOWED_CONTACT_MODES)
    allowed = {
        _LEGACY_CONTACT_MODE_ALIASES.get(str(item or "").upper(), str(item or "").upper())
        for item in configured
        if str(item or "").strip()
    }
    if not allowed or policy["mode"] not in allowed:
        raise AppException(
            "CONTACT_MODE_NOT_ALLOWED",
            "当前招聘季不允许所选联系方式共享模式",
            details={"mode": policy["mode"], "allowedModes": sorted(allowed)},
            http_status=409,
        )


def evaluate_material_readiness(profile_projection: dict, policy: dict | None) -> dict:
    policy = dict(policy or {})
    profile = dict(profile_projection.get("profile") or {})
    items = list(profile_projection.get("items") or [])
    missing: list[str] = []
    field_map = {
        "headline": "headline",
        "selfIntro": "selfIntro",
        "strengths": "strengths",
        "availableFrom": "availableFrom",
        "expectedLocations": "expectedLocations",
        "skillTags": "skillTags",
    }
    required_fields = [field_map.get(str(field), str(field)) for field in policy.get("requiredProfileFields") or []]
    for section in policy.get("requiredSections") or []:
        mapped = _SECTION_FIELDS.get(str(section or "").upper())
        if mapped and mapped not in required_fields:
            required_fields.append(mapped)
    profile_exists = bool(str(profile.get("id") or "").strip()) or int(profile.get("profileVersion") or 0) > 0
    if policy.get("profileRequired") and not profile_exists:
        missing.append("PROFILE_NOT_READY")
    for key in required_fields:
        value = profile.get(key)
        if value in (None, "", []):
            missing.append(f"profile.{key}")
    item_types = {str(item.get("itemType") or "").upper() for item in items}
    for required_type in policy.get("requiredItemTypes") or []:
        required = str(required_type or "").upper()
        if required and required not in item_types:
            missing.append(f"itemType.{required}")
    min_items = int(policy.get("minItemCount") or 0)
    if len(items) < min_items:
        missing.append(f"minItemCount.{min_items}")
    return {"ready": not missing, "missing": missing}


def _attachment_ids(profile_projection: dict) -> list[str]:
    result: list[str] = []
    for item in profile_projection.get("items") or []:
        for file_id in item.get("fileIds") or []:
            text = str(file_id)
            if text not in result:
                result.append(text)
    return result


def create_material_snapshot_in_tx(
    db,
    *,
    tenant_id: int,
    volunteer_group_id: int,
    student_id: int,
    campaign_id: int,
    submission_version: int,
    consent_version: str,
    consent_at: datetime,
    contact_sharing_policy: dict | None,
) -> InternshipApplicationMaterialSnapshot:
    if int(submission_version) < 1:
        raise AppException("VALIDATION_ERROR", "submissionVersion 必须从 1 开始")
    consent_version = str(consent_version or "").strip()
    if not consent_version or not isinstance(consent_at, datetime):
        raise AppException("VALIDATION_ERROR", "材料投递必须记录 consentVersion/consentAt")
    campaign = db.scalar(
        select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.id == _as_id(campaign_id),
            InternshipRecruitmentCampaign.tenant_id == tenant_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        )
    )
    if not campaign:
        raise not_found("招聘季不存在或不在当前租户")
    projection = profile_svc.build_profile_projection_in_tx(
        db, tenant_id=tenant_id, student_id=_as_id(student_id)
    )
    readiness = evaluate_material_readiness(projection, campaign.application_material_policy_json)
    if not readiness["ready"]:
        raise AppException(
            "APPLICATION_MATERIAL_INCOMPLETE",
            "实习档案未满足当前招聘季投递要求",
            details={"missing": readiness["missing"]},
            http_status=409,
        )
    profile = dict(projection.get("profile") or {})
    school_facts = dict(projection.get("schoolFacts") or {})
    # Keep public profile/items, but never volunteers/company/position/application statement/contact values.
    profile_snapshot = {
        "profile": profile,
        "items": list(projection.get("items") or []),
    }
    policy = normalize_contact_sharing_policy(contact_sharing_policy)
    _assert_contact_mode_allowed(policy, campaign.application_material_policy_json)
    payload = {
        "volunteerGroupId": str(volunteer_group_id),
        "studentId": str(student_id),
        "campaignId": str(campaign.id),
        "batchId": str(campaign.batch_id),
        "submissionVersion": int(submission_version),
        "profileVersion": int(profile.get("profileVersion") or 0),
        "profileSnapshot": profile_snapshot,
        "schoolFactSnapshot": school_facts,
        "attachmentFileIds": _attachment_ids(projection),
        "materialPolicySnapshot": dict(campaign.application_material_policy_json or {}),
        "consentVersion": consent_version,
        "consentAt": consent_at.isoformat(),
        "contactSharingPolicy": policy,
    }
    digest = _snapshot_hash(payload)
    existing = db.scalar(
        select(InternshipApplicationMaterialSnapshot).where(
            InternshipApplicationMaterialSnapshot.tenant_id == tenant_id,
            InternshipApplicationMaterialSnapshot.volunteer_group_id == _as_id(volunteer_group_id),
            InternshipApplicationMaterialSnapshot.submission_version == int(submission_version),
        )
    )
    if existing:
        if existing.snapshot_hash != digest:
            raise AppException("DATA_CONFLICT", "同一 submissionVersion 已存在不同材料快照")
        return existing
    snapshot = InternshipApplicationMaterialSnapshot(
        tenant_id=tenant_id,
        volunteer_group_id=_as_id(volunteer_group_id),
        student_id=_as_id(student_id),
        campaign_id=campaign.id,
        batch_id=campaign.batch_id,
        submission_version=int(submission_version),
        profile_version=int(profile.get("profileVersion") or 0),
        profile_snapshot_json=profile_snapshot,
        school_fact_snapshot_json=school_facts,
        attachment_file_ids_json=_attachment_ids(projection),
        material_policy_snapshot_json=dict(campaign.application_material_policy_json or {}),
        consent_version=consent_version,
        consent_at=consent_at,
        contact_sharing_policy=policy,
        snapshot_hash=digest,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def snapshot_public_dict(snapshot: InternshipApplicationMaterialSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "studentId": str(snapshot.student_id),
        "campaignId": str(snapshot.campaign_id),
        "batchId": str(snapshot.batch_id),
        "submissionVersion": snapshot.submission_version,
        "profileVersion": snapshot.profile_version,
        "profileSnapshot": snapshot.profile_snapshot_json,
        "schoolFactSnapshot": snapshot.school_fact_snapshot_json,
        "attachmentFileIds": list(snapshot.attachment_file_ids_json or []),
        "consentVersion": snapshot.consent_version,
        "consentAt": snapshot.consent_at.isoformat(),
        "contactSharingPolicy": snapshot.contact_sharing_policy,
        "snapshotHash": snapshot.snapshot_hash,
        "createdAt": snapshot.created_at.isoformat() if snapshot.created_at else "",
    }
