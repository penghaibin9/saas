"""A03 student-selection Authority adapter over sealed A01 canonical services.

This layer owns no duplicate facts.  It adapts the A03 PC/mobile wire contract and adds the
submit-only V3 evidence barrier before re-entering A01's canonical volunteer transaction.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipApplication, InternshipRecord
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_student_profile import StudentInternshipProfile
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_application_material_snapshot_service as material_svc
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.modules.internship.services import internship_volunteer_group_service as group_svc
from app.modules.internship.services import internship_volunteer_retry
from app.modules.internship.services import internship_volunteer_service as volunteer_svc
from app.services.db_service import _as_id, _tid, session

_DEFAULT_CONSENT_POLICY_VERSION = "INTERNSHIP_APPLICATION_PRIVACY_V1"
_ACTIVE_GROUP_STATUSES = ("DRAFT", "SUBMITTED", "LOCKED", "NEEDS_REVISION", "APPROVED")


def _consent_policy_version(policy: dict | None) -> str:
    value = str(dict(policy or {}).get("consentPolicyVersion") or _DEFAULT_CONSENT_POLICY_VERSION).strip()
    if not value:
        raise AppException("DATA_CONFLICT", "招聘季材料授权版本配置无效", http_status=409)
    return value


def _resolve_context_in_tx(
    db,
    *,
    tenant_id: int,
    student_id: int,
    campaign_id=None,
    record_id=None,
    batch_id=None,
):
    """Resolve A03's public context without making the client own a campaign primary key."""
    if campaign_id not in (None, ""):
        campaign, record = volunteer_svc._resolve_student_record_in_tx(
            db, tenant_id=tenant_id, student_id=student_id, campaign_id=_as_id(campaign_id),
        )
        if record_id not in (None, "") and int(record.id) != _as_id(record_id):
            raise AppException("DATA_CONFLICT", "实习记录与招聘季上下文不一致", http_status=409)
        if batch_id not in (None, "") and int(campaign.batch_id) != _as_id(batch_id):
            raise AppException("DATA_CONFLICT", "批次与招聘季上下文不一致", http_status=409)
        return campaign, record

    if record_id not in (None, ""):
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(record_id),
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.student_id == student_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        if not record:
            raise not_found("当前学生实习记录不存在")
        if batch_id not in (None, "") and int(record.batch_id) != _as_id(batch_id):
            raise AppException("DATA_CONFLICT", "批次与学生实习记录不一致", http_status=409)
        campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.tenant_id == tenant_id,
            InternshipRecruitmentCampaign.batch_id == record.batch_id,
            InternshipRecruitmentCampaign.status == "OPEN",
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        ).order_by(InternshipRecruitmentCampaign.round_no.desc(), InternshipRecruitmentCampaign.id.desc()))
        if not campaign:
            raise not_found("当前实习记录没有开放中的招聘季")
        return campaign, record

    group = db.scalar(select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.tenant_id == tenant_id,
        InternshipVolunteerGroup.student_id == student_id,
        InternshipVolunteerGroup.status.in_(_ACTIVE_GROUP_STATUSES),
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).order_by(InternshipVolunteerGroup.id.desc()))
    if group:
        campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.id == group.campaign_id,
            InternshipRecruitmentCampaign.tenant_id == tenant_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        ))
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == group.record_id,
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.student_id == student_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        if campaign and record:
            return campaign, record

    campaign = db.scalar(
        select(InternshipRecruitmentCampaign)
        .join(InternshipRecord, InternshipRecord.batch_id == InternshipRecruitmentCampaign.batch_id)
        .where(
            InternshipRecruitmentCampaign.tenant_id == tenant_id,
            InternshipRecruitmentCampaign.status == "OPEN",
            InternshipRecruitmentCampaign.is_deleted.is_(False),
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.student_id == student_id,
            InternshipRecord.status.in_(("PREPARING", "READY")),
            InternshipRecord.is_deleted.is_(False),
        )
        .order_by(InternshipRecruitmentCampaign.round_no.desc(), InternshipRecruitmentCampaign.id.desc())
    )
    if not campaign:
        raise not_found("当前学生没有开放中的招聘季")
    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.student_id == student_id,
        InternshipRecord.batch_id == campaign.batch_id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.id.desc()))
    if not record:
        raise not_found("当前招聘季没有对应的学生实习记录")
    return campaign, record


def _application_row(row: InternshipApplication) -> dict:
    return {
        "id": str(row.id),
        "volunteerNo": int(row.volunteer_no),
        "positionId": str(row.position_id or ""),
        "companyName": row.company_name or "",
        "positionName": row.position_name or "",
        "applicationStatement": row.application_statement or "",
        "status": row.status,
        "materialSnapshotId": str(row.material_snapshot_id or ""),
        "version": int(row.version or 0),
    }


