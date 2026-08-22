"""Stage C3 operator-accessible post-archive correction contracts."""
from __future__ import annotations

import inspect


def test_post_archive_correction_routes_are_registered_on_public_bundle():
    from app.modules.academic_affairs.routers.academic_affairs_bundle import build_router

    # FastAPI 0.141 keeps app.include_router(...) as a lazy _IncludedRouter. The
    # academic-affairs bundle is the formal unit consumed by route_registration, so
    # assert its concrete route table rather than an internal application expansion.
    bundle = build_router()
    paths = {route.path for route in bundle.routes if getattr(route, "path", None)}
    assert "/academic-affairs/archive/batches/{batch_id}/manifest/verify" in paths
    assert "/academic-affairs/archive/batches/{batch_id}/corrections" in paths
    assert "/academic-affairs/archive/corrections/{case_id}" in paths
    assert "/academic-affairs/archive/corrections/{case_id}/approve" in paths
    assert "/academic-affairs/archive/corrections/{case_id}/reject" in paths


def test_post_archive_correction_public_service_is_stage_c3_immutable_service():
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as immutable
    from app.modules.academic_affairs.services import academic_affairs_archive_service as public

    assert public.list_correction_cases is immutable.list_correction_cases
    assert public.get_correction_case is immutable.get_correction_case
    assert public.create_correction_case is immutable.create_correction_case
    assert public.approve_correction_case is immutable.approve_correction_case
    assert public.verify_manifest is immutable.verify_manifest


def test_w1_reject_route_keeps_same_high_risk_permission_and_dedicated_review_owner():
    from app.modules.academic_affairs.routers import archive_correction_router
    from app.modules.academic_affairs.services import academic_affairs_archive_correction_review_service as review

    router_source = inspect.getsource(archive_correction_router)
    reject_source = inspect.getsource(review.reject_correction_case)

    assert router_source.count('require_permission("academicAffairs.archive.manage")') >= 6
    assert "review_service.reject_correction_case" in router_source
    assert ".with_for_update().first()" in reject_source
    assert "case.created_by" in reject_source
    assert "case.status != _PENDING" in reject_source
    assert 'case.status = "REJECTED"' in reject_source
    assert "POST_ARCHIVE_CORRECTION_REJECT" in reject_source


def test_w1_reject_service_cannot_write_official_fact_or_manifest():
    from app.modules.academic_affairs.services import academic_affairs_archive_correction_review_service as review

    reject_source = inspect.getsource(review.reject_correction_case)
    assert "apply_official_correction_fact" not in reject_source
    assert "ArchiveManifest(" not in reject_source
    assert "official_fact_id =" not in reject_source
    assert "resulting_manifest_id =" not in reject_source
