"""Deprecated thin facade for legacy imports of the graduation material center."""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.modules.graduation.materials import access_service, command_service, export_service, manifest_service, migration_service, query_service, record_service, rule_service


def _user(user=None):
    return user or get_current_user_ctx() or {}


def list_rules(batch_id=None):
    return query_service.list_rules(batch_id=batch_id, user=_user())


def create_rule(payload, user):
    return rule_service.create_rule(payload, user)


def activate_rule(rule_id, user):
    return rule_service.activate_rule(rule_id, user)


def submit_proposal(user, body):
    return record_service.submit_proposal(user, body)


def submit_final(user, body):
    return record_service.submit_final(user, body)


def proposal_detail(proposal_id, user=None):
    return query_service.proposal_detail(proposal_id, _user(user))


def final_detail(final_id, user=None):
    return query_service.final_detail(final_id, _user(user))


def record_versions(record_type, record_id, *, student_mode=False, user=None):
    return query_service.record_versions(record_type, record_id, _user(user), student_mode=student_mode)


def review_proposal(proposal_id, action, comment, user, *, expected_version=None, file_version_id=None):
    if expected_version is None or file_version_id is None:
        raise AppException("VALIDATION_ERROR", "旧审核调用必须补充 expectedVersion 和 fileVersionId")
    return record_service.review_proposal(
        proposal_id, action, comment, user,
        expected_version=expected_version, expected_file_version_id=file_version_id,
    )


def review_final(final_id, action, comment, user, *, expected_version=None, file_version_id=None):
    if expected_version is None or file_version_id is None:
        raise AppException("VALIDATION_ERROR", "旧审核调用必须补充 expectedVersion 和 fileVersionId")
    return record_service.review_final(
        final_id, action, comment, user,
        expected_version=expected_version, expected_file_version_id=file_version_id,
    )


def backfill_legacy(user, *, limit=500, **kwargs):
    return migration_service.backfill_legacy(user, page_size=limit, **kwargs)


def student_material_library(gd_student_id, user, *, include_history=True):
    return query_service.student_library(gd_student_id, user, include_history=include_history)


def publish_template_asset(template_id, file_id, user):
    return command_service.publish_template_policy(template_id, file_id, {}, user)


def template_versions(template_id, user=None):
    return query_service.template_versions(template_id, _user(user))


def file_archive(gd_student_id, archive_batch_no, user):
    return manifest_service.file_archive(gd_student_id, archive_batch_no, user)


def batch_file(archive_batch_no, batch_id, preview_token, user):
    return manifest_service.batch_file(archive_batch_no, batch_id, preview_token, user)


def get_manifest(gd_student_id, user):
    return query_service.latest_manifest(gd_student_id, user)


def build_student_package(gd_student_id, user):
    job = export_service.create_student_export_job(gd_student_id, user)
    return export_service.run_export_job(int(job["id"]), user)


def build_batch_package(batch_id, user):
    job = export_service.create_export_job(batch_id=batch_id, scope_type="BATCH", scope_value="", user=user)
    return export_service.run_export_job(int(job["id"]), user)


def resolve_material_download(file_id, user, *, student_mode=False):
    del student_mode
    return access_service.resolve_material(file_id, user, action="download")


def resolve_package_download(file_id, user):
    return access_service.resolve_package(file_id, user)


__all__ = [
    "activate_rule", "backfill_legacy", "batch_file", "build_batch_package", "build_student_package",
    "create_rule", "file_archive", "final_detail", "get_manifest", "list_rules", "proposal_detail",
    "publish_template_asset", "record_versions", "resolve_material_download", "resolve_package_download",
    "review_final", "review_proposal", "student_material_library", "submit_final", "submit_proposal",
    "template_versions",
]