def _material_preview_in_tx(db, *, tenant_id: int, student_id: int, campaign) -> dict:
    projection = profile_svc.build_profile_projection_in_tx(
        db, tenant_id=tenant_id, student_id=_as_id(student_id),
    )
    readiness = material_svc.evaluate_material_readiness(
        projection, campaign.application_material_policy_json,
    )
    if not readiness["ready"]:
        raise AppException(
            "APPLICATION_MATERIAL_INCOMPLETE",
            "实习档案未满足当前招聘季投递要求",
            details={"missing": readiness["missing"]},
            http_status=409,
        )
    profile = dict(projection.get("profile") or {})
    school_facts = dict(projection.get("schoolFacts") or {})
    profile_snapshot = {"profile": profile, "items": list(projection.get("items") or [])}
    payload = {
        "studentId": str(student_id),
        "campaignId": str(campaign.id),
        "batchId": str(campaign.batch_id),
        "profileVersion": int(profile.get("profileVersion") or 0),
        "profileSnapshot": profile_snapshot,
        "schoolFactSnapshot": school_facts,
        "attachmentFileIds": material_svc._attachment_ids(projection),
        "materialPolicySnapshot": dict(campaign.application_material_policy_json or {}),
    }
    return {
        "previewHash": f"sha256:{material_svc._snapshot_hash(payload)}",
        "profileVersion": int(profile.get("profileVersion") or 0),
        "consentPolicyVersion": _consent_policy_version(campaign.application_material_policy_json),
        "profileSnapshot": profile_snapshot,
        "schoolFactSnapshot": school_facts,
        "attachmentFileIds": list(payload["attachmentFileIds"]),
        "materialPolicySnapshot": dict(payload["materialPolicySnapshot"]),
    }


def _contact_policy(payload: dict) -> dict:
    if isinstance(payload.get("contactSharingPolicy"), dict):
        raw = dict(payload["contactSharingPolicy"])
    else:
        raw = {"mode": str(payload.get("contactSharingMode") or "MASKED_ONLY").upper()}
    return material_svc.normalize_contact_sharing_policy(raw)


def get_my_volunteers(*, user: dict) -> dict:
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = _resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == record.id,
            InternshipVolunteerGroup.campaign_id == campaign.id,
            InternshipVolunteerGroup.is_deleted.is_(False),
        ).with_for_update())
        if not group:
            return {
                "group": {
                    "exists": False,
                    "campaignId": str(campaign.id),
                    "recordId": str(record.id),
                    "studentId": str(student_id),
                    "batchId": str(record.batch_id),
                    "status": "DRAFT",
                    "version": 0,
                },
                "recordVersion": int(record.version or 0),
                "applications": [],
            }
        changed = group_svc.lazy_release_expired_lock_in_tx(
            db, group=group, tenant_id=tenant_id, user=user,
        )
        rows = list(db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == tenant_id,
            InternshipApplication.record_id == record.id,
            InternshipApplication.application_type == "POSITION",
            InternshipApplication.volunteer_no.in_((1, 2, 3)),
            InternshipApplication.is_deleted.is_(False),
        ).order_by(InternshipApplication.volunteer_no.asc())).all())
        if changed:
            db.commit()
        return {
            "group": {"exists": True, **group_svc.group_dict(group)},
            "recordVersion": int(record.version or 0),
            "applications": [_application_row(row) for row in rows],
        }


def save_my_draft(*, user: dict, body: dict) -> dict:
    """A03 draft adapter.  V3 submit evidence is deliberately absent and never required here."""
    payload = dict(body or {})
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        def _operation():
            campaign, record = _resolve_context_in_tx(
                db,
                tenant_id=tenant_id,
                student_id=student_id,
                campaign_id=payload.get("campaignId"),
                record_id=payload.get("internshipId") or payload.get("recordId"),
                batch_id=payload.get("batchId"),
            )
            return volunteer_svc.save_or_submit_in_tx(
                db,
                tenant_id=tenant_id,
                student_id=student_id,
                record_id=record.id,
                campaign_id=campaign.id,
                volunteers=list(payload.get("items") or payload.get("volunteers") or []),
                expected_record_version=payload.get("expectedRecordVersion"),
                expected_group_version=payload.get("expectedGroupVersion"),
                expected_application_versions=payload.get("expectedApplicationVersions") or {},
                submit=False,
                user=user,
            )

        group, applications, record = internship_volunteer_retry.run_with_bounded_mysql_retry(db, _operation)
        return {
            "group": {"exists": True, **group_svc.group_dict(group)},
            "recordVersion": int(record.version or 0),
            "applications": [_application_row(row) for row in applications],
        }


def get_my_material_preview(*, user: dict) -> dict:
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = _resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        preview = _material_preview_in_tx(
            db, tenant_id=tenant_id, student_id=student_id, campaign=campaign,
        )
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == record.id,
            InternshipVolunteerGroup.campaign_id == campaign.id,
            InternshipVolunteerGroup.is_deleted.is_(False),
        ))
        return {
            **preview,
            "campaignId": str(campaign.id),
            "batchId": str(campaign.batch_id),
            "internshipId": str(record.id),
            "recordVersion": int(record.version or 0),
            "groupVersion": int(group.version or 0) if group else 0,
        }


