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
    gp.GRADUATION_ENDPOINT_PERMISSION_OVERRIDES["graduation_release_hardening.appeal_list"] = "graduationDesign.grade.appealReview"
    gp.GRADUATION_ENDPOINT_PERMISSION_OVERRIDES["graduation_release_hardening.archive_list"] = "graduationDesign.archive.view"

    old_effective = perms.get_effective_permission_patterns
    if not getattr(old_effective, "_gd_topic_submit_alias", False):
        def effective_patterns(user):
            patterns = set(old_effective(user))
            if perms._match("graduationDesign.topic.create", patterns):
                patterns.add(submit_code)
            return sorted(patterns)
        effective_patterns._gd_topic_submit_alias = True
        perms.get_effective_permission_patterns = effective_patterns


def _install_router_overlays() -> None:
    from fastapi import APIRouter, Depends, Query
    from app.core.permissions import require_permission
    from app.core.response import paginate, success
    from app.modules.graduation.routers import graduation_archive, graduation_more
    from app.modules.graduation.services import graduation_archive_service as archive_service
    from app.modules.graduation.services import graduation_more_service as more_service

    archive_router = APIRouter(prefix="/graduation", tags=["毕业设计-上线硬化"])

    @archive_router.get("/gd-archives", summary="归档列表（分页+精确备案批次筛选）")
    def archive_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200), keyword: str | None = None, status: str | None = None, batchId: str | None = None, archiveBatchNo: str | None = None, user=Depends(require_permission("graduationDesign.archive.view"))):
        items, total = archive_service.list_archives(page, pageSize, keyword=keyword, status=status, batch_id=batchId, archive_batch_no=archiveBatchNo)
        return success(paginate(items, total, page, pageSize))

    appeal_router = APIRouter(prefix="/graduation", tags=["毕业设计-上线硬化"])

    @appeal_router.get("/gd-grade-appeals", summary="成绩申诉列表（SQL 分页+批次范围）")
    def appeal_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200), status: str | None = None, keyword: str | None = None, batchId: str | None = None, user=Depends(require_permission("graduationDesign.grade.appealReview"))):
        items, total = more_service.list_appeals(page=page, page_size=pageSize, status=status, keyword=keyword, batch_id=batchId)
        return success(paginate(items, total, page, pageSize))

    if not getattr(graduation_archive.router, "_gd_release_archive_overlay", False):
        graduation_archive.router.routes[0:0] = list(archive_router.routes)
        graduation_archive.router._gd_release_archive_overlay = True
    if not getattr(graduation_more.router, "_gd_release_appeal_overlay", False):
        graduation_more.router.routes[0:0] = list(appeal_router.routes)
        graduation_more.router._gd_release_appeal_overlay = True


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
    _install_router_overlays()
