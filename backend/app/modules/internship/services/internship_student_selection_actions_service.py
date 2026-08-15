"""Canonical student-selection post-submit actions over A01 facts.

No duplicate truth is introduced here. Mutations lock the canonical Record -> VolunteerGroup ->
Applications rows, preserve immutable material snapshots, and reuse the existing group decision/audit
Authority.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipApplication, InternshipRecord
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_application_material_snapshot_service as material_svc
from app.modules.internship.services import internship_audit_service
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.modules.internship.services import internship_volunteer_group_service as group_svc
from app.modules.internship.services import internship_volunteer_retry
from app.services.db_service import _tid, session


def _expected_group_version(body: dict) -> int:
    raw = dict(body or {}).get("expectedGroupVersion")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "必须提供有效的 expectedGroupVersion") from exc
    if value < 0:
        raise AppException("VALIDATION_ERROR", "expectedGroupVersion 必须为非负整数")
    return value


def _resolve_and_lock_group_in_tx(db, *, tenant_id: int, student_id: int, payload: dict):
    campaign, resolved_record = selection_svc._resolve_context_in_tx(
        db,
        tenant_id=tenant_id,
        student_id=student_id,
        campaign_id=payload.get("campaignId"),
        record_id=payload.get("internshipId") or payload.get("recordId"),
        batch_id=payload.get("batchId"),
    )
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
        InternshipVolunteerGroup.student_id == student_id,
        InternshipVolunteerGroup.campaign_id == campaign.id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).with_for_update())
    if not group:
        raise not_found("当前招聘季尚无志愿组")
    return campaign, record, group


def _lock_applications_in_tx(db, *, tenant_id: int, record_id: int) -> list[InternshipApplication]:
    return list(db.scalars(select(InternshipApplication).where(
        InternshipApplication.tenant_id == tenant_id,
        InternshipApplication.record_id == record_id,
        InternshipApplication.application_type == "POSITION",
        InternshipApplication.volunteer_no.in_((1, 2, 3)),
        InternshipApplication.is_deleted.is_(False),
    ).order_by(InternshipApplication.volunteer_no.asc()).with_for_update()).all())


def _result(group: InternshipVolunteerGroup, record: InternshipRecord, rows: list[InternshipApplication]) -> dict:
    return {
        "group": {"exists": True, **group_svc.group_dict(group)},
        "recordVersion": int(record.version or 0),
        "applications": [selection_svc._application_row(row) for row in rows],
    }


def withdraw_my_submission(*, user: dict, body: dict) -> dict:
    """Withdraw the whole current SUBMITTED group back to DRAFT without revalidating positions."""
    payload = dict(body or {})
    expected_group = _expected_group_version(payload)
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)

    with session() as db:
        def _operation():
            campaign, record, group = _resolve_and_lock_group_in_tx(
                db, tenant_id=tenant_id, student_id=student_id, payload=payload,
            )
            if int(group.version or 0) != expected_group:
                raise AppException("DATA_CONFLICT", "志愿组版本已变化，请刷新后重试", http_status=409)
            if group.status != "SUBMITTED":
                if group.status == "LOCKED":
                    raise AppException(
                        "VOLUNTEER_GROUP_LOCKED",
                        "企业已给出拟接收意向，不能直接撤回；请先申请改志愿",
                        http_status=409,
                    )
                raise AppException("DATA_CONFLICT", f"志愿组状态 {group.status} 不能整组撤回", http_status=409)

            rows = _lock_applications_in_tx(db, tenant_id=tenant_id, record_id=record.id)
            active_rows = [row for row in rows if row.position_id is not None and row.status not in {"WITHDRAWN", "CANCELLED"}]
            invalid = [row for row in active_rows if row.status != "PENDING_REVIEW"]
            if invalid:
                raise AppException(
                    "DATA_CONFLICT",
                    "志愿组与申请状态不一致，请刷新后联系管理员",
                    details={"applicationIds": [str(row.id) for row in invalid]},
                    http_status=409,
                )

            group_svc.supersede_group_active_decisions_in_tx(
                db, group=group, reason="STUDENT_WITHDRAW_VOLUNTEER_GROUP", user=user,
            )
            for row in active_rows:
                row.status = "DRAFT"
                row.material_snapshot_id = None
                row.submitted_at = None
                row.version = int(row.version or 0) + 1

            before_status = group.status
            previous_snapshot_id = group.current_material_snapshot_id
            group.status = "DRAFT"
            group.current_material_snapshot_id = None
            group.submitted_at = None
            group.locked_application_id = None
            group.locked_by_decision_id = None
            group.locked_at = None
            group.teacher_confirm_deadline = None
            group.unlock_requested_at = None
            group.unlock_request_reason = None
            group.revision_requested_at = None
            group.revision_reason = None
            # The withdrawn submission is no longer an active contact-sharing grant. The immutable
            # snapshot (including its historical consent) remains untouched.
            group.contact_consent_revoked_at = None
            group.version = int(group.version or 0) + 1

            internship_audit_service.add_audit(
                db,
                target_type="INTERNSHIP_VOLUNTEER_GROUP",
                target_id=group.id,
                action="STUDENT_WITHDRAW_VOLUNTEER_GROUP",
                user=user,
                batch_id=group.batch_id,
                internship_id=group.record_id,
                before_status=before_status,
                after_status=group.status,
                new_version=group.version,
                detail={
                    "campaignId": str(campaign.id),
                    "submissionVersion": int(group.submission_version or 0),
                    "previousMaterialSnapshotId": str(previous_snapshot_id or ""),
                    "applicationIds": [str(row.id) for row in active_rows],
                },
            )
            return group, record, rows

        group, record, rows = internship_volunteer_retry.run_with_bounded_mysql_retry(db, _operation)
        return _result(group, record, rows)


def request_my_unlock(*, user: dict, body: dict) -> dict:
    payload = dict(body or {})
    expected_group = _expected_group_version(payload)
    reason = str(payload.get("reason") or "").strip()
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)

    with session() as db:
        def _operation():
            _campaign, record, group = _resolve_and_lock_group_in_tx(
                db, tenant_id=tenant_id, student_id=student_id, payload=payload,
            )
            current_version = int(group.version or 0)
            if group.unlock_requested_at is not None and group.unlock_request_reason == reason and group.status == "LOCKED":
                rows = _lock_applications_in_tx(db, tenant_id=tenant_id, record_id=record.id)
                return group, record, rows
            if current_version != expected_group:
                raise AppException("DATA_CONFLICT", "志愿组版本已变化，请刷新后重试", http_status=409)
            rows = _lock_applications_in_tx(db, tenant_id=tenant_id, record_id=record.id)
            group_svc.request_unlock_in_tx(db, group=group, reason=reason, user=user)
            return group, record, rows

        group, record, rows = internship_volunteer_retry.run_with_bounded_mysql_retry(db, _operation)
        return _result(group, record, rows)


def list_my_submissions(*, user: dict) -> dict:
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = selection_svc._resolve_context_in_tx(
            db, tenant_id=tenant_id, student_id=student_id,
        )
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == record.id,
            InternshipVolunteerGroup.student_id == student_id,
            InternshipVolunteerGroup.campaign_id == campaign.id,
            InternshipVolunteerGroup.is_deleted.is_(False),
        ))
        if not group:
            return {"items": [], "total": 0}
        snapshots = list(db.scalars(select(InternshipApplicationMaterialSnapshot).where(
            InternshipApplicationMaterialSnapshot.tenant_id == tenant_id,
            InternshipApplicationMaterialSnapshot.volunteer_group_id == group.id,
            InternshipApplicationMaterialSnapshot.student_id == student_id,
            InternshipApplicationMaterialSnapshot.campaign_id == campaign.id,
        ).order_by(
            InternshipApplicationMaterialSnapshot.submission_version.desc(),
            InternshipApplicationMaterialSnapshot.id.desc(),
        )).all())
        items = []
        for snapshot in snapshots:
            data = material_svc.snapshot_public_dict(snapshot)
            items.append({
                "submissionVersion": int(snapshot.submission_version or 0),
                "materialSnapshotId": str(snapshot.id),
                "snapshotHash": snapshot.snapshot_hash,
                "consentVersion": snapshot.consent_version,
                "consentAt": snapshot.consent_at.isoformat() if snapshot.consent_at else None,
                "contactSharingPolicy": data.get("contactSharingPolicy") or {},
                "createdAt": snapshot.created_at.isoformat() if snapshot.created_at else None,
                "isCurrent": int(group.current_material_snapshot_id or 0) == int(snapshot.id),
            })
        return {"items": items, "total": len(items)}


def get_my_submission(*, user: dict, submission_version: int) -> dict:
    try:
        version = int(submission_version)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "submissionVersion 必须为正整数") from exc
    if version < 1:
        raise AppException("VALIDATION_ERROR", "submissionVersion 必须为正整数")
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = selection_svc._resolve_context_in_tx(
            db, tenant_id=tenant_id, student_id=student_id,
        )
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == record.id,
            InternshipVolunteerGroup.student_id == student_id,
            InternshipVolunteerGroup.campaign_id == campaign.id,
            InternshipVolunteerGroup.is_deleted.is_(False),
        ))
        if not group:
            raise not_found("当前招聘季尚无志愿组")
        snapshot = db.scalar(select(InternshipApplicationMaterialSnapshot).where(
            InternshipApplicationMaterialSnapshot.tenant_id == tenant_id,
            InternshipApplicationMaterialSnapshot.volunteer_group_id == group.id,
            InternshipApplicationMaterialSnapshot.student_id == student_id,
            InternshipApplicationMaterialSnapshot.campaign_id == campaign.id,
            InternshipApplicationMaterialSnapshot.submission_version == version,
        ))
        if not snapshot:
            raise not_found("该提交版本不存在")
        return {
            **material_svc.snapshot_public_dict(snapshot),
            "materialSnapshotId": str(snapshot.id),
            "isCurrent": int(group.current_material_snapshot_id or 0) == int(snapshot.id),
            "currentGroupStatus": group.status,
            "currentGroupVersion": int(group.version or 0),
            "currentContactConsentRevokedAt": (
                group.contact_consent_revoked_at.isoformat() if group.contact_consent_revoked_at else None
            ),
        }


def revoke_my_contact_consent(*, user: dict, body: dict) -> dict:
    payload = dict(body or {})
    expected_group = _expected_group_version(payload)
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)

    with session() as db:
        def _operation():
            campaign, record, group = _resolve_and_lock_group_in_tx(
                db, tenant_id=tenant_id, student_id=student_id, payload=payload,
            )
            rows = _lock_applications_in_tx(db, tenant_id=tenant_id, record_id=record.id)
            if group.current_material_snapshot_id is None:
                raise AppException("DATA_CONFLICT", "当前没有生效中的投递材料授权可撤销", http_status=409)
            if group.contact_consent_revoked_at is not None:
                return group, record, rows
            if int(group.version or 0) != expected_group:
                raise AppException("DATA_CONFLICT", "志愿组版本已变化，请刷新后重试", http_status=409)

            now = datetime.utcnow()
            group.contact_consent_revoked_at = now
            group.version = int(group.version or 0) + 1
            internship_audit_service.add_audit(
                db,
                target_type="INTERNSHIP_VOLUNTEER_GROUP",
                target_id=group.id,
                action="STUDENT_REVOKE_CONTACT_CONSENT",
                user=user,
                batch_id=group.batch_id,
                internship_id=group.record_id,
                before_status=group.status,
                after_status=group.status,
                new_version=group.version,
                detail={
                    "campaignId": str(campaign.id),
                    "materialSnapshotId": str(group.current_material_snapshot_id),
                    "submissionVersion": int(group.submission_version or 0),
                    "revokedAt": now.isoformat(),
                },
            )
            return group, record, rows

        group, record, rows = internship_volunteer_retry.run_with_bounded_mysql_retry(db, _operation)
        return _result(group, record, rows)