def submit_my_saved_volunteers(*, user: dict, body: dict) -> dict:
    """Validate A03 V3 evidence under locks, then delegate mutation to sealed A01 Authority."""
    payload = dict(body or {})
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    expected_profile_raw = payload.get("expectedProfileVersion")
    preview_hash = str(payload.get("confirmMaterialPreviewHash") or payload.get("previewHash") or "").strip()
    if expected_profile_raw in (None, "") or not preview_hash:
        raise AppException("VALIDATION_ERROR", "提交志愿必须提供 expectedProfileVersion + previewHash")
    try:
        expected_profile = int(expected_profile_raw)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "expectedProfileVersion 必须为非负整数") from exc
    if expected_profile < 0:
        raise AppException("VALIDATION_ERROR", "expectedProfileVersion 必须为非负整数")

    with session() as db:
        def _operation():
            campaign, resolved_record = _resolve_context_in_tx(
                db,
                tenant_id=tenant_id,
                student_id=student_id,
                campaign_id=payload.get("campaignId"),
                record_id=payload.get("internshipId") or payload.get("recordId"),
                batch_id=payload.get("batchId"),
            )
            # Frozen lock order for the A03 submit seam: Record -> Group -> Applications -> Profile.
            record = db.scalar(select(InternshipRecord).where(
                InternshipRecord.id == resolved_record.id,
                InternshipRecord.tenant_id == tenant_id,
                InternshipRecord.student_id == student_id,
                InternshipRecord.is_deleted.is_(False),
            ).with_for_update())
            if not record:
                raise not_found("学生实习记录不存在")
            group = db.scalar(select(InternshipVolunteerGroup).where(
                InternshipVolunteerGroup.tenant_id == tenant_id,
                InternshipVolunteerGroup.record_id == record.id,
                InternshipVolunteerGroup.campaign_id == campaign.id,
                InternshipVolunteerGroup.is_deleted.is_(False),
            ).with_for_update())
            if not group:
                raise AppException("VALIDATION_ERROR", "没有可提交的志愿草稿")
            try:
                expected_group = int(payload.get("expectedGroupVersion"))
            except (TypeError, ValueError) as exc:
                raise AppException("VALIDATION_ERROR", "必须提供有效的 expectedGroupVersion") from exc
            if int(group.version or 0) != expected_group:
                raise AppException("DATA_CONFLICT", "志愿组版本已变化，请刷新后重试", http_status=409)

            all_rows = list(db.scalars(select(InternshipApplication).where(
                InternshipApplication.tenant_id == tenant_id,
                InternshipApplication.record_id == record.id,
                InternshipApplication.application_type == "POSITION",
                InternshipApplication.volunteer_no.in_((1, 2, 3)),
                InternshipApplication.is_deleted.is_(False),
            ).order_by(InternshipApplication.volunteer_no.asc()).with_for_update()).all())
            rows = [row for row in all_rows if row.status == "DRAFT"]
            if not rows:
                raise AppException("VALIDATION_ERROR", "没有可提交的志愿草稿")

            profile = db.scalar(select(StudentInternshipProfile).where(
                StudentInternshipProfile.tenant_id == tenant_id,
                StudentInternshipProfile.student_id == student_id,
                StudentInternshipProfile.is_deleted.is_(False),
            ).with_for_update())
            current_profile = int(profile.profile_version or 0) if profile else 0
            if current_profile != expected_profile:
                raise AppException("DATA_CONFLICT", "实习档案已变化，请重新预览后提交", http_status=409)

            preview = _material_preview_in_tx(
                db, tenant_id=tenant_id, student_id=student_id, campaign=campaign,
            )
            if preview["profileVersion"] != expected_profile or preview["previewHash"] != preview_hash:
                raise AppException("DATA_CONFLICT", "企业视角材料预览已变化，请重新确认后提交", http_status=409)
            consent_version = str(payload.get("consentPolicyVersion") or payload.get("consentVersion") or "").strip()
            if consent_version != preview["consentPolicyVersion"]:
                raise AppException("DATA_CONFLICT", "材料授权版本已更新，请重新预览并确认", http_status=409)
            contact_policy = _contact_policy(payload)
            material_svc._assert_contact_mode_allowed(
                contact_policy, campaign.application_material_policy_json,
            )

            volunteers = [
                {
                    "volunteerNo": int(row.volunteer_no),
                    "positionId": int(row.position_id or 0),
                    "applicationStatement": row.application_statement or "",
                }
                for row in rows
            ]
            expected_apps = {int(row.volunteer_no): int(row.version or 0) for row in all_rows}
            return volunteer_svc.save_or_submit_in_tx(
                db,
                tenant_id=tenant_id,
                student_id=student_id,
                record_id=record.id,
                campaign_id=campaign.id,
                volunteers=volunteers,
                expected_record_version=int(record.version or 0),
                expected_group_version=expected_group,
                expected_application_versions=expected_apps,
                submit=True,
                consent_version=consent_version,
                consent_at=datetime.utcnow(),
                contact_sharing_policy=contact_policy,
                user=user,
            )

        group, applications, record = internship_volunteer_retry.run_with_bounded_mysql_retry(db, _operation)
        return {
            "group": {"exists": True, **group_svc.group_dict(group)},
            "recordVersion": int(record.version or 0),
            "applications": [_application_row(row) for row in applications],
        }
