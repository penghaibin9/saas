"""Deprecated thin compatibility facade for the consolidated material domain."""
from __future__ import annotations

from app.modules.graduation.materials import command_service, migration_service, query_service, rule_service, snapshot_service
from app.modules.graduation.materials.definitions import DEFAULT_MATERIAL_DEFINITIONS, DEFAULT_SPEC_BY_CODE, STAGE_GROUPS

MATERIAL_DEFINITIONS = list(DEFAULT_MATERIAL_DEFINITIONS)
SPEC_BY_CODE = DEFAULT_SPEC_BY_CODE
SYSTEM_SNAPSHOT_CODES = snapshot_service.SYSTEM_SNAPSHOT_CODES


def ensure_complete_rule(db, batch_id, user=None):
    return rule_service.active_rule(db, batch_id)


def list_rules(batch_id, user):
    return query_service.list_rules(batch_id=batch_id, user=user)


def student_library(gd_student_id, user, *, include_history=True):
    return query_service.student_library(gd_student_id, user, include_history=include_history)


def material_overview(user, **kwargs):
    return query_service.students(user, **kwargs)


def submit_material(user, material_code, file_id, *, expected_version=None):
    return command_service.submit_material(user, material_code, file_id, expected_version=expected_version)


def review_material(material_id, expected_file_version_id, action, comment, user, *, expected_version=None):
    return command_service.review_material(
        material_id, expected_file_version_id, action, comment, user, expected_version=expected_version,
    )


def ensure_structured_snapshots(_db, student, user):
    return snapshot_service.prepare_all(int(student.id), user).get("created", [])


def backfill_legacy(user, **kwargs):
    return migration_service.backfill_legacy(user, **kwargs)


def publish_template_policy(template_id, file_id, payload, user):
    return command_service.publish_template_policy(template_id, file_id, payload, user)


def update_template_policy_status(policy_id, enabled, expected_version, user):
    return command_service.update_template_policy_status(policy_id, enabled, expected_version, user)


def template_catalog(user, *, batch_id=None):
    return query_service.template_catalog(user, batch_id=batch_id)


def sync_record(record_type, record_id, user):
    detail = query_service.proposal_detail(record_id, user) if str(record_type).upper() == "PROPOSAL" else query_service.final_detail(record_id, user)
    return {"status": "ALREADY_NATIVE", "recordId": str(record_id), "materialId": detail.get("materialId")}


__all__ = [
    "MATERIAL_DEFINITIONS", "SPEC_BY_CODE", "STAGE_GROUPS", "SYSTEM_SNAPSHOT_CODES",
    "backfill_legacy", "ensure_complete_rule", "ensure_structured_snapshots", "list_rules",
    "material_overview", "publish_template_policy", "review_material", "student_library",
    "submit_material", "sync_record", "template_catalog", "update_template_policy_status",
]
