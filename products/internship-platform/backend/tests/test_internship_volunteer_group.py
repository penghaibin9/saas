"""E-A01 / A01-9 InternshipVolunteerGroup coordination contracts."""
from __future__ import annotations

from datetime import datetime, timedelta
import inspect

from sqlalchemy import Index, UniqueConstraint

from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_volunteer_group_service as service


def _unique_sets():
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in InternshipVolunteerGroup.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_sets():
    return {
        tuple(column.name for column in index.columns)
        for index in InternshipVolunteerGroup.__table__.indexes
        if isinstance(index, Index)
    }


def test_group_is_coordination_fact_not_second_volunteer_table():
    columns = set(InternshipVolunteerGroup.__table__.columns.keys())
    assert InternshipVolunteerGroup.__tablename__ == "t_internship_volunteer_group"
    assert {
        "tenant_id", "record_id", "student_id", "batch_id", "campaign_id", "status",
        "submission_version", "current_material_snapshot_id", "submitted_at", "locked_application_id",
        "locked_at", "locked_by_decision_id", "teacher_confirm_deadline", "approved_at",
        "revision_requested_at", "revision_reason", "released_at", "release_reason",
        "released_by_user_id", "unlock_requested_at", "unlock_request_reason",
        "contact_consent_revoked_at",
    } <= columns
    assert not {"volunteer_no", "position_id", "company_id"} & columns
    assert ("tenant_id", "record_id", "campaign_id") in _unique_sets()


def test_group_indexes_support_student_workbench_and_timeout_release():
    indexes = _index_sets()
    assert ("tenant_id", "student_id", "campaign_id", "status", "is_deleted") in indexes
    assert ("tenant_id", "campaign_id", "status", "teacher_confirm_deadline", "is_deleted") in indexes
    assert ("tenant_id", "record_id", "status", "is_deleted") in indexes


def test_campaign_has_frozen_48_hour_sla_without_second_phase_truth():
    columns = set(InternshipRecruitmentCampaign.__table__.columns.keys())
    assert "teacher_confirm_sla_hours" in columns
    assert InternshipRecruitmentCampaign.teacher_confirm_sla_hours.default.arg == 48
    assert service._DEFAULT_TEACHER_CONFIRM_SLA_HOURS == 48
    assert "phase" not in columns


def test_accept_intent_lock_records_application_decision_and_teacher_deadline():
    now = datetime(2026, 9, 10, 8, 0, 0)
    group = InternshipVolunteerGroup(
        id=1, tenant_id=1, record_id=2, student_id=3, batch_id=4, campaign_id=5,
        status="SUBMITTED", submission_version=1, version=0,
    )
    original_audit = service.internship_audit_service.add_audit
    original_notify = service._notify_lock_in_tx
    service.internship_audit_service.add_audit = lambda *args, **kwargs: None
    service._notify_lock_in_tx = lambda *args, **kwargs: None
    try:
        service.lock_for_accept_intent_in_tx(
            None, group=group, application_id=77, decision_id=99,
            teacher_confirm_sla_hours=48, now=now,
        )
    finally:
        service.internship_audit_service.add_audit = original_audit
        service._notify_lock_in_tx = original_notify
    assert group.status == "LOCKED"
    assert group.locked_application_id == 77
    assert group.locked_by_decision_id == 99
    assert group.teacher_confirm_deadline == now + timedelta(hours=48)


def test_sla_rejects_more_than_168_hours():
    source = inspect.getsource(service.lock_for_accept_intent_in_tx)
    assert "hours > 168" in source
    assert "1-168" in source


def test_expired_lock_lazily_expires_decision_and_preserves_history():
    source = inspect.getsource(service.lazy_release_expired_lock_in_tx)
    assert 'group.status = "NEEDS_REVISION"' in source
    assert 'group.release_reason = "TEACHER_CONFIRM_TIMEOUT"' in source
    assert 'effect_status="EXPIRED"' in source
    assert "group.locked_by_decision_id = None" not in source
    assert "group.locked_application_id = None" not in source
    assert "delete(" not in source.lower()
    assert "AUTO_RELEASE_ENTERPRISE_CONFIRM_LOCK" in source


def test_locked_group_blocks_student_edit_and_has_explicit_unlock_request():
    source = inspect.getsource(service.assert_student_editable_in_tx)
    unlock = inspect.getsource(service.request_unlock_in_tx)
    assert "lazy_release_expired_lock_in_tx(" in source
    assert 'group.status == "LOCKED"' in source
    assert "VOLUNTEER_GROUP_LOCKED" in source
    assert 'group.status in {"APPROVED", "CLOSED"}' in source
    assert "unlock_requested_at" in unlock
    assert "unlock_request_reason" in unlock
    assert "STUDENT_REQUEST_VOLUNTEER_UNLOCK" in unlock


def test_teacher_release_supersedes_active_accept_intent_and_is_audited():
    revision_source = inspect.getsource(service.teacher_request_revision_in_tx)
    approve_source = inspect.getsource(service.teacher_mark_approved_in_tx)
    assert 'effect_status="SUPERSEDED"' in revision_source
    assert "REQUEST_VOLUNTEER_REVISION" in revision_source
    assert "APPROVE_VOLUNTEER_GROUP" in approve_source
    assert "released_at" in revision_source
    assert "release_reason" in revision_source
    assert "locked_by_decision_id" in revision_source
    assert "locked_application_id" in revision_source
    assert "delete(" not in revision_source.lower()
    assert "delete(" not in approve_source.lower()


def test_student_change_supersedes_non_accept_enterprise_decisions():
    source = inspect.getsource(service.supersede_group_active_decisions_in_tx)
    assert 'effect_status="SUPERSEDED"' in source
    assert "STUDENT_VOLUNTEERS_CHANGED" not in source  # caller supplies the reason contract
    assert "ENTERPRISE_APPLICATION_ACCEPT_INTENT" not in source
    assert "VOLUNTEER_GROUP_LOCKED" in source
