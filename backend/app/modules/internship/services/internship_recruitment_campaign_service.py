"""RecruitmentCampaign canonical service for E-A01.

All mutations are tenant-scoped. Existing rows are locked with SELECT ... FOR UPDATE and
must match expectedVersion before mutation. `phase` and material readiness are always derived.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipBatch
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.modules.internship.enterprise_collaboration_contract import (
    RECRUITMENT_CAMPAIGN_TRANSITIONS,
    RECRUITMENT_CAMPAIGN_WINDOW_FIELDS,
)
from app.services.db_service import _as_id, _iso, _tid, session

_WINDOW_PHASES = (
    ("SCHOOL_CONFIRMING", "school_confirm_start_at", "school_confirm_end_at"),
    ("ENTERPRISE_DECIDING", "enterprise_decision_start_at", "enterprise_decision_end_at"),
    ("STUDENT_SELECTING", "student_select_start_at", "student_select_end_at"),
    ("POSITION_SUBMITTING", "position_submit_start_at", "position_submit_end_at"),
    ("INVITING", "invite_start_at", "invite_end_at"),
)
_WINDOW_PAIRS = tuple((fields[1], fields[2]) for fields in _WINDOW_PHASES)
_MATERIAL_POLICY_KEYS = frozenset({
    "schemaVersion", "profileRequired", "requiredSections", "requiredItemTypes",
    "applicationStatementRequired", "minStatementLength", "resumePdfEnabled",
    "allowedContactSharingModes",
})
_MATERIAL_SECTIONS = frozenset({"SELF_INTRO", "SKILLS", "AVAILABILITY", "LOCATION_PREFERENCES"})
_MATERIAL_ITEM_TYPES = frozenset({"SKILL_EVIDENCE", "CERTIFICATE", "PROJECT", "PRACTICE", "AWARD", "PORTFOLIO"})
_CONTACT_MODES = frozenset({"MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT", "IMMEDIATE"})


def derive_campaign_phase(campaign: InternshipRecruitmentCampaign, now: datetime | None = None) -> str:
    status = (campaign.status or "DRAFT").upper()
    if status in {"FROZEN", "CLOSED", "ARCHIVED"}:
        return status
    if status != "OPEN":
        return "PREPARE"

    current = now or datetime.utcnow()
    # If windows overlap, expose the most advanced active phase. This avoids persisting a
    # second phase truth while keeping a single deterministic UI phase.
    for phase, start_field, end_field in _WINDOW_PHASES:
        start = getattr(campaign, start_field, None)
        end = getattr(campaign, end_field, None)
        if start is not None and end is not None and start <= current <= end:
            return phase
    return "PREPARE"


def _validate_windows(values: dict[str, Any]) -> None:
    for start_field, end_field in _WINDOW_PAIRS:
        start = values.get(start_field)
        end = values.get(end_field)
        if (start is None) != (end is None):
            raise AppException(
                "VALIDATION_ERROR",
                f"{start_field}/{end_field} 必须同时填写或同时为空",
            )
        if start is not None and end is not None and start > end:
            raise AppException("VALIDATION_ERROR", f"{start_field} 不能晚于 {end_field}")

    access_end = values.get("enterprise_access_end_at")
    if access_end is not None:
        configured_ends = [values.get(end_field) for _, end_field in _WINDOW_PAIRS]
        configured_ends = [value for value in configured_ends if value is not None]
        if configured_ends and access_end < max(configured_ends):
            raise AppException(
                "VALIDATION_ERROR",
                "enterprise_access_end_at 不能早于已配置招聘窗口结束时间",
            )


def _normalize_string_array(value, *, field: str, allowed: frozenset[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AppException("VALIDATION_ERROR", f"applicationMaterialPolicy.{field} 必须是数组")
    output: list[str] = []
    for raw in value:
        item = str(raw or "").upper().strip()
        if item not in allowed:
            raise AppException("VALIDATION_ERROR", f"applicationMaterialPolicy.{field} 含非法值 {item or '-'}")
        if item not in output:
            output.append(item)
    return output


def _normalize_material_policy(value) -> dict | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        raise AppException("VALIDATION_ERROR", "applicationMaterialPolicy 必须是对象")
    unknown = set(value) - _MATERIAL_POLICY_KEYS
    if unknown:
        raise AppException("VALIDATION_ERROR", f"applicationMaterialPolicy 含未知字段：{','.join(sorted(unknown))}")
    schema_version = str(value.get("schemaVersion") or "V1").upper()
    if schema_version != "V1":
        raise AppException("VALIDATION_ERROR", "applicationMaterialPolicy.schemaVersion 仅支持 V1")
    try:
        min_statement = int(value.get("minStatementLength") or 0)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "applicationMaterialPolicy.minStatementLength 必须是整数") from exc
    if min_statement < 0 or min_statement > 5000:
        raise AppException("VALIDATION_ERROR", "applicationMaterialPolicy.minStatementLength 必须在 0-5000")
    return {
        "schemaVersion": "V1",
        "profileRequired": bool(value.get("profileRequired", False)),
        "requiredSections": _normalize_string_array(
            value.get("requiredSections"), field="requiredSections", allowed=_MATERIAL_SECTIONS,
        ),
        "requiredItemTypes": _normalize_string_array(
            value.get("requiredItemTypes"), field="requiredItemTypes", allowed=_MATERIAL_ITEM_TYPES,
        ),
        "applicationStatementRequired": bool(value.get("applicationStatementRequired", False)),
        "minStatementLength": min_statement,
        "resumePdfEnabled": bool(value.get("resumePdfEnabled", True)),
        "allowedContactSharingModes": _normalize_string_array(
            value.get("allowedContactSharingModes", ["MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT"]),
            field="allowedContactSharingModes",
            allowed=_CONTACT_MODES,
        ),
    }


def _get_campaign(db, campaign_id: int, *, tenant_id: int, lock: bool = False):
    stmt = select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == _as_id(campaign_id),
        InternshipRecruitmentCampaign.tenant_id == tenant_id,
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    campaign = db.scalar(stmt)
    if not campaign:
        raise not_found("招聘季不存在或不在当前租户范围内")
    return campaign


def _require_expected_version(campaign: InternshipRecruitmentCampaign, body: dict[str, Any]) -> int:
    raw = body.get("expectedVersion", body.get("version"))
    if raw is None:
        raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（乐观锁）")
    try:
        expected = int(raw)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from exc
    current = int(campaign.version or 0)
    if expected != current:
        raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试")
    return current


def _row(campaign: InternshipRecruitmentCampaign, now: datetime | None = None) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "batchId": str(campaign.batch_id),
        "campaignCode": campaign.campaign_code,
        "campaignName": campaign.campaign_name,
        "roundNo": campaign.round_no,
        "status": campaign.status,
        "phase": derive_campaign_phase(campaign, now=now),
        "inviteStartAt": _iso(campaign.invite_start_at),
        "inviteEndAt": _iso(campaign.invite_end_at),
        "positionSubmitStartAt": _iso(campaign.position_submit_start_at),
        "positionSubmitEndAt": _iso(campaign.position_submit_end_at),
        "studentSelectStartAt": _iso(campaign.student_select_start_at),
        "studentSelectEndAt": _iso(campaign.student_select_end_at),
        "enterpriseDecisionStartAt": _iso(campaign.enterprise_decision_start_at),
        "enterpriseDecisionEndAt": _iso(campaign.enterprise_decision_end_at),
        "schoolConfirmStartAt": _iso(campaign.school_confirm_start_at),
        "schoolConfirmEndAt": _iso(campaign.school_confirm_end_at),
        "enterpriseAccessEndAt": _iso(campaign.enterprise_access_end_at),
        "enterpriseConfirmRequired": bool(campaign.enterprise_confirm_required),
        "teacherConfirmSlaHours": int(campaign.teacher_confirm_sla_hours or 48),
        "applicationMaterialPolicy": dict(campaign.application_material_policy_json or {}),
        "remark": campaign.remark or "",
        "version": int(campaign.version or 0),
        "createdAt": _iso(campaign.created_at),
        "updatedAt": _iso(campaign.updated_at),
    }


def _body_values(body: dict[str, Any]) -> dict[str, Any]:
    def _clean(value):
        return value.strip() if isinstance(value, str) else value

    values: dict[str, Any] = {}
    mapping = {
        "campaignCode": "campaign_code",
        "campaignName": "campaign_name",
        "roundNo": "round_no",
        "inviteStartAt": "invite_start_at",
        "inviteEndAt": "invite_end_at",
        "positionSubmitStartAt": "position_submit_start_at",
        "positionSubmitEndAt": "position_submit_end_at",
        "studentSelectStartAt": "student_select_start_at",
        "studentSelectEndAt": "student_select_end_at",
        "enterpriseDecisionStartAt": "enterprise_decision_start_at",
        "enterpriseDecisionEndAt": "enterprise_decision_end_at",
        "schoolConfirmStartAt": "school_confirm_start_at",
        "schoolConfirmEndAt": "school_confirm_end_at",
        "enterpriseAccessEndAt": "enterprise_access_end_at",
        "enterpriseConfirmRequired": "enterprise_confirm_required",
        "teacherConfirmSlaHours": "teacher_confirm_sla_hours",
        "remark": "remark",
    }
    for source, target in mapping.items():
        if source in body:
            values[target] = _clean(body[source])
    if "applicationMaterialPolicy" in body:
        values["application_material_policy_json"] = _normalize_material_policy(body.get("applicationMaterialPolicy"))
    return values


def _validate_identity(values: dict[str, Any]) -> None:
    if "campaign_code" in values and not (values["campaign_code"] or "").strip():
        raise AppException("VALIDATION_ERROR", "campaignCode 不能为空")
    if "campaign_name" in values and not (values["campaign_name"] or "").strip():
        raise AppException("VALIDATION_ERROR", "campaignName 不能为空")
    if "round_no" in values:
        try:
            round_no = int(values["round_no"])
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "roundNo 必须是正整数") from exc
        if round_no < 1:
            raise AppException("VALIDATION_ERROR", "roundNo 必须从 1 开始")
        values["round_no"] = round_no
    if "teacher_confirm_sla_hours" in values:
        try:
            hours = int(values["teacher_confirm_sla_hours"])
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "teacherConfirmSlaHours 必须是整数") from exc
        if hours < 1 or hours > 168:
            raise AppException("VALIDATION_ERROR", "teacherConfirmSlaHours 必须在 1-168 小时")
        values["teacher_confirm_sla_hours"] = hours


def create_campaign(body: dict[str, Any] | None, user=None):
    body = dict(body or {})
    tenant_id = _tid()
    if not body.get("batchId"):
        raise AppException("VALIDATION_ERROR", "batchId 不能为空")
    values = _body_values(body)
    _validate_identity(values)
    if not values.get("campaign_code") or not values.get("campaign_name"):
        raise AppException("VALIDATION_ERROR", "campaignCode/campaignName 不能为空")
    values.setdefault("round_no", 1)
    values.setdefault("teacher_confirm_sla_hours", 48)
    _validate_windows(values)

    with session() as db:
        batch = db.scalar(
            select(InternshipBatch).where(
                InternshipBatch.id == _as_id(body["batchId"]),
                InternshipBatch.tenant_id == tenant_id,
                InternshipBatch.is_deleted.is_(False),
            )
        )
        if not batch:
            raise AppException("VALIDATION_ERROR", "实习批次不存在或不在当前租户")
        campaign = InternshipRecruitmentCampaign(
            tenant_id=tenant_id,
            batch_id=batch.id,
            status="DRAFT",
            **values,
        )
        db.add(campaign)
        db.flush()
        db.commit()
        return _row(campaign)


def update_campaign(campaign_id: int, body: dict[str, Any] | None, user=None):
    body = dict(body or {})
    tenant_id = _tid()
    with session() as db:
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=True)
        current_version = _require_expected_version(campaign, body)
        if campaign.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅 DRAFT 招聘季允许修改名称、批次、材料策略和关键时间窗")

        if "batchId" in body:
            batch = db.scalar(
                select(InternshipBatch).where(
                    InternshipBatch.id == _as_id(body["batchId"]),
                    InternshipBatch.tenant_id == tenant_id,
                    InternshipBatch.is_deleted.is_(False),
                )
            )
            if not batch:
                raise AppException("VALIDATION_ERROR", "实习批次不存在或不在当前租户")
            campaign.batch_id = batch.id

        values = _body_values(body)
        _validate_identity(values)
        merged = {field: getattr(campaign, field) for field in RECRUITMENT_CAMPAIGN_WINDOW_FIELDS}
        merged.update(values)
        _validate_windows(merged)
        for field, value in values.items():
            setattr(campaign, field, value)
        campaign.version = current_version + 1
        db.commit()
        return _row(campaign)


def transition_campaign(
    campaign_id: int,
    target_status: str,
    body: dict[str, Any] | None,
    user=None,
):
    body = dict(body or {})
    target = (target_status or "").strip().upper()
    tenant_id = _tid()
    with session() as db:
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=True)
        current_version = _require_expected_version(campaign, body)
        allowed = RECRUITMENT_CAMPAIGN_TRANSITIONS.get(campaign.status, frozenset())
        if target not in allowed:
            raise AppException(
                "DATA_CONFLICT",
                f"招聘季状态 {campaign.status} 不可迁移到 {target}",
            )
        if target == "OPEN":
            values = {
                field: getattr(campaign, field)
                for field in RECRUITMENT_CAMPAIGN_WINDOW_FIELDS
            }
            _validate_windows(values)
        campaign.status = target
        campaign.version = current_version + 1
        db.commit()
        return _row(campaign)


def get_campaign(campaign_id: int, *, now: datetime | None = None):
    with session() as db:
        return _row(_get_campaign(db, campaign_id, tenant_id=_tid()), now=now)


def list_campaigns(*, batch_id: int | None = None, page: int = 1, page_size: int = 20):
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    with session() as db:
        stmt = select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.tenant_id == _tid(),
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        )
        if batch_id is not None:
            stmt = stmt.where(InternshipRecruitmentCampaign.batch_id == _as_id(batch_id))
        rows = db.scalars(
            stmt.order_by(InternshipRecruitmentCampaign.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).all()
        has_more = len(rows) > page_size
        items = [_row(item) for item in rows[:page_size]]
        return {"items": items, "page": page, "pageSize": page_size, "hasMore": has_more}
