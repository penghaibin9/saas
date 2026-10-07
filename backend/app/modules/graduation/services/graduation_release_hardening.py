"""Graduation center pre-release P0/P1/P2 hardening installer."""
from __future__ import annotations




from app.modules.graduation.services.graduation_release_hardening_common import _strict_dt
from app.modules.graduation.services.graduation_release_topic_core_hardening import _install_topic_hardening
from app.modules.graduation.services.graduation_release_topic_read_hardening import _install_topic_read_hardening
from app.modules.graduation.services.graduation_release_topic_export_hardening import _install_topic_export_hardening
from app.modules.graduation.services.graduation_release_mentor_manage_hardening import _install_mentor_manage_hardening
from app.modules.graduation.services.graduation_release_mentor_stats_hardening import _install_mentor_stats_hardening
from app.modules.graduation.services.graduation_release_mentor_assignment_hardening import _install_mentor_assignment_hardening
from app.modules.graduation.services.graduation_release_grade_policy_hardening import _install_grade_policy_hardening
from app.modules.graduation.services.graduation_release_grade_appeal_hardening import _install_grade_appeal_hardening
from app.modules.graduation.services.graduation_release_grade_stats_hardening import _install_grade_stats_hardening
from app.modules.graduation.services.graduation_release_process_hardening import _install_process_hardening
from app.modules.graduation.services.graduation_release_archive_hardening import _install_archive_hardening
from app.modules.graduation.services.graduation_release_scope_hardening import _install_scope_id_hardening

_INSTALLED = False


def _install_validation_and_permission_hardening() -> None:
    from app.modules.graduation.services import graduation_batch_service as batch
    from app.core import graduation_permissions as gp
    from app.core import permissions as perms

    old_create = batch.create_batch
    old_update = batch.update_batch
    old_set_stages = batch.set_stages

    def _validate_stage_dates(stages):
        for i, stage in enumerate(stages or []):
            if not isinstance(stage, dict): continue
            for key in ("startDate", "endDate"):
                if stage.get(key) not in (None, ""):
                    _strict_dt(stage.get(key), f"stages[{i}].{key}")

    def create_batch(body):
        data = body.model_dump() if hasattr(body, "model_dump") else dict(body)
        for key in ("startDate", "endDate"): _strict_dt(data.get(key), key) if data.get(key) not in (None, "") else None
        _validate_stage_dates(data.get("stages"))
        return old_create(body)

    def update_batch(batch_id, body):
        data = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else dict(body)
        for key in ("startDate", "endDate"): _strict_dt(data.get(key), key) if data.get(key) not in (None, "") else None
        _validate_stage_dates(data.get("stages"))
        return old_update(batch_id, body)

    def set_stages(batch_id, stages):
        _validate_stage_dates(stages)
        return old_set_stages(batch_id, stages)

    batch.create_batch = create_batch
    batch.update_batch = update_batch
    batch.set_stages = set_stages

    submit_code = "graduationDesign.topic.submit"
    gp.GRADUATION_PERMISSION_CODES = frozenset(set(gp.GRADUATION_PERMISSION_CODES) | {submit_code})
    gp.GRADUATION_ENDPOINT_PERMISSIONS["submit_gd_topic_review"] = submit_code
    gp.GRADUATION_ENDPOINT_PERMISSION_OVERRIDES["graduation_topic.submit_gd_topic_review"] = submit_code

    old_effective = perms.get_effective_permission_patterns
    if not getattr(old_effective, "_gd_topic_submit_alias", False):
        def effective_patterns(user, *, strict=False):
            patterns = set(old_effective(user, strict=True) if strict else old_effective(user))
            if perms._match("graduationDesign.topic.create", patterns):
                patterns.add(submit_code)
            return sorted(patterns)
        effective_patterns._gd_topic_submit_alias = True
        perms.get_effective_permission_patterns = effective_patterns


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_scope_id_hardening()
    _install_topic_hardening()
    _install_topic_read_hardening()
    _install_topic_export_hardening()
    _install_mentor_manage_hardening()
    _install_mentor_stats_hardening()
    _install_mentor_assignment_hardening()
    _install_grade_policy_hardening()
    _install_grade_appeal_hardening()
    _install_grade_stats_hardening()
    _install_process_hardening()
    _install_archive_hardening()
    _install_validation_and_permission_hardening()
