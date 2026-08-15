"""Atomic 1/2/3 volunteer write path over canonical InternshipApplication rows."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipApplication, InternshipPosition, InternshipRecord
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_application_material_snapshot_service as material_svc
from app.modules.internship.services import internship_audit_service
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility_svc
from app.modules.internship.services import internship_volunteer_group_service as group_svc
from app.modules.internship.services import internship_volunteer_retry
from app.services.db_service import _as_id, _tid, session


def _expected_application_versions(value) -> dict[int, int]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise AppException("VALIDATION_ERROR", "expectedApplicationVersions 必须是对象")
    result: dict[int, int] = {}
    for raw_slot, raw_version in value.items():
        try:
            slot = int(raw_slot)
            version = int(raw_version)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "expectedApplicationVersions 必须使用整数槽位和版本") from exc
        if slot not in (1, 2, 3) or version < 0:
            raise AppException("VALIDATION_ERROR", "expectedApplicationVersions 槽位必须为 1/2/3 且版本非负")
        result[slot] = version
    return result


def _parse_consent_at(value) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", "consentAt 必须是 ISO-8601 日期时间") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _assert_application_statements(policy: dict | None, volunteers: list[dict], *, submit: bool) -> None:
    if not submit:
        return
    config = dict(policy or {})
    required = bool(config.get("applicationStatementRequired"))
    try:
        minimum = max(0, int(config.get("minStatementLength") or 0))
    except (TypeError, ValueError) as exc:
        raise AppException("DATA_CONFLICT", "招聘季申请说明最小长度配置无效") from exc
    if required and minimum < 1:
        minimum = 1
    if not required and minimum == 0:
        return
    invalid = []
    for item in volunteers:
        statement = str(item.get("applicationStatement") or "").strip()
        if len(statement) < minimum:
            invalid.append({
                "volunteerNo": int(item.get("volunteerNo") or 0),
                "reason": f"申请说明不少于 {minimum} 字",
            })
    if invalid:
        raise AppException(
            "APPLICATION_MATERIAL_INCOMPLETE",
            "岗位申请说明未满足当前招聘季要求",
            details={"invalidItems": invalid},
            http_status=409,
        )


def save_or_submit_in_tx(
    db,
    *,
    tenant_id: int,
    student_id: int,
    record_id: int,
    campaign_id: int,
    volunteers: list[dict],
    expected_record_version: int,
    expected_group_version: int,
    expected_application_versions: dict[int, int] | None,
    submit: bool,
    consent_version: str | None = None,
    consent_at: datetime | None = None,
    contact_sharing_policy: dict | None = None,
    user=None,
):
    """Lock order is frozen: Record -> VolunteerGroup -> Applications volunteer_no ASC."""
    if not 1 <= len(volunteers) <= 3:
        raise AppException("VALIDATION_ERROR", "志愿必须为 1-3 个")
    slots = [int(v.get("volunteerNo") or 0) for v in volunteers]
    if slots != list(range(1, len(volunteers) + 1)):
        raise AppException("VALIDATION_ERROR", "volunteerNo 必须连续固定为 1/2/3")
    position_ids = [int(v.get("positionId") or 0) for v in volunteers]
    if len(set(position_ids)) != len(position_ids) or any(x <= 0 for x in position_ids):
        raise AppException("VALIDATION_ERROR", "三个志愿岗位不得重复且必须有效")
    try:
        expected_record = int(expected_record_version)
        expected_group = int(expected_group_version)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "必须提供有效的 expectedRecordVersion/expectedGroupVersion") from exc
    expected_apps = _expected_application_versions(expected_application_versions)

    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == _as_id(record_id),
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.student_id == _as_id(student_id),
        InternshipRecord.is_deleted.is_(False),
    ).with_for_update())
    if not record:
        raise not_found("实习记录不存在")
    if int(record.version or 0) != expected_record:
        raise AppException("DATA_CONFLICT", "学生实习记录已变化，请刷新后重试", http_status=409)
    if record.status not in {"PREPARING", "READY"}:
        raise AppException("DATA_CONFLICT", "当前实习状态不可修改招聘季志愿")

    campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == _as_id(campaign_id),
        InternshipRecruitmentCampaign.tenant_id == tenant_id,
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    ))
    if not campaign:
        raise not_found("招聘季不存在")
    if record.batch_id != campaign.batch_id:
        raise AppException("DATA_CONFLICT", "学生实习记录与招聘季批次不一致")
    _assert_application_statements(
        campaign.application_material_policy_json,
        volunteers,
        submit=submit,
    )

    group = group_svc.get_or_create_group_in_tx(
        db, tenant_id=tenant_id, record_id=record.id, student_id=student_id,
        batch_id=campaign.batch_id, campaign_id=campaign.id,
    )
    group_svc.assert_student_editable_in_tx(db, group=group, tenant_id=tenant_id)
    if int(group.version or 0) != expected_group:
        raise AppException("DATA_CONFLICT", "志愿组版本已变化，请刷新后重试", http_status=409)

    existing = list(db.scalars(select(InternshipApplication).where(
        InternshipApplication.tenant_id == tenant_id,
        InternshipApplication.record_id == record.id,
        InternshipApplication.application_type == "POSITION",
        InternshipApplication.volunteer_no.in_([1, 2, 3]),
        InternshipApplication.is_deleted.is_(False),
    ).order_by(InternshipApplication.volunteer_no.asc()).with_for_update()).all())
    by_slot = {int(row.volunteer_no): row for row in existing}
    for slot, row in by_slot.items():
        if slot not in expected_apps:
            raise AppException("VALIDATION_ERROR", f"缺少第{slot}志愿 expectedApplicationVersion")
        if int(row.version or 0) != expected_apps[slot]:
            raise AppException("DATA_CONFLICT", f"第{slot}志愿版本已变化，请刷新后重试", http_status=409)

    checked = {}
    for item in volunteers:
        position = db.scalar(select(InternshipPosition).where(
            InternshipPosition.id == int(item["positionId"]),
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.is_deleted.is_(False),
        ))
        if not position:
            raise not_found("志愿岗位不存在")
        eligibility_svc.evaluate_position_for_student_in_tx(
            db, tenant_id=tenant_id, record=record, campaign=campaign, position=position,
        )
        checked[int(item["volunteerNo"])] = position

    # Rechecks are complete before any mutation. Existing enterprise decisions are history-bound to
    # the previous material snapshot and must be superseded before slot content changes.
    group_svc.supersede_group_active_decisions_in_tx(
        db, group=group, reason="STUDENT_VOLUNTEERS_CHANGED", user=user,
    )

    now = datetime.utcnow()
    before_group_status = group.status
    for item in volunteers:
        slot = int(item["volunteerNo"])
        p = checked[slot]
        row = by_slot.get(slot)
        if row is None:
            if expected_apps.get(slot, 0) not in (0,):
                raise AppException("DATA_CONFLICT", f"第{slot}志愿尚未创建，expectedApplicationVersion 应为 0")
            row = InternshipApplication(
                tenant_id=tenant_id, record_id=record.id, student_id=student_id,
                batch_id=campaign.batch_id, application_type="POSITION", volunteer_no=slot,
            )
            db.add(row)
            by_slot[slot] = row
        elif row.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "已批准志愿不能普通修改")
        row.position_id = p.id
        row.company_name = p.company_name
        row.position_name = p.title
        row.work_address = p.work_address or p.work_location
        row.application_statement = str(item.get("applicationStatement") or "").strip() or None
        row.status = "DRAFT"
        row.material_snapshot_id = None
        row.submitted_at = None
        row.version = int(row.version or 0) + 1

    # Slots omitted from a shorter draft are kept as historical rows but withdrawn, never DELETEd.
    for slot, row in by_slot.items():
        if slot > len(volunteers) and row.status not in {"APPROVED", "CANCELLED", "WITHDRAWN"}:
            row.status = "WITHDRAWN"
            row.version = int(row.version or 0) + 1

    if submit:
        next_submission = int(group.submission_version or 0) + 1
        snapshot = material_svc.create_material_snapshot_in_tx(
            db, tenant_id=tenant_id, volunteer_group_id=group.id, student_id=student_id,
            campaign_id=campaign.id, submission_version=next_submission,
            consent_version=str(consent_version or ""), consent_at=consent_at,
            contact_sharing_policy=contact_sharing_policy,
        )
        for slot in range(1, len(volunteers) + 1):
            row = by_slot[slot]
            row.material_snapshot_id = snapshot.id
            row.status = "PENDING_REVIEW"
            row.submitted_at = now
        group_svc.mark_submitted_in_tx(
            db, group=group, material_snapshot_id=snapshot.id,
            submission_version=next_submission, now=now,
        )
        action = "VOLUNTEER_GROUP_SUBMIT"
    else:
        group.status = "DRAFT" if group.status != "NEEDS_REVISION" else "NEEDS_REVISION"
        group.version = int(group.version or 0) + 1
        action = "VOLUNTEER_GROUP_SAVE"

    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action=action,
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status=before_group_status,
        after_status=group.status,
        new_version=group.version,
        detail={"campaignId": str(group.campaign_id), "slots": [1, 2, 3][:len(volunteers)]},
    )
    db.flush()
    return group, [by_slot[i] for i in sorted(by_slot) if i <= len(volunteers)], record


def _resolve_student_record_in_tx(db, *, tenant_id: int, student_id: int, campaign_id: int):
    campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == _as_id(campaign_id),
        InternshipRecruitmentCampaign.tenant_id == tenant_id,
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    ))
    if not campaign:
        raise not_found("招聘季不存在")
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


def get_my_volunteers(*, user: dict, campaign_id: int) -> dict:
    from app.modules.internship.services import internship_student_profile_service as profile_svc

    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        _campaign, record = _resolve_student_record_in_tx(
            db, tenant_id=tenant_id, student_id=student_id, campaign_id=campaign_id,
        )
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == record.id,
            InternshipVolunteerGroup.campaign_id == _as_id(campaign_id),
            InternshipVolunteerGroup.is_deleted.is_(False),
        ).with_for_update())
        if not group:
            return {
                "group": {"exists": False, "campaignId": str(campaign_id), "status": "DRAFT", "version": 0},
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
            InternshipApplication.volunteer_no.in_([1, 2, 3]),
            InternshipApplication.is_deleted.is_(False),
        ).order_by(InternshipApplication.volunteer_no.asc())).all())
        if changed:
            db.commit()
        return {
            "group": {"exists": True, **group_svc.group_dict(group)},
            "recordVersion": int(record.version or 0),
            "applications": [_application_row(row) for row in rows],
        }


def save_my_volunteers(*, user: dict, body: dict, submit: bool) -> dict:
    from app.modules.internship.services import internship_student_profile_service as profile_svc

    payload = dict(body or {})
    campaign_id = _as_id(payload.get("campaignId"))
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    consent_at = _parse_consent_at(payload.get("consentAt"))
    with session() as db:
        def _operation():
            _campaign, record = _resolve_student_record_in_tx(
                db, tenant_id=tenant_id, student_id=student_id, campaign_id=campaign_id,
            )
            return save_or_submit_in_tx(
                db,
                tenant_id=tenant_id,
                student_id=student_id,
                record_id=record.id,
                campaign_id=campaign_id,
                volunteers=list(payload.get("volunteers") or []),
                expected_record_version=payload.get("expectedRecordVersion"),
                expected_group_version=payload.get("expectedGroupVersion"),
                expected_application_versions=payload.get("expectedApplicationVersions") or {},
                submit=submit,
                consent_version=payload.get("consentVersion"),
                consent_at=consent_at,
                contact_sharing_policy=payload.get("contactSharingPolicy"),
                user=user,
            )

        group, applications, record = internship_volunteer_retry.run_with_bounded_mysql_retry(db, _operation)
        return {
            "group": {"exists": True, **group_svc.group_dict(group)},
            "recordVersion": int(record.version or 0),
            "applications": [_application_row(row) for row in applications],
        }
